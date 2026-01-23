import asyncio
import logging
import time
import traceback
import uuid
from typing import Optional, Callable, Awaitable, List, Dict

from numpy.f2py.rules import options

import voxe


async def invoke(method, *args, **kwargs):
    if not callable(method):
        return None
    if asyncio.iscoroutinefunction(method):
        return await method(*args, **kwargs)
    return method(*args, **kwargs)


class Packet:
    protocol: str
    topic: str
    call_id: str
    method: str
    status: int
    error: str
    offset: int = 0

    def __init__(self, payload: bytes):
        items = list(voxe.loads(payload))
        self.protocol = items[0]
        if self.protocol == "__message__":
            self.topic = items[1]
            self.offset = 2
        elif self.protocol == "__call__":
            self.call_id = items[1]
            self.method = items[2]
            self.offset = 3
        elif self.protocol == "__return__":
            self.call_id = items[1]
            self.status = items[2]
            if self.status != 0:
                self.error = items[3]
                self.offset = 4
            else:
                self.offset = 3
        self.items = items

    def remains(self) -> List[any]:
        return self.items[self.offset:]

    def __str__(self):
        ss = ""
        if self.protocol == "__message__":
            ss = f"__message__ {self.topic}"
        elif self.protocol == "__call__":
            ss = f"__call__ {self.method} {self.call_id}"
        elif self.protocol == "__return__":
            ss = f"__call__ {self.call_id}"
        return ss


async def write(writer: asyncio.StreamWriter, data: bytes):
    writer.write(len(data).to_bytes(8) + data)
    await writer.drain()


