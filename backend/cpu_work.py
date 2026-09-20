"""Stop obsolete CPU jobs between native calls while retaining single-worker ownership."""
import asyncio
import threading

import anyio
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool


class WorkCancelled(Exception):
    pass


def check_cancelled(cancel_event):
    if cancel_event is not None and cancel_event.is_set():
        raise WorkCancelled()


async def run_async(http_request, function, *args):
    """Cancel an in-flight provider request when the browser disconnects."""
    result, failure = Response(status_code=499), None
    async with anyio.create_task_group() as watchers:
        async def watch_disconnect():
            while True:
                if (await http_request.receive())['type'] == 'http.disconnect':
                    watchers.cancel_scope.cancel()
                    return
        watchers.start_soon(watch_disconnect)
        try:
            result = await function(*args)
        except Exception as error:
            failure = error
        finally:
            watchers.cancel_scope.cancel()
    if failure is not None:
        raise failure
    return result


async def run_cpu(http_request, lock, function, *args):
    # The endpoint's JSON model has already consumed the body. Only this watcher
    # reads subsequent ASGI messages; is_disconnected() can miss them in middleware.
    stop = threading.Event()

    async def watch_disconnect():
        try:
            while True:
                message = await http_request.receive()
                if message['type'] == 'http.disconnect':
                    return
        finally:
            stop.set()

    result, failure = None, None
    async with anyio.create_task_group() as watchers:
        watchers.start_soon(watch_disconnect)
        try:
            async with lock:
                check_cancelled(stop)
                # AnyIO shielding alone does not cover a raw asyncio.Task.cancel().
                # Shield a retained worker task, then drain it before giving up the lock.
                worker = asyncio.create_task(run_in_threadpool(function, *args, cancel_event=stop))
                try:
                    result = await asyncio.shield(worker)
                except asyncio.CancelledError:
                    stop.set()
                    with anyio.CancelScope(shield=True):
                        while not worker.done():
                            try:
                                await asyncio.shield(worker)
                            except asyncio.CancelledError:
                                continue
                            except Exception:
                                break
                        # Consume a cooperative cancellation or other worker failure;
                        # the request's cancellation remains the reason for exit.
                        if not worker.cancelled():
                            worker.exception()
                    raise
                check_cancelled(stop)
        except WorkCancelled:
            result = Response(status_code=499)
        except Exception as exc:
            # Raise after task-group cleanup so FastAPI sees the original type,
            # e.g. a readable ValueError for a corrupt image, not ExceptionGroup.
            failure = exc
        finally:
            stop.set()
            watchers.cancel_scope.cancel()
    if failure is not None:
        raise failure
    return result
