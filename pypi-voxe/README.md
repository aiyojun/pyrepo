# Project description

Voxe is a kind of simple transport layer protocol.

## Usage

```python
import voxe

data = voxe.dumps(12, 'hello voxe', 3.14)
a, b, c = voxe.loads(data)
print(data)
print(a, b, c)
```
