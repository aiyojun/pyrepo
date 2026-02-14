import ctypes
import os

os.add_dll_directory(os.path.dirname(__file__))
dll = ctypes.CDLL("WebView2Window.dll")

listener = ctypes.CFUNCTYPE(None, ctypes.c_char_p)
set_title = dll.set_title
set_position = dll.set_position
set_size = dll.set_size
set_client = dll.set_client
set_navigation = dll.set_navigation
set_icon = dll.set_icon
set_listener = dll.set_listener
set_memory = dll.set_memory
get_window = dll.get_window
read = dll.read
write = dll.write
post = dll.post
build = dll.build
destroy = dll.destroy
preload = dll.preload
evaluate = dll.evaluate

set_title.argtypes = [ctypes.c_char_p]
set_title.restype = None
set_position.argtypes = [ctypes.c_int, ctypes.c_int]
set_position.restype = None
set_size.argtypes = [ctypes.c_int, ctypes.c_int]
set_size.restype = None
set_client.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
set_client.restype = None
set_navigation.argtypes = [ctypes.c_char_p]
set_navigation.restype = None
set_icon.argtypes = [ctypes.c_char_p]
set_icon.restype = None
set_listener.argtypes = [listener]
set_listener.restype = None
set_memory.argtypes = [ctypes.c_int]
set_memory.restype = None
get_window.argtypes = []
get_window.restype = ctypes.c_void_p
read.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_int]
read.restype = ctypes.c_int
write.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_int]
write.restype = ctypes.c_int
post.argtypes = [ctypes.c_char_p]
post.restype = None
build.argtypes = []
build.restype = None
destroy.argtypes = []
destroy.restype = None
preload.argtypes = [ctypes.c_char_p]
preload.restype = None
evaluate.argtypes = [ctypes.c_char_p, listener]
evaluate.restype = None
