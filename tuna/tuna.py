import copy
import math
import re
import struct
import threading

from pymcprotocol import Type3E, Type4E
from pymodbus import Framer
from pymodbus.client import ModbusTcpClient
from pymodbus.pdu import ModbusResponse


def datasize(_datatype: str):
    dtm = {'short': 1, 'int': 2, 'integer': 2, 'float': 2, 'long': 4, 'double': 4}
    if _datatype in dtm:
        return dtm[_datatype]
    else:
        raise Exception(f'unknown datatype : {_datatype}')


def transform_read(__endian_store__, __endian_lib__, buf: list[int], datatype: str = 'short', size=1):
    if datatype == 'string':
        return b''.join([struct.pack(__endian_lib__, e) for e in buf[0:math.ceil(size / 2)]]).decode()[0:size]
    if datatype == 'short':
        f, s = 'h', 1
    elif datatype == 'int' or datatype == 'integer':
        f, s = 'i', 2
    elif datatype == 'long':
        f, s = 'q', 4
    elif datatype == 'float':
        f, s = 'f', 2
    elif datatype == 'double':
        f, s = 'd', 4
    else:
        raise Exception(f'invalid datatype, datatype : {datatype}')
    _r = list(map(lambda _i: struct.unpack(__endian_store__(f), b''.join(
        struct.pack(__endian_lib__, e) for e in buf[s * _i:s * (_i + 1)]))[0], range(size)))
    return _r if len(_r) > 1 else _r[0]


def transform_write(__endian_store__, __endian_lib__, value: any, datatype=None):
    buf: list[int] = []
    if value is None or (type(value) is list and len(value) == 0):
        return buf
    value_type = type(value) if type(value) is not list else type(value[0])
    if value_type is str:
        bt = value.encode()
        bt = bt + (b'\x00' if len(bt) % 2 == 1 else b'')
        for _i in range(int(len(bt) / 2)):
            buf.append(struct.unpack(__endian_lib__, bt[_i * 2:_i * 2 + 2])[0])
        return buf
    elif value_type is int and (datatype is None or datatype == 'short'):
        f, s = 'h', 1
    elif value_type is int and datatype == 'int':
        f, s = 'i', 2
    elif value_type is int and datatype == 'long':
        f, s = 'q', 4
    elif (value_type is float or int) and (datatype is None or datatype == 'float'):
        f, s = 'f', 2
    elif (value_type is float or int) and datatype == 'double':
        f, s = 'd', 4
    else:
        raise Exception(f'invalid datatype, value : {value}')

    def _each(v):
        m = struct.pack(__endian_store__(f), v)
        for _i in range(s):
            buf.append(struct.unpack(__endian_lib__, m[_i * 2:_i * 2 + 2])[0])

    if type(value) is list:
        for _i in value:
            _each(_i)
    else:
        _each(value)

    return buf


