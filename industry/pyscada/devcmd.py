import re


def get_default(reg: str, raw: str, default):
    r = re.search(reg, raw)
    return r.group(0) if r else default


def execute(cmd, cli, plc):
    _r = None
    try:
        device = re.match(r'^[MD][0-9]+', cmd)
        if not device:
            raise Exception(f"invalid device type {cmd}, only support M-/D-")
        device = device[0]
        _cmd = cmd[len(device):]
        if _cmd == '':
            _r = ({"command": cmd, "taskType": "read", "dataType": "short", "device": device,
                   "value": plc.read(cli, device, datatype='short')})
        elif re.match(r'^@bool(ean)?$', _cmd):
            _r = ({"command": cmd, "taskType": "read", "dataType": "bool", "device": device,
                   "value": plc.read(cli, device, datatype='bool')})
        elif re.match(r'^@short$', _cmd):
            _r = ({"command": cmd, "taskType": "read", "dataType": "short", "device": device,
                   "value": plc.read(cli, device, datatype='short')})
        elif re.match(r'^@int(eger)?$', _cmd):
            _r = ({"command": cmd, "taskType": "read", "dataType": "int", "device": device,
                   "value": plc.read(cli, device, datatype='int')})
        elif re.match(r'^@long$', _cmd):
            _r = ({"command": cmd, "taskType": "read", "dataType": "long", "device": device,
                   "value": plc.read(cli, device, datatype='long')})
        elif re.match(r'^@float$', _cmd):
            _r = ({"command": cmd, "taskType": "read", "dataType": "float", "device": device,
                   "value": plc.read(cli, device, datatype='float')})
        elif re.match(r'^@double$', _cmd):
            _r = ({"command": cmd, "taskType": "read", "dataType": "double", "device": device,
                   "value": plc.read(cli, device, datatype='double')})
        elif re.match(r'^@asciiL[0-9]+$', _cmd):
            size = int(get_default(r'L[0-9]+', _cmd, 'L1')[1:])
            _r = ({"command": cmd, "taskType": "read", "dataType": "string", "device": device, "length": size,
                   "value": plc.read(cli, device, datatype='str', length=size)})
        elif re.match(r'^(@short)?W[+-]?[0-9]+$', _cmd):
            x = int(get_default(r'W[+-]?[0-9]+', _cmd, 'W0')[1:])
            _r = ({"command": cmd, "taskType": "write", "dataType": "short", "device": device, "value": x})
            plc.write(cli, device, x, datatype='short')
        elif re.match(r'^@int(eger)?W[+-]?[0-9]+$', _cmd):
            x = int(get_default(r'W[+-]?[0-9]+', _cmd, 'W0')[1:])
            _r = ({"command": cmd, "taskType": "write", "dataType": "int", "device": device, "value": x})
            plc.write(cli, device, x, datatype='int')
        elif re.match(r'^@longW[+-]?[0-9]+$', _cmd):
            x = int(get_default(r'W[+-]?[0-9]+', _cmd, 'W0')[1:])
            _r = ({"command": cmd, "taskType": "write", "dataType": "long", "device": device, "value": x})
            plc.write(cli, device, x, datatype='long')
        elif re.match(r'^(@bool)?W(true|false)$', _cmd):
            x = get_default(r'W(true|false)', _cmd, 'Wfalse')[1:] == 'true'
            _r = ({"command": cmd, "taskType": "write", "dataType": "bool", "device": device, "value": x})
            plc.write(cli, device, x, datatype='bool')
        elif re.match(r'^(@float)?W[+-]?[0-9]+\.[0-9]+$', _cmd):
            x = float(get_default(r'W[+-]?[0-9]+\.[0-9]+', _cmd, 'W0')[1:])
            _r = ({"command": cmd, "taskType": "write", "dataType": "float", "device": device, "value": x})
            plc.write(cli, device, x, datatype='float')
        elif re.match(r'^@doubleW[+-]?[0-9]+\.[0-9]+$', _cmd):
            x = float(get_default(r'W[+-]?[0-9]+\.[0-9]+', _cmd, 'W0')[1:])
            _r = ({"command": cmd, "taskType": "write", "dataType": "double", "device": device, "value": x})
            plc.write(cli, device, x, datatype='double')
        elif re.match(r'^@asciiW.+$', _cmd):
            text = get_default(r'^@asciiW.+', _cmd, '@asciiW')[7:]
            _r = ({"command": cmd, "taskType": "write", "dataType": "string", "device": device, "value": text})
            plc.write(cli, device, text, datatype='str')
        else:
            raise Exception(f"invalid command: {_cmd}")
    except Exception as e:
        _r = ({"command": cmd, "error": str(e)})
    return _r
