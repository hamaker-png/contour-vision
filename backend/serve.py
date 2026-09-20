"""Public container entry point. Use run.py for the local desktop workflow."""
import uvicorn
from .cimg_native import library
from .local_settings import public_mode
from .server_policy import configured_hosts, integer_setting

def main():
    if not public_mode():
        raise SystemExit("Set CONTOUR_PUBLIC=1 for this server entry point. Use run.py for local mode.")
    configured_hosts()
    integer_setting("CONTOUR_MAX_ACTIVE_POSTS", 2, 1, 8)
    integer_setting("CONTOUR_POSTS_PER_MINUTE", 60, 1, 600)
    port = integer_setting("PORT", 8000, 1, 65535)
    library()  # A container with a missing CImg bridge must fail readiness.
    uvicorn.run("backend.app:app", host="0.0.0.0", port=port, workers=1,
                access_log=False, proxy_headers=False, limit_concurrency=16,
                timeout_keep_alive=5, timeout_graceful_shutdown=30, server_header=False)

if __name__ == "__main__":
    main()