class Buffer:
    def __init__(self, buf: list[int] | None = None, offset=None,
                 endian_store=lambda f: f'<{f}', endian_lib=f'<H'):
        self.memory = [] if buf is None else buf
        self.endian_store = endian_store
        self.endian_lib = endian_lib
        self.address_type = None
        self.address_num = None
        self.set_offset(offset)

    def clear(self):
        self.memory.clear()
        return self

    def get_bytearray(self):
        return self.memory

    def set_offset(self, offset):
        if offset is None:
            self.address_type, self.address_num = None, None
        else:
            r = re.search(r'[0-9]+', offset)
            self.address_type = offset[0:r.start()]
            self.address_num = int(offset[r.start():])

    def append(self, data, datatype: str | None = None):
        if datatype == 'short':
            return self._append_short(data)
        elif datatype == 'int':
            return self._append_int(data)
        elif datatype == 'float':
            return self._append_float(data)
        elif datatype == 'long':
            return self._append_long(data)
        elif datatype == 'double':
            return self._append_double(data)
        elif type(data) is str:
            return self._append_string(data)
        else:
            raise Exception(f'invalid datatype {datatype}')

    def read(self, device: str, datatype: str, length=None):
        if not device.startswith(self.address_type):
            raise Exception(f'invalid address type {device}, expected "{self.address_type}-"')
        i = int(device[len(self.address_type):]) - self.address_num
        if datatype == 'short':
            return self._get_short(i)
        elif datatype == 'int':
            return self._get_int(i)
        elif datatype == 'float':
            return self._get_float(i)
        elif datatype == 'long':
            return self._get_long(i)
        elif datatype == 'double':
            return self._get_double(i)
        elif datatype == 'string':
            return self._get_string(i, length)
        else:
            raise Exception(f'invalid datatype {datatype}')

    def _append_short(self, data: int):
        self.memory = [*self.memory, *transform_write(self.endian_store, self.endian_lib, data, 'short')]
        return self

    def _append_int(self, data: int):
        self.memory = [*self.memory, *transform_write(self.endian_store, self.endian_lib, data, 'int')]
        return self

    def _append_long(self, data: int):
        self.memory = [*self.memory, *transform_write(self.endian_store, self.endian_lib, data, 'long')]
        return self

    def _append_float(self, data: float):
        self.memory = [*self.memory, *transform_write(self.endian_store, self.endian_lib, data, 'float')]
        return self

    def _append_double(self, data: float):
        self.memory = [*self.memory, *transform_write(self.endian_store, self.endian_lib, data, 'double')]
        return self

    def _append_string(self, data: str):
        self.memory = [*self.memory, *transform_write(self.endian_store, self.endian_lib, data)]
        return self

    def _get_short(self, i: int):
        return transform_read(self.endian_store, self.endian_lib, self.memory[i:], datatype='short')

    def _get_int(self, i: int):
        return transform_read(self.endian_store, self.endian_lib, self.memory[i:], datatype='int')

    def _get_float(self, i: int):
        return transform_read(self.endian_store, self.endian_lib, self.memory[i:], datatype='float')

    def _get_double(self, i: int):
        return transform_read(self.endian_store, self.endian_lib, self.memory[i:], datatype='double')

    def _get_long(self, i: int):
        return transform_read(self.endian_store, self.endian_lib, self.memory[i:], datatype='long')

    def _get_string(self, i: int, length: int):
        return transform_read(self.endian_store, self.endian_lib, self.memory[i:], datatype='string', size=length)


class Adaptor:
    def valid(self, protocol: str) -> bool:
        raise NotImplementedError

    def build(self, host: str, port: int, params: dict):
        raise NotImplementedError

    def read(self, device: str, datatype: str | None, length: int):
        raise NotImplementedError

    def write(self, device: str, datatype: str | None, data: any):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError


class McAdaptor(Adaptor):
    def __init__(self):
        self.host = '127.0.0.1'
        self.port = 502
        self.plc_type = 'L'
        self.cli = None
        self.endian_store = lambda f: f'<{f}'
        self.endian_lib = '<h'
        self.mc_type = '3e'

    def valid(self, protocol: str) -> bool:
        if protocol == 'mc_3e':
            self.mc_type = '3e'
        elif protocol == 'mc_4e':
            self.mc_type = '4e'
        else:
            return False
        return True

    def build(self, host: str, port: int, params: dict):
        conn = copy.deepcopy(self)
        conn.plc_type = params.get('series', self.plc_type)
        conn.cli = Type3E(conn.plc_type) if conn.mc_type == '3e' else Type4E(conn.plc_type)
        conn.cli.setaccessopt(commtype=params.get('commtype', 'binary'),
                              timer_sec=int(float(params.get('timeout', 5.0))))
        conn.cli.connect(host, port)
        return conn

    def close(self):
        if self.cli is not None:
            self.cli.close()

    def read(self, device: str, datatype: str | None, length: int):
        if re.match(r'[BMSXY][0-9]+', device):
            ret = list(map(lambda _x: True if _x else False, self.cli.batchread_bitunits(device, length)))
        elif re.match(r'D[0-9]+', device):
            if datatype is None:
                ret = self.cli.batchread_wordunits(device, length)
            else:
                size = length if datatype == 'string' else length * datasize(datatype)
                ret = transform_read(
                    self.endian_store, self.endian_lib,
                    self.cli.batchread_wordunits(device, size),
                    datatype=datatype, size=length
                )
        else:
            raise Exception(f'unknown address position : {device}')
        return ret if datatype is not None else Buffer(
            ret, offset=device, endian_store=self.endian_store, endian_lib=self.endian_lib)

    def write(self, device: str, datatype: str | None, data: any):
        if re.match(r'[BMSXY][0-9]+', device):
            if type(data) is not list:
                data = [1 if data else 0]
            self.cli.batchwrite_bitunits(device, list(map(lambda _x: 1 if _x else 0, data)))
        elif re.match(r'D[0-9]+', device):
            if type(data) is Buffer:
                self.cli.batchread_wordunits(device, data.get_bytearray())
                return
            self.cli.batchwrite_wordunits(
                device, transform_write(self.endian_store, self.endian_lib, data, datatype=datatype),
            )
        else:
            raise Exception(f'unknown address position : {device}')


