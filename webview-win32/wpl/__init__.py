import asyncio
import ctypes
import json
import os
import traceback
import typing
import uuid

import pythoncom
import voxe
import win32con
import win32gui

_dir_ = os.path.dirname(__file__)
os.add_dll_directory(_dir_)
dll = ctypes.CDLL("WebviewWrapper.dll")
dll.listener = ctypes.CFUNCTYPE(None, ctypes.c_char_p)
dll.set_title.argtypes = [ctypes.c_char_p]
dll.set_title.restype = None
dll.set_position.argtypes = [ctypes.c_int, ctypes.c_int]
dll.set_position.restype = None
dll.set_size.argtypes = [ctypes.c_int, ctypes.c_int]
dll.set_size.restype = None
dll.set_client.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
dll.set_client.restype = None
dll.set_navigation.argtypes = [ctypes.c_char_p]
dll.set_navigation.restype = None
dll.set_icon.argtypes = [ctypes.c_char_p]
dll.set_icon.restype = None
dll.set_listener.argtypes = [dll.listener]
dll.set_listener.restype = None
dll.set_memory.argtypes = [ctypes.c_int]
dll.set_memory.restype = None
dll.get_window.argtypes = []
dll.get_window.restype = ctypes.c_void_p
dll.read.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_int]
dll.read.restype = ctypes.c_int
dll.write.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_int]
dll.write.restype = ctypes.c_int
dll.post.argtypes = [ctypes.c_char_p]
dll.post.restype = None
dll.build.argtypes = []
dll.build.restype = None
dll.destroy.argtypes = []
dll.destroy.restype = None


class Packer:
    chunk: int = 1024 * 1024 * 10
    reqid: typing.Optional[str] = None
    pkgid: typing.Optional[str] = None
    total: int = 0
    cache: typing.Optional[bytearray] = None
    offset: int = 0
    futures: typing.Dict[str, asyncio.Future[bytearray]] = {}
    acks: typing.Dict[str, asyncio.Future[int]] = {}
    on_service = None
    scopes = {}
    cb = None
    cb2 = None

    def __init__(self):
        self.cb = lambda x: self.on_listen(x)
        self.cb2 = dll.listener(self.cb)
        dll.set_listener(self.cb2)

    def _read(self, size):
        buf = (ctypes.c_uint8 * size)()
        dll.read(buf, size)
        return bytes(buf[:size])

    def _write(self, data: bytes):
        data = data if type(data) is bytearray else bytearray(data)
        size = len(data)
        buf = (ctypes.c_uint8 * size).from_buffer(data)
        return dll.write(buf, size)

    def on_listen(self, buf: bytes):
        # print("[FRONT]", buf.decode(encoding='utf-8'))
        try:
            data = json.loads(buf)
            if "type" not in data:
                return
            if data["type"] == "ack":
                pkgid = data["pkgid"]
                if pkgid in self.acks:
                    self.acks[pkgid].set_result(1)
                return
            if data["type"] != "req":
                return
            self.pkgid = data["pkgid"]
            if self.reqid is None or self.reqid != data["reqid"]:
                self.reqid = data["reqid"]
                self.total = data["total"]
                self.cache = bytearray(self.total)
                self.offset = 0
            size = data["size"]
            self.cache[self.offset:self.offset + size] = self._read(size)  # dll.read(size)
            dll.post(json.dumps(dict(type="ack", pkgid=self.pkgid, reqid=self.reqid)).encode(encoding='utf-8'))
            self.offset += size
            if self.offset >= self.total:
                # print("[CACHE]", self.reqid, self.reqid in self.futures, self.total, self.cache)
                try:
                    ctx = voxe.loads(bytes(self.cache))
                    print("ctx :", ctx)
                    if ctx[0] in self.scopes:
                        r = self.scopes[ctx[0]](*ctx[1:])
                        asyncio.create_task(self.post_packet(voxe.dumps(0, r), self.reqid))
                    else:
                        asyncio.create_task(self.post_packet(voxe.dumps(1, "no such method"), self.reqid))
                    # print(type(self.cache))
                    # print("voxe :", )
                except Exception as e:
                    traceback.print_exc()
                    asyncio.create_task(self.post_packet(voxe.dumps(1, str(e)), self.reqid))
                    pass
                # self.post_packet(b"hello", self.reqid)
                if self.on_service:
                    self.on_service(self.cache)
            if self.offset >= self.total and self.reqid in self.futures:
                self.futures[self.reqid].set_result(self.cache)
                self.reqid = None
                self.cache = None
        except json.decoder.JSONDecodeError:
            pass
        except Exception as e:
            print(f"error : {str(e)}")
            traceback.print_exc()

    def set_memo(self, size):
        dll.set_memory(size)

    def debug(self, buf: bytes):
        cmd = buf.decode(encoding='utf-8')
        print("[FRONT]", cmd)
        if cmd == "write":
            self._write(b"hello world")
        elif cmd == "read":
            data = self._read(4)
            print("[WMEMO]", int.from_bytes(data))

    async def post_packet(self, data: bytes, reqid=None):
        if reqid is None:
            reqid = str(uuid.uuid4()).replace("-", "")
        size = len(data)
        chunk = self.chunk
        pb, pe = 0, 0
        while pb < size:
            pe = pb + chunk
            if pe > size:
                pe = size
            pkgid = str(uuid.uuid4()).replace("-", "")
            ack = asyncio.Future()
            self.acks[pkgid] = ack
            self._write(data[pb:pe])
            try:
                # print(f"[POSTM] reqid={reqid},pkgid={pkgid},total={size},size={pe-pb},begin={pb},end={pe}")
                dll.post(json.dumps(dict(type="req", reqid=reqid, pkgid=pkgid, total=size, size=pe-pb)).encode('utf-8'))
                await asyncio.wait_for(ack, None)
                # print(f"[POSTM] pkgid={pkgid} ack")
            except Exception:
                traceback.print_exc()
            finally:
                del self.acks[pkgid]
            pb = pe

    async def request(self, data: bytes, timeout=None):
        reqid = str(uuid.uuid4()).replace("-", "")
        future = asyncio.Future()
        self.futures[reqid] = future
        await self.post_packet(data, reqid)
        r = await asyncio.wait_for(future, timeout=timeout)
        del self.futures[reqid]
        return r