class Duplex:
    scopes: Dict[str, Callable] = {}
    futures: Dict[str, asyncio.Future[Packet]] = {}
    request_timeout: float = 3.0

    def __init__(self, request_timeout: float = 3.0, chunk_max_len: int = 1024 * 1024 * 4):
        self.request_timeout = request_timeout
        self._max_len = chunk_max_len

    # --- 通信层同步请求和异步消息实现 ---

    # 用于监听异步消息
    on_message: Optional[Callable[[asyncio.StreamWriter, str, bytes], (Awaitable[None] | None)]] = None

    async def publish(self, writer: asyncio.StreamWriter, topic: str, payload: bytes):
        """ 用于发布异步消息 """
        await write(writer, voxe.dumps("__message__", topic, payload))

    async def _on_listen(self, writer: asyncio.StreamWriter, payload: bytes):
        packet = Packet(payload)
        if packet.protocol == "__message__":
            await invoke(self.on_message, writer, packet.topic, packet.remains()[0])
            return
        elif packet.protocol == "__call__":
            if packet.method in self.scopes:
                try:
                    t0 = int(time.time() * 1000)
                    r = await invoke(self.scopes[packet.method], *packet.remains())
                    logging.info(f"distro::scopes::{packet.method} {int(time.time() * 1000) - t0}ms")
                    await write(writer, voxe.dumps("__return__", packet.call_id, 0, r))
                except Exception as e:
                    traceback.print_exc()
                    await write(writer, voxe.dumps("__return__", packet.call_id, 1, e))
            else:
                await write(writer, voxe.dumps("__return__", packet.call_id, 1, f"No such method : {packet.method}"))
        elif packet.protocol == "__return__":
            self.futures[packet.call_id].set_result(packet)
            pass
        pass

    async def request(self, writer: asyncio.StreamWriter, method: str, args: List[any]) -> any:
        """ 用于同步请求 """
        call_id = str(uuid.uuid4()).replace("-", "")
        future: asyncio.Future[Packet] = asyncio.get_event_loop().create_future()
        self.futures[call_id] = future
        try:
            await write(writer, voxe.dumps("__call__", call_id, method, *args))
            packet = await asyncio.wait_for(future, self.request_timeout)
            if packet.status != 0:
                raise Exception(packet.error)
            ret = packet.remains()
            return ret[0] if len(ret) == 1 else ret
        finally:
            del self.futures[call_id]

    # --- 传输层协议实现 ---

    # 存储连接对象的容器
    sessions: set[asyncio.StreamWriter] = set()

    _on_recv: Optional[Callable[[asyncio.StreamWriter, bytes], (Awaitable[None] | None)]] = None

    _server: Optional[asyncio.Server] = None

    _client_task = None

    async def _dialogue(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.sessions.add(writer)
        addr = writer.get_extra_info("peername")
        logging.debug(f"connected: {addr}")
        # import socket
        # sock = writer.get_extra_info("socket")
        # sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        # sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, self._max_len)
        # sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self._max_len)
        async def _recv(_payload: bytes):
            if callable(self._on_recv):
                try:
                    if asyncio.iscoroutinefunction(self._on_recv):
                        await self._on_recv(writer, _payload)
                    else:
                        self._on_recv(writer, _payload)
                except Exception as e:
                    traceback.print_exc()
                    logging.error(e)

        try:
            header_len, max_len = 8, self._max_len
            size = -1
            header_buf, payload_buf = bytearray(header_len), None
            header_ptr, payload_ptr = 0, 0
            while True:
                buffer: bytes = await reader.read(max_len)
                if not buffer:
                    break
                buffer_len, buffer_ptr = len(buffer), 0
                if header_ptr < header_len:
                    if header_ptr + buffer_len < header_len:
                        header_buf[header_ptr:header_ptr+buffer_len] = buffer
                        header_ptr += buffer_len
                        continue
                    else:
                        buffer_ptr = header_len - header_ptr
                        header_buf[header_ptr:header_len] = buffer[:buffer_ptr]
                        header_ptr = header_len
                        size = int.from_bytes(header_buf)
                        payload_ptr, payload_buf = 0, bytearray(size)
                while buffer_ptr < buffer_len:
                    buffer_rem = buffer_len - buffer_ptr
                    if payload_ptr + buffer_rem < size:
                        payload_buf[payload_ptr:payload_ptr+buffer_rem] = buffer[buffer_ptr:]
                        payload_ptr += buffer_rem
                        break
                    payload_exp = size - payload_ptr
                    payload_buf[payload_ptr:size] = buffer[buffer_ptr:buffer_ptr+payload_exp]
                    buffer_ptr += payload_exp
                    await _recv(bytes(payload_buf))
                    size, payload_buf = -1, None
                    header_ptr, payload_ptr = 0, 0
                    buffer_rem = buffer_len - buffer_ptr
                    if buffer_rem < header_len:
                        header_buf[:buffer_rem] = buffer[buffer_ptr:]
                        header_ptr = buffer_rem
                        break
                    header_buf[:header_len] = buffer[buffer_ptr:buffer_ptr+header_len]
                    header_ptr = header_len
                    buffer_ptr += header_len
                    size = int.from_bytes(header_buf)
                    payload_ptr, payload_buf = 0, bytearray(size)
        except asyncio.CancelledError:
            pass
        finally:
            self.sessions.remove(writer)
            logging.debug(f"disconnected: {addr}")
            writer.close()
            await writer.wait_closed()

    # --- 启动API ---

    def close(self):
        if self._server is not None:
            self._server.close()
            self._server = None
        else:
            list(self.sessions)[0].close()
            self._client_task = None

    async def run_as_server(self, port=8888) -> asyncio.Server:
        """
        Duplex作为服务端运行，等待外部连接；
        连接后的会话存入sessions；
        后续通过sessions来发送业务数据。
        """
        self._on_recv = self._on_listen
        server = await asyncio.start_server(self._dialogue, host="0.0.0.0", port=port)
        self._server = server
        addr = server.sockets[0].getsockname()
        logging.info(f"server listening on {addr}")
        await server.start_serving()
        return server

    async def run_as_client(self, host: str = "127.0.0.1", port: int = 8888, reconnect_interval: float = 3.0) -> asyncio.StreamWriter:
        """
        Duplex作为客户端运行，主动连接服务端；
        连接后的服务节点将存入sessions，sessions中有且仅有一个服务端；
        后续通过sessions来发送业务数据。
        """
        opened = asyncio.Event()
        self._client_task = asyncio.create_task(self._run_client(opened, host, port, reconnect_interval))
        async with asyncio.timeout(1.0):
            await opened.wait()
        return list(self.sessions)[0]

    async def _run_client(self, opened, host, port, reconnect_interval):
        while True:
            try:
                reader, writer = await asyncio.open_connection(host, port)
                if opened is not None:
                    opened.set()
                self._on_recv = self._on_listen
                await self._dialogue(reader, writer)
                return
            except Exception:
                traceback.print_exc()
                await asyncio.sleep(reconnect_interval)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s:%(name)s:%(levelname)s : %(message)s')
    import argparse
    import sys
    import pathlib

    def parse_arg(argv):
        parser = argparse.ArgumentParser(description="")
        parser.add_argument("--mode", help="工作模式。", type=str, default="server", choices=("server", "client"))
        parser.add_argument("--port", help="服务端口号", type=int, default=9999)
        parser.add_argument("--host", help="服务IP", type=str, default="127.0.0.1")
        parser.add_argument("--path", help="静态资源路径，用于读取相对路径的文件。", type=str, default=".")
        parser.add_argument("files", nargs="*")
        return parser.parse_args(argv)

    args = parse_arg(sys.argv[1:])

    async def cost(duplex, session, method, args):
        t0 = int(time.time() * 1000)
        r = await duplex.request(session, method, args)
        logging.info(f"distro::request::{method} {int(time.time() * 1000) - t0}ms")
        return r

    def read_file(path):
        path = pathlib.Path(path)
        if path.is_absolute():
            return path.read_bytes()
        else:
            return (pathlib.Path(args.path) / path).read_bytes()

    async def run_server():
        duplex = Duplex()
        duplex.scopes["readfile"] = read_file
        srv = await duplex.run_as_server(port=args.port)
        await srv.wait_closed()

    async def run_client():
        duplex = Duplex()
        cli = await duplex.run_as_client(host=args.host, port=args.port)
        srv = list(duplex.sessions)[0]
        files = args.files
        for file in files:
            data = await cost(duplex, srv, "readfile", [file])
            # binaries = await cost(duplex, srv, "readfile", [file])
            with open(file, 'wb+') as fp:
                fp.write(data)
        cli.close()
        await cli.wait_closed()

    if args.mode == "server":
        asyncio.run(run_server())
    else:
        asyncio.run(run_client())
