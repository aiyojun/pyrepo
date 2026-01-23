import json
import struct


VER = b""
BOOL = b"\x00"
NONE = b"\x07"
INT = b"\x02"
FLOAT = b"\x03"
STR = b"\x06"
ERR = b"\x08"
BYTES = b"\x09"
JSON = b"\x0a"


def loads(data: bytes):
    if type(data) is not bytes:
        raise Exception("Not voxe protocol!")
    ret = []
    if len(data) < len(VER) or data[0:len(VER)] != VER:
        raise Exception("Not voxe protocol!")
    elif len(data) == len(VER):
        return None
    data = data[len(VER):]
    index = 0
    while index < len(data):
        pre = data[index + 1]
        if pre == BOOL[0]:
            ret.append(bool(data[index + 3]))
            index += 4
        elif pre == NONE[0]:
            ret.append(None)
            index += 3
        elif pre == INT[0]:
            ret.append(struct.unpack(">i", data[index + 3:index + 7])[0])
            index += 7
        elif pre == FLOAT[0]:
            ret.append(struct.unpack(">f", data[index + 3:index + 7])[0])
            index += 7
        elif pre == STR[0]:
            string_length = struct.unpack(">i", data[index + 3:index + 7])[0]
            ret.append(data[index + 8:index + 8 + string_length].decode(encoding="utf-8"))
            index += 8 + string_length
        elif pre == ERR[0]:
            string_length = struct.unpack(">i", data[index + 3:index + 7])[0]
            raise Exception(data[index + 8:index + 8 + string_length].decode(encoding="utf-8"))
        elif pre == BYTES[0]:
            string_length = struct.unpack(">i", data[index + 3:index + 7])[0]
            ret.append(data[index + 8:index + 8 + string_length])
            index += 8 + string_length
        elif pre == JSON[0]:
            string_length = struct.unpack(">i", data[index + 3:index + 7])[0]
            ret.append(json.loads(data[index + 8:index + 8 + string_length].decode(encoding="utf-8")))
            index += 8 + string_length
        else:
            raise Exception(f"Invalid voxe protocol byte: {pre} at {index + 1}")
    return tuple(ret)


def dumps(*args):
    ret = VER
    for arg in args:
        if arg is None:
            ret += b"\x00" + NONE + b"\x00"
        elif type(arg) is dict:
            data = json.dumps(arg).encode("utf-8")
            ret += b'\x00' + JSON + b'\x00' + struct.pack('>i', len(data)) + b'\x00' + data
        elif type(arg) is bytes:
            ret += b'\x00' + BYTES + b'\x00' + struct.pack('>i', len(arg)) + b'\x00' + arg
        elif type(arg) is str:
            data = arg.encode("utf-8")
            ret += b'\x00' + STR + b'\x00' + struct.pack('>i', len(data)) + b'\x00' + data
        elif isinstance(arg, Exception):
            data = str(arg).encode("utf-8")
            ret += b'\x00' + STR + b'\x00' + struct.pack('>i', len(data)) + b'\x00' + data
        elif type(arg) is int:
            ret += b'\x00' + INT + b'\x00' + struct.pack('>i', arg)
        elif type(arg) is float:
            ret += b'\x00' + FLOAT + b'\x00' + struct.pack('>f', arg)
        elif type(arg) is bool:
            ret += b'\x00' + BOOL + b'\x00' + struct.pack('>?', arg)
    return ret
