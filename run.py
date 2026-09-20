import argparse
import threading
import webbrowser
from pathlib import Path

import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Launch the local CPU vision workbench")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    from backend.cimg_native import library
    try:
        library()
    except (ValueError,OSError):
        print('Building the CImg CPU bridge once for this computer…',flush=True)
        try:
            from scripts.build_vision import build
            build()
        except Exception as error:
            print(f'CImg setup requires a C++ compiler: {error}. Other operations remain available.',flush=True)
    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{args.port}")).start()
    uvicorn.run("backend.app:app", host="127.0.0.1", port=args.port, access_log=False)
