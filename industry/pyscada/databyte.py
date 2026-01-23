import struct

"""
Note:
    pymodbus     is    big-endian descriptor
    pymcprotocol is little-endian descriptor
"""


def datasize(datatype: str, string_length: int = 1):
    if datatype == 'short' or datatype == 'bool':
        length = 1
    elif datatype == 'int' or datatype == 'float':
        length = 2
    elif datatype == 'long' or datatype == 'double':
        length = 4
    else:
        length = string_length
    return length


def transform_write(__endian_store__, __endian_lib__, value, **kwargs):
    buf: list[int] = []
    datatype = kwargs.get('datatype', None)
    if value is None:
        return buf
    value_type = type(value)
    if value_type is bool and (datatype is None or datatype == 'bool'):
        buf.append(1 if value else 0)
        return buf
    elif value_type is str and (datatype is None or datatype == 'str'):
        bt = value.encode()
        for i in range(int(len(bt) / 2)):
            buf.append(struct.unpack(__endian_lib__, bt[i * 2:i * 2 + 2])[0])
        return buf
    elif value_type is int and (datatype is None or datatype == 'short'):
        f, s = 'h', 1
    elif value_type is int and datatype == 'int':
        f, s = 'i', 2
    elif value_type is int and datatype == 'long':
        f, s = 'q', 4
    elif value_type is float and (datatype is None or datatype == 'float'):
        f, s = 'f', 2
    elif value_type is float and datatype == 'double':
        f, s = 'd', 4
    else:
        raise Exception(f'invalid datatype, value : {value}')
    m = struct.pack(__endian_store__(f), value)
    for i in range(s):
        buf.append(struct.unpack(__endian_lib__, m[i * 2:i * 2 + 2])[0])
    return buf


def transform_read(__endian_store__, __endian_lib__, buf: list[int], datatype: str = 'short', **kwargs):
    if datatype == 'bool':
        return True if buf[0] else False
    elif datatype == 'short':
        return struct.unpack(__endian_store__('h'), struct.pack(__endian_lib__, buf[0]))[0]
    elif datatype == 'int':
        f, s = 'i', 2
    elif datatype == 'long':
        f, s = 'q', 4
    elif datatype == 'float':
        f, s = 'f', 2
    elif datatype == 'double':
        f, s = 'd', 4
    elif datatype == 'str':
        size = kwargs.get('length', 1)
        return b''.join([struct.pack(__endian_lib__, e) for e in buf[0:int(size / 2)]]).decode()
    else:
        raise Exception(f'invalid datatype, datatype : {datatype}')
    return struct.unpack(__endian_store__(f), b''.join(
        struct.pack(__endian_lib__, e) for e in buf[0:s]))[0]
