using System.Windows;
using System.Windows.Input;
using KeyEventArgs = System.Windows.Input.KeyEventArgs;
using MessageBox = System.Windows.MessageBox;
using MessageBoxButton = System.Windows.MessageBoxButton;
using MessageBoxImage = System.Windows.MessageBoxImage;

namespace CPUMonitor;

public partial class SettingsWindow : Window
{
    public AppSettings Settings { get; private set; }

    private uint _modifiers;
    private uint _key;


    public SettingsWindow(
        AppSettings settings,
        string hotkeyText)
    {
        InitializeComponent();


        Settings = new AppSettings
        {
            Opacity =
                settings.Opacity,

            AlwaysOnTop =
                settings.AlwaysOnTop,

            StartWithWindows =
                settings.StartWithWindows,

            Left =
                settings.Left,

            Top =
                settings.Top,

            HotkeyModifiers =
                settings.HotkeyModifiers,

            HotkeyKey =
                settings.HotkeyKey,

            ShowNetwork =
                settings.ShowNetwork,

            ShowDisk =
                settings.ShowDisk,

            ShowMonthlyNetwork =
                settings.ShowMonthlyNetwork,

            Theme =
                settings.Theme
        };


        _modifiers =
            Settings.HotkeyModifiers;

        _key =
            Settings.HotkeyKey;


        OpacitySlider.Value =
            Settings.Opacity * 100;

        AlwaysOnTopCheck.IsChecked =
            Settings.AlwaysOnTop;

        StartupCheck.IsChecked =
            Settings.StartWithWindows;

        switch (Settings.Theme?.Trim().ToLowerInvariant())
        {
            case "speedrunners":
                ThemeComboBox.SelectedIndex = 1;
                break;
            case "windowsxp":
            case "xp":
                ThemeComboBox.SelectedIndex = 2;
                break;
            case "windows7":
            case "win7":
                ThemeComboBox.SelectedIndex = 3;
                break;
            case "windows10":
            case "win10":
                ThemeComboBox.SelectedIndex = 4;
                break;
            default:
                ThemeComboBox.SelectedIndex = 0;
                break;
        }

        MonthlyNetworkCheck.IsChecked =
            Settings.ShowMonthlyNetwork;

        NetworkCheck.IsChecked =
            Settings.ShowNetwork;

        DiskCheck.IsChecked =
            Settings.ShowDisk;

        HotkeyBox.Text =
            hotkeyText;
    }


    private void OpacitySlider_ValueChanged(
        object sender,
        RoutedPropertyChangedEventArgs<double> e)
    {
        if (OpacityText != null)
        {
            OpacityText.Text =
                $"{(int)OpacitySlider.Value}%";
        }
    }


    private void HotkeyBox_PreviewKeyDown(
        object sender,
        KeyEventArgs e)
    {
        e.Handled = true;


        var modifiers =
            Keyboard.Modifiers;

        uint nativeModifiers = 0;


        if ((modifiers &
             ModifierKeys.Control) != 0)
        {
            nativeModifiers |=
                HotkeyManager.MOD_CONTROL;
        }


        if ((modifiers &
             ModifierKeys.Alt) != 0)
        {
            nativeModifiers |=
                HotkeyManager.MOD_ALT;
        }


        if ((modifiers &
             ModifierKeys.Shift) != 0)
        {
            nativeModifiers |=
                HotkeyManager.MOD_SHIFT;
        }


        if ((modifiers &
             ModifierKeys.Windows) != 0)
        {
            nativeModifiers |=
                HotkeyManager.MOD_WIN;
        }


        Key key =
            e.Key == Key.System
                ? e.SystemKey
                : e.Key;


        if (key is Key.LeftCtrl or
            Key.RightCtrl or
            Key.LeftAlt or
            Key.RightAlt or
            Key.LeftShift or
            Key.RightShift or
            Key.LWin or
            Key.RWin)
        {
            return;
        }


        uint vk =
            (uint)KeyInterop.VirtualKeyFromKey(
                key);


        if (nativeModifiers == 0)
        {
            MessageBox.Show(
                "El atajo debe incluir Ctrl, Alt, Shift o Windows.",
                "Atajo inválido",
                MessageBoxButton.OK,
                MessageBoxImage.Information);

            return;
        }


        _modifiers =
            nativeModifiers;

        _key =
            vk;


        HotkeyBox.Text =
            BuildHotkeyText(
                nativeModifiers,
                vk);
    }


    private static string BuildHotkeyText(
        uint modifiers,
        uint key)
    {
        var parts =
            new List<string>();


        if ((modifiers &
             HotkeyManager.MOD_CONTROL) != 0)
        {
            parts.Add("Ctrl");
        }


        if ((modifiers &
             HotkeyManager.MOD_ALT) != 0)
        {
            parts.Add("Alt");
        }


        if ((modifiers &
             HotkeyManager.MOD_SHIFT) != 0)
        {
            parts.Add("Shift");
        }


        if ((modifiers &
             HotkeyManager.MOD_WIN) != 0)
        {
            parts.Add("Win");
        }


        string keyName =
            key switch
            {
                >= 0x41 and <= 0x5A =>
                    ((char)key).ToString(),

                >= 0x30 and <= 0x39 =>
                    ((char)key).ToString(),

                >= 0x70 and <= 0x87 =>
                    $"F{key - 0x6F}",

                0x20 =>
                    "Space",

                0x1B =>
                    "Esc",

                _ =>
                    $"0x{key:X}"
            };


        parts.Add(keyName);

        return string.Join(
            " + ",
            parts);
    }


    private void Save_Click(
        object sender,
        RoutedEventArgs e)
    {
        Settings.Opacity =
            OpacitySlider.Value / 100.0;

        Settings.AlwaysOnTop =
            AlwaysOnTopCheck.IsChecked == true;

        Settings.StartWithWindows =
            StartupCheck.IsChecked == true;

        Settings.ShowNetwork =
            NetworkCheck.IsChecked == true;

        Settings.ShowDisk =
            DiskCheck.IsChecked == true;

        Settings.ShowMonthlyNetwork =
            MonthlyNetworkCheck.IsChecked == true;

        if (ThemeComboBox.SelectedItem is System.Windows.Controls.ComboBoxItem selectedTheme &&
            selectedTheme.Tag is string themeTag)
        {
            Settings.Theme = themeTag;
        }
        else
        {
            Settings.Theme = "Default";
        }

        Settings.HotkeyModifiers =
            _modifiers;

        Settings.HotkeyKey =
            _key;


        DialogResult = true;
    }


    private void Cancel_Click(
        object sender,
        RoutedEventArgs e)
    {
        DialogResult = false;
    }
}