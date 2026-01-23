import json
import sys
import argparse
from pymodbus.client import ModbusTcpClient
from pymodbus.framer import Framer
from devcmd import execute
import modbus as plc


def get_commandline():
    parser = argparse.ArgumentParser(description="Modbus TCP client")
    parser.add_argument('commands', nargs='+', help='commands')
    parser.add_argument('-i', '--ip', type=str, default="127.0.0.1", help='modbus server ip address')
    parser.add_argument('-p', '--port', type=int, default=502, required=False, help='modbus server port')
    parser.add_argument('-f', '--frame', type=str, default="binary", choices=['binary', 'ascii'], required=False,
                        help='frame format of communication protocol')
    return parser.parse_args(sys.argv[1:])


if __name__ == '__main__':
    args = get_commandline()
    cli = ModbusTcpClient(args.ip, args.port, framer=Framer.ASCII if args.frame == 'ascii' else Framer.BINARY)
    cli.connect()
    print(json.dumps({
        "protocol": "modbus", "ip": args.ip, "port": args.port, "frame": args.frame,
        "tasks": [execute(cmd, cli, plc) for cmd in args.commands]},
                     indent=2, sort_keys=True, ensure_ascii=False))
    cli.close()