def _error_filter(resp: ModbusResponse):
    if resp.isError():
        raise Exception(f'modbus error, function code : {resp.function_code}')
    return resp


class ModbusAdaptor(Adaptor):
    def __init__(self):
        self.host = '127.0.0.1'
        self.port = 502
        self.framer = Framer.SOCKET
        self.timeout = 5.0
        self.cli = None
        self.offset_r = 0
        self.endian_store = lambda f: f'<{f}'
        self.endian_lib = '<H'
        self.slave = 0

    def valid(self, protocol: str) -> bool:
        if protocol == 'modbus' or protocol == 'modbus_tcp':
            self.framer = Framer.SOCKET
        elif protocol == 'modbus_rtu':
            self.framer = Framer.RTU
        elif protocol == 'modbus_binary':
            self.framer = Framer.BINARY
        elif protocol == 'modbus_ascii':
            self.framer = Framer.ASCII
        else:
            return False
        return True

    def build(self, host: str, port: int, params: dict):
        conn = copy.deepcopy(self)
        conn.host = host
        conn.port = port
        conn.slave = int(params.get('slave', conn.slave))
        conn.slave = int(params.get('station', conn.slave))
        conn.timeout = float(params.get('timeout', conn.timeout))
        if 'series' in params:
            if params.get('series') == 'H5U':
                conn.offset_r = 0x3000
        conn.cli = ModbusTcpClient(host=conn.host, port=conn.port, timeout=conn.timeout, framer=conn.framer)
        return conn

    def close(self):
        if self.cli is not None:
            self.cli.close()

    def read(self, device: str, datatype: str | None, length: int):
        if re.match(r'M[0-9]+', device):
            ret = list(map(lambda _x: True if _x else False,
                           _error_filter(self.cli.read_coils(int(device[1:]), count=length, slave=self.slave)).bits))
        elif re.match(r'[DR][0-9]+', device):
            addr = int(device[1:]) + (0 if device[0] == 'D' else self.offset_r)
            if datatype is None:
                ret = _error_filter(self.cli.read_holding_registers(
                    addr, count=length, slave=self.slave)).registers
            else:
                size = length if datatype == 'string' else length * datasize(datatype)
                ret = transform_read(
                    self.endian_store, self.endian_lib,
                    _error_filter(self.cli.read_holding_registers(addr, count=size, slave=self.slave)).registers,
                    datatype=datatype, size=length
                )
        else:
            raise Exception(f'unknown address position : {device}')
        return ret if datatype is not None else Buffer(
            ret, offset=device, endian_store=self.endian_store, endian_lib=self.endian_lib)

    def write(self, device: str, datatype: str | None, data: any):
        if re.match(r'M[0-9]+', device):
            self.cli.write_coils(int(device[1:]), data, slave=self.slave)
        elif re.match(r'D[0-9]+', device):
            if type(data) is Buffer:
                self.cli.write_registers(int(device[1:]), data.get_bytearray(), slave=self.slave)
                return
            self.cli.write_registers(
                int(device[1:]), transform_write(self.endian_store, self.endian_lib, data, datatype=datatype),
                slave=self.slave
            )
        elif re.match(r'R[0-9]+', device):
            if type(data) is Buffer:
                self.cli.write_registers(int(device[1:]) + self.offset_r, data.get_bytearray(), slave=self.slave)
                return
            self.cli.write_registers(
                int(device[1:]) + self.offset_r,
                transform_write(self.endian_store, self.endian_lib, data, datatype=datatype),
                slave=self.slave
            )
        else:
            raise Exception(f'unknown address position : {device}')


