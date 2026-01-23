import json
import sys
import socket
import argparse


def get_commandline():
    parser = argparse.ArgumentParser(description="KEYENCE DL-EN1 Client")
    parser.add_argument('-i', '--ip', type=str, default="127.0.0.1",
                        help='server ip address')
    parser.add_argument('-p', '--port', type=int, default=8000,
                        required=False, help='server port')
    parser.add_argument('-t', '--timeout', type=int, default=3,
                        required=False, help='tcp timeout (in seconds)')
    parser.add_argument('-s', '--size', type=int, default=1024,
                        required=False, help='buffer size')
    parser.add_argument('-c', '--command', type=str,
                        required=True, help='eg: M0 MS SR SW FR')
    return parser.parse_args(sys.argv[1:])


if __name__ == '__main__':
    args = get_commandline()
    data = {"device": "KEYENCE DL-EN1 Client", "ip": args.ip, "port": args.port}
    try:
        cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cli.connect((args.ip, args.port))
        cli.send(args.command.encode('utf-8'))
        ret = cli.recv(args.size).decode(encoding='utf-8')
        data.update({"command": args.command, "response": ret})
        cli.close()
    except Exception as e:
        data.update({"error": str(e)})
    print(json.dumps(data, indent=2, ensure_ascii=False))
