import json
from tornado.web import Application, StaticFileHandler, RequestHandler
from tornado.ioloop import IOLoop
from tornado.httpserver import HTTPServer


def parse_argv():
    argv = sys.argv
    parser = argparse.ArgumentParser(usage="{} [options]".format(argv[0]))
    parser.add_argument('-p', '--port', type=str, default='8080', help='Port of service')
    parser.add_argument('-P', '--path', type=str, default='.', help='Static files path')
    return parser.parse_args()


class DownloadHandler(RequestHandler):
    def get(self):
        rsrc = self.get_query_argument('filename')
        self.redirect("/" + rsrc)


class RestfulHandler(RequestHandler):
    def post(self):
        req = json.loads(self.request.body.decode(encoding='UTF-8'))
        resp = {
            'code': 200,
            'message': 'request success!'
        }
        return self.write(resp)


class EchoHandler(RequestHandler):
    def post(self):
        print(self.request.body.decode(encoding='TUF-8'))
        resp = {
            'code': 200,
            'message': 'request success!'
        }
        return self.write(resp)


# allow cross domain
class CrossDomainHandler(RequestHandler):
    def allowMyOrigin(self):
        # @todo: set allow list
        #   allow_list = []
        #   if self.request.headers['Origin'] ...
        if 'Origin' not in self.request.headers:
            return
        origin = self.request.headers['Origin']
        print("origin :", origin)
        self.set_header("Access-Control-Allow-Origin", origin)  # 这个地方能够写域名
        self.set_header("Access-Control-Allow-Headers", "x-requested-with")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')


class XSSHandler(CrossDomainHandler, StaticFileHandler):
    def set_default_headers(self):
        self.allowMyOrigin()


def main():
    args = parse_argv()
    urls = [
        (r"/download", DownloadHandler),
        (r"/restful/api", RestfulHandler),
        (r"/echo", EchoHandler),
        (r'^/(.*?)$', StaticFileHandler, {"path": args.path, "default_filename": "index.html"},),
    ]
    HTTPServer(Application(urls, static_path=args.path)).listen(int(args.port))
    IOLoop.current().start()


if __name__ == '__main__':
    main()