class Tuna:
    """ Tuna: 最新版本的PLC连接工具，当前支持一下几种PLC连接：
    1. 通用modbus tcp连接，连接url格式为："modbus://127.0.0.1:502?timeout=5"
    2. 通用modbus rtu连接，连接url格式为："modbus_rtu://127.0.0.1:502?timeout=5"
    3. 三菱mc 3e协议连接，连接url格式为："mc_3e://10.8.7.6:502?timeout=5&series=Q"
    4. 三菱mc 4e协议连接，连接url格式为："mc_4e://10.8.7.6:502?timeout=5&series=Q"
    品牌相关：
    1. 汇川H5U："modbus://127.0.0.1:502?timeout=5&series=H5U"
    2. 三菱L系列："mc_3e://10.8.7.6:502?timeout=5&series=L"
    """

    def __init__(self, url):
        pattern_ipv4 = r'(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)){3}'
        pattern_domain = r'[_a-zA-Z.]+'
        pattern_protocol = r'^[_a-zA-Z][_a-zA-Z0-9]*://'
        pattern_port = r'(:[0-9]+)?'
        pattern_query = r'(\?(&[_a-zA-Z][_a-zA-Z0-9]*=[_a-zA-Z0-9])+)?'
        if not re.match(f"{pattern_protocol}({pattern_ipv4}|{pattern_domain}){pattern_port}{pattern_query}", url):
            raise ValueError(f"Invalid url : {url}, format : protocol://host[:port][?query]")
        [head, rest] = url.split('://')
        self.protocol = head
        params = {}
        if rest.find('?') > -1:
            [head, rest] = rest.split('?')
            t = head.split(':')
            self.host = t[0]
            self.port = 502 if len(t) == 1 else int(t[1])
            for q in rest.split('&'):
                kv = q.split('=')
                params[kv[0]] = kv[1]
        self.params = params
        self.plugins = [McAdaptor(), ModbusAdaptor()]
        self.cli = None
        self.lock = threading.RLock()

    def connect(self):
        self.cli = self._build(self.protocol, self.host, self.port, self.params)
        return self

    def close(self):
        if self.cli is not None:
            self.cli.close()

    def __str__(self):
        return f'{self.protocol}://{self.host}:{self.port} {str(self.params)}'

    def _build(self, protocol: str, host: str, port: int, params: dict):
        for plugin in self.plugins:
            if plugin.valid(protocol):
                return plugin.build(host, port, params)
        raise ValueError(f"unknown protocol : {protocol}")

    def read(self, device: str, datatype: str | None, size: int = 1):
        with self.lock:
            return self.cli.read(device, datatype, size)

    def write(self, device: str, datatype: str | None, values):
        with self.lock:
            self.cli.write(device, datatype, values)


if __name__ == '__main__':
    # 用法总结：
    tuna = Tuna('modbus://10.1.16.210:502?timeout=5.0').connect()
    # tuna = Tuna('modbus://10.8.7.6:502?timeout=5.0&series=H5U').connect()
    # tuna = Tuna('mc_3e://172.16.1.153:8100?timeout=5.0&series=L').connect()
    print(tuna)
    # 单次写入各种类型的数据
    # tuna.write('R100', 'int', 87)
    # tuna.write('D100', 'int', 86)
    # tuna.write('D200', 'long', 50054)
    # tuna.write('D205', 'float', [23.23, 34.56])
    # tuna.write('D210', 'string', 'hello world!')
    print(tuna.read('D7000', 'int'))

    # print(tuna.read('R100', 'int'))
    # print(tuna.read('D100', 'int'))
    # print(tuna.read('D200', 'long'))
    # print(tuna.read('D205', 'float', 2))
    # print(tuna.read('D210', 'string', 12))
    # # 批量写入多种类型的数据
    # buffer = Buffer().append(89, 'int').append(12.23, 'float').append("hello world")
    # tuna.write('D500', None, buffer)
    # print(tuna.read('D500', 'int'))
    # print(tuna.read('D502', 'float'))
    # print(tuna.read('D504', 'string', 11))
    # # 批量读取多种类型的数据
    # buffer = tuna.read('D500', None, 20)
    # print(buffer.read('D500', datatype='int'))
    # print(buffer.read('D502', datatype='float'))
    # print(buffer.read('D504', datatype='string', length=11))
