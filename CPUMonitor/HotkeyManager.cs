using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;

namespace CPUMonitor;

public sealed class HotkeyManager
{
    public const uint MOD_ALT = 0x0001;
    public const uint MOD_CONTROL = 0x0002;
    public const uint MOD_SHIFT = 0x0004;
    public const uint MOD_WIN = 0x0008;

    private const int WM_HOTKEY = 0x0312;

    private HwndSource? _source;

    public event EventHandler? HotkeyPressed;

    public void Initialize(Window window)
    {
        var helper = new WindowInteropHelper(window);
        _source = HwndSource.FromHwnd(helper.Handle);

        _source?.AddHook(WndProc);
    }

    public bool Register(Window window, int id, uint modifiers, uint key)
    {
        var hwnd = new WindowInteropHelper(window).Handle;
        return RegisterHotKey(hwnd, id, modifiers, key);
    }

    public void Unregister(Window window, int id)
    {
        var hwnd = new WindowInteropHelper(window).Handle;
        if (hwnd != IntPtr.Zero)
            UnregisterHotKey(hwnd, id);
    }

    private IntPtr WndProc(IntPtr hwnd, int msg, IntPtr wParam, IntPtr lParam, ref bool handled)
    {
        if (msg == WM_HOTKEY)
        {
            HotkeyPressed?.Invoke(this, EventArgs.Empty);
            handled = true;
        }

        return IntPtr.Zero;
    }

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool RegisterHotKey(
        IntPtr hWnd,
        int id,
        uint fsModifiers,
        uint vk);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool UnregisterHotKey(
        IntPtr hWnd,
        int id);
}
