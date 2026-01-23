import sys
import argparse
from pymodbus.framer import Framer
from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusServerContext, ModbusSlaveContext


def get_commandline():
    parser = argparse.ArgumentParser(description="Modbus Server")
    parser.add_argument('-p', '--port', type=int, default=502, required=False, help='set modbus server port')
    return parser.parse_args(sys.argv[1:])


if __name__ == '__main__':
    args = get_commandline()
    StartTcpServer(
        context=ModbusServerContext(ModbusSlaveContext(), True),
        address=('0.0.0.0', args.port),
        framer=Framer.BINARY,
        ignore_missing_slaves=True, )
