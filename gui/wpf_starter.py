netcore_desktop_path = r"C:\Program Files\dotnet\shared\Microsoft.WindowsDesktop.App\9.0.3"
netcore_webview_path = r"C:\Users\jun.dai\.nuget\packages\microsoft.web.webview2\1.0.3650.58\lib_manual\netcoreapp3.0"
runtime_webview_path = r"C:\Users\jun.dai\.nuget\packages\microsoft.web.webview2\1.0.3650.58\runtimes\win-x64\native"
import os
current_project_path = os.path.dirname(__file__)
import ctypes
ctypes.CDLL(os.path.join(netcore_desktop_path, "wpfgfx_cor3.dll"))
ctypes.CDLL(os.path.join(runtime_webview_path, "WebView2Loader.dll"))
import pythonnet
import pythoncom
pythonnet.load("coreclr")
import clr
clr.AddReference("System")
clr.AddReference(os.path.join(netcore_desktop_path, "WindowsBase.dll"))
clr.AddReference(os.path.join(netcore_desktop_path, "PresentationCore.dll"))
clr.AddReference(os.path.join(netcore_desktop_path, "PresentationFramework.dll"))
clr.AddReference(os.path.join(netcore_desktop_path, "System.Windows.Presentation.dll"))
clr.AddReference(os.path.join(netcore_webview_path, "Microsoft.Web.WebView2.Core.dll"))
clr.AddReference(os.path.join(netcore_webview_path, "Microsoft.Web.WebView2.Wpf.dll"))
clr.AddReference(os.path.join(current_project_path, "SharkSharp.dll"))
from System import Uri, UriKind
from System.Windows import Application, Window, Thickness, CornerRadius, HorizontalAlignment, VerticalAlignment, ResourceDictionary, WindowState, ResizeMode, WindowStyle, SystemParameters
from System.Windows.Shell import WindowChrome
from System.Windows.Media import Brushes, SolidColorBrush, Color, VisualTreeHelper
from System.Windows.Media.Imaging import BitmapImage
from System.Windows.Media.Effects import DropShadowEffect, BlurEffect, RenderingBias
from System.Windows.Controls import Grid, Panel, UserControl, Button, Border, DockPanel
from System.Windows.Interop import WindowInteropHelper
from Microsoft.Web.WebView2.Wpf import WebView2
from SharkSharp import WindowPlus


def print_scope():
    from System import AppDomain, Environment
    print("clr version :", Environment.Version)
    import sys
    print("---")
    print("python modules:")
    for mod in sys.modules:
        print(" ", mod)
    print("---")
    print("C# assemblies:")
    for ass in AppDomain.CurrentDomain.GetAssemblies():
        print(" ", ass.FullName)
    print("---")


class MainWindow:
    def __init__(self, width=960, height=680, resize_border=7):
        self.width = width
        self.height = height
        self.resize_border = resize_border
        self.window = WindowPlus()
        self.chrome = WindowChrome()
        self.grid = Grid()
        self.back = Border()
        self.border = Border()
        self.blur = BlurEffect()
        self.app = Application()
        self.web = WebView2()

    def setup_ui(self):
        self.window.Width = self.width
        self.window.Height = self.height
        self.window.WindowStyle = getattr(WindowStyle, "None")
        self.window.ResizeMode = ResizeMode.CanResize
        self.window.Background = Brushes.Transparent
        self.window.AllowsTransparency = True
        self.window.BorderThickness = Thickness(7, 1, 7, 1)  # Thickness(self.resize_border)
        self.window.Icon = BitmapImage(Uri(f"file:///{current_project_path}/Assets/logo-1.ico"))
        self.window.WindowState = WindowState.Normal
        self.chrome.ResizeBorderThickness = Thickness(self.resize_border)
        WindowChrome.SetWindowChrome(self.window, self.chrome)
        self.blur.Radius = 10
        self.blur.RenderingBias = RenderingBias.Quality
        self.back.Background = SolidColorBrush(Color.FromArgb(40, 40, 40, 40))
        self.back.CornerRadius = CornerRadius(8)
        self.back.Effect = self.blur
        self.border.Background = Brushes.White
        self.grid.Children.Add(self.back)
        self.grid.Children.Add(self.border)
        self.window.Content = self.grid
        self.window.StateChanged += self.on_window_state_changed

    def setup_web(self):
        # self.web.Source = Uri("https://www.bing.com")
        self.web.Source = Uri("http://172.16.1.166:8081")
        # self.web.Source = Uri(f"file:///{project_path}/index.html")
        self.web.CoreWebView2InitializationCompleted += self.on_cwv_loaded
        self.border.Child = self.web

    def on_cwv_loaded(self, *args):
        CoreWebView2 = self.web.CoreWebView2
        CoreWebView2.Settings.IsNonClientRegionSupportEnabled = True
        CoreWebView2.Settings.IsWebMessageEnabled = True
        CoreWebView2.WebMessageReceived += self.on_web_message
        CoreWebView2.OpenDevToolsWindow()

    def on_web_message(self, sender, args):
        print("on_message :", args.WebMessageAsJson)

    def on_window_state_changed(self, sender, args):
        if self.window.WindowState == WindowState.Maximized:
            self.window.BorderThickness = Thickness(0)
        else:
            self.window.BorderThickness = Thickness(7, 1, 7, 1)

    def run(self):
        self.app.Run(self.window)


def main():
    pythoncom.CoInitialize()
    win = MainWindow()
    win.setup_ui()
    win.setup_web()
    win.run()


if __name__ == '__main__':
    main()
