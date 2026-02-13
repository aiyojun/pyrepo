# Project description

Build immersive applications supported by WebView2 on Windows Operation Systems

## Usage

```python
import asyncio

from webview2 import Window, webview2_api 

class MainWindow(Window):
    @webview2_api
    def greeting(self):
        return "hello webview2"


win = MainWindow(
    title="My App", size="1480x960",# icon="logo.ico",
    url="https://www.bing.com",# cache="PATH_OF_WEBVIEW2_CACHE"
)
asyncio.run(win.run())

```

## Titlebar

Mark the css `app-region:drag;` of the title bar element to achieve the effect of dragging the title bar.