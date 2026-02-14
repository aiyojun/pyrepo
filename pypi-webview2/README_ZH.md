# webview2

在Windows系统上，构建基于WebView2的沉浸式应用。

## GUI框架

不使用WinForms和WPF，直接采用Win32。

选用win32的原因是：只有原生api能完全控制窗体的功能，包括获得沉浸式效果。

本项目使用win32的方式很特殊，主体功能由pywin32构建，以充分发挥Python能力；

WebView2部分因存在COM接口，所以采用了C++封装dll的方式，由WebView2Window提供支持。

鉴于WebView2窗体渲染模式屏蔽了跟系统间的交互，WebView2Window采用Composition渲染模式。

在Composition模式下，WebView的窗体能够达到与Visual Studio和Jetbrains一样的沉浸式窗体。

WebView2Window提供的特性如下：

1. Frameless
2. 窗体阴影
3. Resizeable
4. 垂直最大化
5. 当窗口最大化时，限制客户端区域到工作区内
6. 与系统窗体行为一致的最小化，最大化，还原和关闭按钮

## 使用方法

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

## 自定义标题栏

将自定义的标题栏区域的css的app-region属性标记未drag，即可获得拖拽标题栏效果。