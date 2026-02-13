from .bridge import Window, webview2_api

__version__ = "0.0.2"

__all__ = ["Window", "webview2_api"]

def main(args: list[str] | None = None) -> int:
    import sys
    import argparse
    parser = argparse.ArgumentParser(description='Run an application by webview.')
    parser.add_argument('--url', type=str, help='Entry of the application')
    parser.add_argument('--icon', type=str, required=False, default=None, help='Path of app icon')
    parser.add_argument('--title', type=str, required=False, default=None, help='Application title')
    parser.add_argument('--cache', type=str, required=False, default=None, help='Path of webview cache')
    parser.add_argument('--size', type=str, required=False, default=None, help='Window size')
    args = parser.parse_args(sys.argv[1:] if args is None else args)
    win = Window(args.title, args.icon, args.url, args.size, args.cache)
    import asyncio
    asyncio.run(win.run())
    return 0
