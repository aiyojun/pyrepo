import argparse
import json
import re
import sys

from pymcprotocol import Type3E as McClient
from databyte import transform_read, transform_write, datasize
from devcmd import execute

__endian_lib__ = '<h'


def __endian_store__(f: str):
    # '<' represents little-endian read,
    # '>' represents    big-endian read.
    return f'<{f}'


def write(client: McClient, device: str, value, **kwargs):
    if re.match(r"[BMSXY][0-9]+", device):
        client.batchwrite_bitunits(device, [1 if value else 0])
    else:
        client.batchwrite_wordunits(device, transform_write(__endian_store__, __endian_lib__, value, **kwargs))


def read(client: McClient, device: str, **kwargs):
    if re.match(r"[BMSXY][0-9]+", device):
        return True if client.batchread_bitunits(device, 1)[0] else False
    return transform_read(__endian_store__, __endian_lib__, client.batchread_wordunits(
        device, datasize(kwargs.get('datatype', 'short'), kwargs.get('length', 1))), **kwargs)


def get_commandline():
    parser = argparse.ArgumentParser(description="Modbus TCP client")
    parser.add_argument('commands', nargs='+', help='commands')
    parser.add_argument('-i', '--ip', type=str, default="127.0.0.1", help='server ip address')
    parser.add_argument('-p', '--port', type=int, default=502,
                        required=False, help='server port')
    parser.add_argument('-s', '--series', type=str, default="L", choices=['L', 'Q', 'QnA', 'iQ-L', 'iQ-R'],
                        required=False, help='plc series, eg L, Q, QnA, iQ-L, iQ-R')
    parser.add_argument('-f', '--frame', type=str, default="binary", choices=['binary', 'ascii'],
                        required=False, help='frame format of communication protocol')
    return parser.parse_args(sys.argv[1:])


if __name__ == '__main__':
    args = get_commandline()
    cli = McClient(plctype=args.series)
    cli.setaccessopt(commtype=args.frame)
    cli.connect(args.ip, args.port)

    class XD(dict):
        def __getattr__(self, key):
            return self[key]

    plc = XD(read=read, write=write)
    print(json.dumps({
        "protocol": "mc", "ip": args.ip, "port": args.port, "frame": args.frame, "series": args.series,
        "tasks": [execute(cmd, cli, plc) for cmd in args.commands]
    }, indent=2, sort_keys=True, ensure_ascii=False))
    cli.close()
