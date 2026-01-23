import re
from pymodbus.pdu import ModbusResponse
from pymodbus.client import ModbusTcpClient
from databyte import transform_read, transform_write, datasize

__endian_lib__ = '>H'


def __endian_store__(f: str):
    # '<' represents little-endian read,
    # '>' represents    big-endian read.
    return f'<{f}'


def _error_checking(resp: ModbusResponse):
    if resp.isError():
        raise Exception(resp.function_code)
    return resp


def write(client: ModbusTcpClient, device: str, value, **kwargs):
    if re.match(r"[BMSXY][0-9]+", device):
        client.write_coil(int(device[1:]), value)
    else:
        client.write_registers(int(device[1:]), transform_write(__endian_store__, __endian_lib__, value, **kwargs))


def read(client: ModbusTcpClient, device: str, **kwargs):
    if re.match(r"[BMSXY][0-9]+", device):
        return True if _error_checking(client.read_holding_registers(int(device[1:]))).bits[0] else False
    r = _error_checking(client.read_holding_registers(
        int(device[1:]), datasize(kwargs.get('datatype', 'short'), kwargs.get('length', 1)))).registers
    return transform_read(__endian_store__, __endian_lib__, r, **kwargs)
