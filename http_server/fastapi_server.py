import uvicorn
from fastapi import FastAPI, WebSocket, Request
from fastapi.staticfiles import StaticFiles
from starlette.endpoints import WebSocketEndpoint
from starlette.responses import RedirectResponse


def parse_argv():
    argv = sys.argv
    parser = argparse.ArgumentParser(usage="{} [options]".format(argv[0]))
    parser.add_argument('-p', '--port', type=str, default='8080', help='Port of service')
    parser.add_argument('-P', '--path', type=str, default='.', help='Static files path')
    return parser.parse_args()


app = FastAPI()
pool: list[WebSocket] = []
# usage:
# [await e.send_text(...) for e in pool]


@app.get('/')
async def get_root():
    return RedirectResponse('/static/index.html')


@app.websocket_route("/message/order", name="ws")
class MessageService(WebSocketEndpoint):
    async def on_connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        pool.append(websocket)
        await websocket.send_text("link success![From server]")

    async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:
        pool.remove(websocket)


def main():
	args = parse_argv()
	app.mount("/static", StaticFiles(directory=args.path), name="static")
    uvicorn.run(app, host="0.0.0.0", port=int(args.port))


if __name__ == '__main__':
	main()
