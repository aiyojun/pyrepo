import json
import re
import sys
import time
import argparse
import functools
import traceback
import pymcprotocol
from kafka import KafkaProducer
from pymodbus.client import ModbusTcpClient

__global_settings = {
    "plc_ip": "172.16.1.153",
    "plc_port": 8100,
    "plc_type": "L",
    "memory": [],
    "kafka_host": "172.16.1.121:9092",
    "kafka_topic": "xxx-plc",
    "read_interval": 1.0,  # seconds
    "conn_interval": 3.0,
}


def parse_memory(mm: str):
    if not re.match(r"^([A-Z*])?[0-9]+(L[0-9]+)?(B[0-9]+)?(X[0-9]+)?$", mm):
        raise Exception("Invalid memory format")

    def get_default(s: str, r: str, d: str):
        x = re.search(r, s)
        return x[0] if type(x) is re.Match else d

    return {"type": get_default(mm, r"[A-Z]+", "D"),
            "addr": int(get_default(mm, r"[0-9]+", "1")),
            "size": int(get_default(mm, r"L[0-9]+", "L1")[1:]),
            "bits": int(get_default(mm, r"B[0-9]+", "B0")[1:]),
            "comp": int(get_default(mm, r"X[0-9]+", "X16")[1:]),
            }


def arg_help():
    argv = sys.argv
    # print(argv)
    parser = argparse.ArgumentParser(usage="{} [options] memory".format(argv[0]),
                                     description="PLC(mc protocol) data acquisition, then send to kafka")
    parser.add_argument('-I', '--plc_ip', required=True, help='PLC ip')
    parser.add_argument('-P', '--plc_port', required=True, help='PLC port')
    parser.add_argument('-T', '--plc_type', help='PLC type')
    parser.add_argument('-H', '--kafka_host', help='Kafka host')
    parser.add_argument('-t', '--kafka_topic', help='Kafka topic')
    parser.add_argument('-R', '--reconnect_interval', required=True, help='Reconnect interval in seconds')
    parser.add_argument('-i', '--interval', required=True, help='Read interval in seconds')
    parser.add_argument("memory", nargs="+", help="PLC address; eg: D200L10B16 D30 M4 B2")
    args = parser.parse_args()
    global __global_settings
    __global_settings = {
        "plc_ip": args.plc_ip,
        "plc_port": int(args.plc_port),
        "plc_type": args.plc_type or "L",
        "kafka_host": args.kafka_host,
        "kafka_topic": args.kafka_topic,
        "read_interval": float(args.interval),  # seconds
        "conn_interval": float(args.reconnect_interval),
        "memory": [parse_memory(arg) for arg in args.memory]
    }
    return


class MCDevice:
    def __init__(self, ip: str, port: int, plc_type: str = "L", conn_interval: float = 1.0):
        self.isConnected = False
        self.conn_interval = conn_interval
        self.plc_type = plc_type
        self.ip = ip
        self.port = port
        self.cli = None
        self.mb = None
        self.connect()
        self.isConnected = True

    def pull(self, begin: str, length: int):
        try:
            if self.plc_type == "modbus":
                if re.match(r"^[BMSXY][0-9]+", begin):
                    return self.mb.read_coils(int(begin[1:]), length)
                elif re.match(r"[DR][0-9]+", begin):
                    return self.mb.read_holding_registers(int(begin[1:]), length)
                else:
                    print("modbus device address error :", begin)
                    return None
            else:
                if re.match(r"^[BMSXY][0-9]+(.)*", begin):
                    return self.cli.batchread_bitunits(headdevice=begin, readsize=length)
                else:
                    return self.cli.batchread_wordunits(headdevice=begin, readsize=length)
        except Exception as e:
            print(e)
            traceback.print_stack()
            time.sleep(self.conn_interval)
            self.isConnected = False
            return None

    def connect(self):
        print("connect to : " + self.ip + ":" + str(self.port))
        if self.plc_type == "modbus":
            self.mb = ModbusTcpClient(self.ip, self.port)
        else:
            self.cli = pymcprotocol.Type3E(plctype=self.plc_type)
            self.cli.connect(self.ip, self.port)
        print("connect to : " + self.ip + ":" + str(self.port) + " success")


class PostProcessor:
    def process(self, d: dict):
        raise NotImplementedError


class MCDeviceTask:
    def __init__(self, mc_ip: str, mc_port: int, mc_type: str,
                 mc_memory: list,
                 mc_interval: float,
                 conn_interval: float,
                 postprocessor: PostProcessor = None):
        self.conn = MCDevice(mc_ip, mc_port, mc_type, conn_interval)
        self.memory = mc_memory
        self.interval = mc_interval
        self.conn_interval = conn_interval
        self.postprocessor = postprocessor
        self.isRunning = False

    def stop(self):
        self.isRunning = False

    def grab(self, res: dict, target: dict):
        device_type: str = target["type"]
        device_addr: int = target["addr"]
        device_size: int = target["size"]
        device_bits: int = target["bits"]
        device_comp: int = target["comp"]
        data = self.conn.pull(device_type + str(device_addr), device_size)
        if data is None:
            return
        if device_bits == 0:
            i = 0
            if device_comp == 32 and len(data) % 2 == 1:
                data.append(0)
            while i < len(data):
                res[device_type + str(device_addr + i)] = data[i] | (data[i + 1] << 16) if device_comp == 32 else data[i]
                i += 2 if device_comp == 32 else 1
        else:
            for i in range(len(data)):
                separate_bit(res, data[i], device_addr, i, device_type, device_bits)

    def start(self):
        self.isRunning = True
        count = 0
        while self.isRunning:
            try:
                if not self.conn.isConnected:
                    self.conn.connect()
                    continue
                rdata = {"time": int(time.time() * 1000), "machine": self.conn.ip + ":" + str(self.conn.port)}
                for mm in self.memory:
                    self.grab(rdata, mm)
                if self.postprocessor is not None:
                    if count < 10:
                        print(json.dumps(rdata))
                        count += 1
                    self.postprocessor.process(rdata)
                time.sleep(self.interval)
                # print(json.dumps(rdata))
            except Exception as e:
                print(e)
                # impossible branch
                traceback.print_stack()
        pass


class KafkaProducerSession(PostProcessor):
    def __init__(self, host: str, topic: str):
        self.topic = topic
        self.producer = KafkaProducer(bootstrap_servers=host, value_serializer=lambda m: json.dumps(m).encode())

    def process(self, d: dict):
        try:
            self.producer.send(self.topic, d)
        except Exception:
            traceback.print_stack()


def separate_bit(pool: dict, x: int, begin: int, offset: int, device_type: str = "D", radix: int = 16):
    for i in range(radix):
        pool["{}{}.{}".format(device_type, begin + offset, hex(i)[-1].upper())] = x >> i & 0x01


def main():
    plc = MCDeviceTask(__global_settings["plc_ip"],
                       __global_settings["plc_port"],
                       __global_settings["plc_type"],
                       __global_settings["memory"],
                       __global_settings["read_interval"],
                       __global_settings["conn_interval"],
                       KafkaProducerSession(__global_settings["kafka_host"], __global_settings["kafka_topic"])\
                           if __global_settings["kafka_host"] is not None\
                               and __global_settings["kafka_topic"] is not None else None)
    plc.start()


if __name__ == '__main__':
    arg_help()
    print(__global_settings)
    main()