async def run():
    while True:
        r = win32gui.PeekMessage(None, 0, 0, win32con.PM_REMOVE)
        code, msg = r
        if code == 0:
            await asyncio.sleep(0.005)
            continue
        if msg[1] == win32con.WM_QUIT:
            exit(0)
        win32gui.TranslateMessage(msg)
        win32gui.DispatchMessage(msg)


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
    pythoncom.OleInitialize()
    if args.cache is not None:
        os.environ["WEBVIEW2_USER_DATA_FOLDER"] = args.cache
    if args.size is not None and 'x' in args.size.lower():
        size = [int(item) for item in args.size.lower().split('x')]
        width, height = size[0], size[1]
        dll.set_size(width, height)
    if args.title is not None:
        dll.set_title(args.title.encode(encoding='utf-8'))
    if args.icon is not None:
        dll.set_icon(args.icon.encode(encoding='utf-8'))
    if args.icon is not None:
        dll.set_navigation(args.url.encode(encoding='utf-8'))
    dll.set_memory(1024*1024*10)
    packer = Packer()
    packer.set_memo(1024*1024*10)
    import pathlib
    packer.scopes["readfile"] = lambda p: pathlib.Path(p).read_bytes()
    packer.scopes["readText"] = lambda p: pathlib.Path(p).read_text(encoding='utf-8')
    def close():
        hwnd = dll.get_window()
        win32gui.SendMessage(hwnd, win32con.WM_CLOSE, 0, 0)
    def maximize():
        hwnd = dll.get_window()
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
    def minimize():
        hwnd = dll.get_window()
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
    def restore():
        hwnd = dll.get_window()
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

    packer.scopes["close"] = close
    packer.scopes["maximize"] = maximize
    packer.scopes["minimize"] = minimize
    packer.scopes["restore"] = restore

    dll.build()
    # win32gui.PumpMessages()
    asyncio.run(run())
    close()
    return 0
