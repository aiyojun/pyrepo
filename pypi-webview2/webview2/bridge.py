import asyncio
import ctypes
import functools
import json
import os
import pathlib
import re
import traceback
import typing
import uuid

import pythoncom
import voxe
import win32con
import win32gui

from .core import dll, listener

_dir_ = os.path.dirname(__file__)


class Transport:
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
        self.cb2 = listener(self.cb)
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
            self.cache[self.offset:self.offset + size] = self._read(size)
            dll.post(json.dumps(dict(type="ack", pkgid=self.pkgid, reqid=self.reqid)).encode(encoding='utf-8'))
            self.offset += size
            if self.offset >= self.total:
                try:
                    ctx = voxe.loads(bytes(self.cache))
                    method_name, args = ctx[0], ctx[1:]
                    if type(self.scopes) is dict:
                        if method_name in self.scopes:
                            r = self.scopes[method_name](*args)
                            asyncio.create_task(self.send(voxe.dumps(0, r), self.reqid))
                        else:
                            asyncio.create_task(self.send(voxe.dumps(1, "no such method"), self.reqid))
                    else:
                        if method_name in dir(self.scopes):
                            method = getattr(self.scopes, method_name)
                            r = method(*args)
                            asyncio.create_task(self.send(voxe.dumps(0, r), self.reqid))
                        else:
                            asyncio.create_task(self.send(voxe.dumps(1, "no such method"), self.reqid))
                except Exception as e:
                    traceback.print_exc()
                    asyncio.create_task(self.send(voxe.dumps(1, str(e)), self.reqid))
                    pass
                if self.on_service:
                    self.on_service(self.cache)
            if self.offset >= self.total and self.reqid in self.futures:
                self.futures[self.reqid].set_result(self.cache)
                self.reqid = None
                self.cache = None
        except json.decoder.JSONDecodeError:
            pass
        except Exception as e:
            traceback.print_exc()

    async def send(self, data: bytes, reqid=None):
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
                dll.post(json.dumps(dict(type="req", reqid=reqid, pkgid=pkgid, total=size, size=pe-pb)).encode('utf-8'))
                await asyncio.wait_for(ack, None)
            except Exception:
                traceback.print_exc()
            finally:
                del self.acks[pkgid]
            pb = pe

    async def request(self, data: bytes, timeout=None):
        reqid = str(uuid.uuid4()).replace("-", "")
        future = asyncio.Future()
        self.futures[reqid] = future
        await self.send(data, reqid)
        r = await asyncio.wait_for(future, timeout=timeout)
        del self.futures[reqid]
        return r


def webview2_api(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    wrapper.__webview2_api__ = True
    return wrapper


class Window:
    def __init__(self, title=None, icon=None, url=None, size=None, cache=None, memory_size=1024*1024*10):
        if cache is not None:
            os.environ["WEBVIEW2_USER_DATA_FOLDER"] = cache
        if size is not None and 'x' in size.lower():
            size = [int(item) for item in size.lower().split('x')]
            width, height = size[0], size[1]
            dll.set_size(width, height)
        if title is not None:
            dll.set_title(title.encode(encoding='utf-8'))
        if icon is not None:
            dll.set_icon(icon.encode(encoding='utf-8'))
        if url is not None:
            dll.set_navigation(url.encode(encoding='utf-8'))
        if memory_size is not None:
            dll.set_memory(memory_size)
        transport = Transport()
        transport.scopes = self

    async def run(self):
        pythoncom.OleInitialize()
        dll.preload(self._build_context(os.path.join(_dir_, "webview2.js")).encode(encoding='utf-8'))
        dll.build()
        while True:
            r = win32gui.PeekMessage(None, 0, 0, win32con.PM_REMOVE)
            code, msg = r
            if code == 0:
                await asyncio.sleep(0.005)
                continue
            if msg[1] == win32con.WM_QUIT:
                break
            win32gui.TranslateMessage(msg)
            win32gui.DispatchMessage(msg)
        self.close()
        pythoncom.CoUninitialize()
        return 0

    def _build_context(self, script_path):
        script = pathlib.Path(script_path).read_text()
        methods = []
        for name in dir(self):
            if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", name):
                continue
            member = getattr(self, name)
            if not callable(member):
                continue
            func = member.__func__ if hasattr(member, "__func__") else member
            if not getattr(func, "__webview2_api__", False):
                continue
            methods.append(
                f"{name}:async(...args)=>await invoke(window.webview2.transport,window.webview2.voxe,'{name}', ...args)")
        ptr = script.rfind("}")
        script = (script[0:ptr]
                  + ";Object.defineProperty(window,'webview2',Object.freeze({value:{api:{"
                  + ",".join(methods)
                  + "},voxe:new Voxe(),transport:new Transport()},writable:false,configurable:false,enumerable:false}))"
                  + script[ptr:])
        return script

    @webview2_api
    def close(self):
        hwnd = dll.get_window()
        win32gui.SendMessage(hwnd, win32con.WM_CLOSE, 0, 0)

    @webview2_api
    def maximize(self):
        hwnd = dll.get_window()
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)

    @webview2_api
    def minimize(self):
        hwnd = dll.get_window()
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)

    @webview2_api
    def restore(self):
        hwnd = dll.get_window()
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
