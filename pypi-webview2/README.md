# webview2

Build immersive applications supported by WebView2 on Windows Operation Systems

## GUI Framework

Instead of WinForms and WPF, Use native Win32 directly.

The reason for choosing Win32 is that only the native API provides full control over window functionality, including achieving an immersive visual effect.

This project uses Win32 in a unique way: the core functionality is built with pywin32 to fully leverage Python’s capabilities.

For the WebView2 component, which exposes COM interfaces, we adopted a C++-wrapped DLL approach, supported by WebView2Window.

Because WebView2’s default rendering mode blocks interaction with the operating system, WebView2Window employs the Composition rendering mode.

In Composition mode, the WebView window achieves the same level of immersive styling as seen in applications like Visual Studio and JetBrains IDEs.

WebView2Window provides the following features:

1. Frameless
2. Shadow
3. Resizeable
4. Vertical Maximize
5. Restrict client area to workspace when window maximized
6. Minimize, maximize, restore and close buttons consistent with the behavior of system windows

## Usage

```python
import asyncio

from webview2 import Window, webview2_api 

class MainWindow(Window):
    @webview2_api
    def greeting(self):
        """
        JavaScript side invoke `await window.webview2.api.greeting()`
        """
        return "hello webview2"


win = MainWindow(
    title="My App", size="1480x960",# icon="logo.ico",
    url="https://www.bing.com",# cache="PATH_OF_WEBVIEW2_CACHE"
)
asyncio.run(win.run())

```

## Titlebar

Mark the css `app-region:drag;` of the title bar element to achieve the effect of dragging the title bar.