using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;

public class WindowPlus : Window
{
    public WindowPlus()
    {
        SourceInitialized += (s, e) =>
        {
            var hwnd = new WindowInteropHelper(this).Handle;
            var source = HwndSource.FromHwnd(hwnd);
            source?.AddHook(WndProc);
        };
    }

    private IntPtr WndProc(IntPtr hwnd, int msg, IntPtr wParam, IntPtr lParam, ref bool handled)
    {
        const int WM_GETMINMAXINFO = 0x0024;

        if (msg == WM_GETMINMAXINFO)
        {
            // 获取当前窗口所在的显示器
            var monitor = MonitorFromWindow(hwnd, MonitorDefaultToNearest);
            if (monitor != IntPtr.Zero)
            {
                var monitorInfo = new MonitorInfo();
                monitorInfo.cbSize = Marshal.SizeOf(monitorInfo);
                GetMonitorInfo(monitor, ref monitorInfo);

                // 使用 rcWork（工作区）而非 rcMonitor（全屏）
                var mmi = (MinMaxInfo)Marshal.PtrToStructure(lParam, typeof(MinMaxInfo))!;

                mmi.ptMaxPosition.X = Math.Abs(monitorInfo.rcWork.left - monitorInfo.rcMonitor.left);
                mmi.ptMaxPosition.Y = Math.Abs(monitorInfo.rcWork.top - monitorInfo.rcMonitor.top);
                mmi.ptMaxSize.X = monitorInfo.rcWork.right - monitorInfo.rcWork.left;
                mmi.ptMaxSize.Y = monitorInfo.rcWork.bottom - monitorInfo.rcWork.top;

                Marshal.StructureToPtr(mmi, lParam, false);
                handled = true;
            }
        }

        return IntPtr.Zero;
    }

    // P/Invoke 声明
    [DllImport("user32.dll")]
    static extern IntPtr MonitorFromWindow(IntPtr hwnd, uint dwFlags);

    private const uint MonitorDefaultToNearest = 0x00000002;

    [DllImport("user32.dll")]
    static extern bool GetMonitorInfo(IntPtr hMonitor, ref MonitorInfo lpmi);

    [StructLayout(LayoutKind.Sequential)]
    public struct Point
    {
        public int X;
        public int Y;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct MinMaxInfo
    {
        public Point ptReserved;
        public Point ptMaxSize;
        public Point ptMaxPosition;
        public Point ptMinTrackSize;
        public Point ptMaxTrackSize;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct MonitorInfo
    {
        public int cbSize;
        public Rect rcMonitor;
        public Rect rcWork;
        public uint dwFlags;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct Rect
    {
        public int left;
        public int top;
        public int right;
        public int bottom;
    }
}