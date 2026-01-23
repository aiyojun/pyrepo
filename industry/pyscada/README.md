# pyscada

## Build

> python -m venv venv

> venv/bin/pip install pymcprotocol==0.3.0 pymodbus==3.6.4

## Run

```shell
# mcprotocol, Write 23 to D200, then Read int in D200
venv/bin/python ./pyscada/mcprotocol.py -i 127.0.0.1 -p 8001 -s L D200@int D200@intW23
# modbus
venv/bin/python ./pyscada/modbus_tcp.py -i 127.0.0.1 -p 502 D200@int D200@intW23
```

