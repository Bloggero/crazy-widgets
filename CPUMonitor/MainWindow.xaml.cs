using System.ComponentModel;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Shapes;
using System.Windows.Threading;
using Application = System.Windows.Application;
using Brush = System.Windows.Media.Brush;
using Brushes = System.Windows.Media.Brushes;
using FontFamily = System.Windows.Media.FontFamily;
using Color = System.Windows.Media.Color;
using Point = System.Windows.Point;
using KeyEventArgs = System.Windows.Input.KeyEventArgs;
using MouseButtonEventArgs = System.Windows.Input.MouseButtonEventArgs;
using HorizontalAlignment = System.Windows.HorizontalAlignment;
using MessageBox = System.Windows.MessageBox;
using MessageBoxButton = System.Windows.MessageBoxButton;
using MessageBoxImage = System.Windows.MessageBoxImage;

namespace CPUMonitor;

public partial class MainWindow : Window
{
    private const int HotkeyId = 9001;

    private readonly DispatcherTimer _timer;
    private readonly SettingsManager _settingsManager;

    private AppSettings _settings;

    private readonly PerformanceMonitor _monitor;
    private readonly HotkeyManager _hotkeyManager;

    private bool _allowClose;
    private bool _settingsOpen;
    private bool _isUpdating;
    private DateTime _lastMonthlyUpdate = DateTime.MinValue;
    private bool _hasMonthlyData;
    private System.Windows.Forms.NotifyIcon? _notifyIcon;

    public MainWindow()
    {
        InitializeComponent();

        _settingsManager = new SettingsManager();
        _settings = _settingsManager.Load();
        _monitor = new PerformanceMonitor();
        _hotkeyManager = new HotkeyManager();

        _timer = new DispatcherTimer
        {
            Interval = TimeSpan.FromSeconds(1)
        };

        _timer.Tick += Timer_Tick;

        ApplySettings();
        InitializeTrayIcon();
    }

    // =========================================
    // CARGA
    // =========================================
    private void Window_Loaded(object sender, RoutedEventArgs e)
    {
        UpdateIndicatorLayout();

        if (!double.IsNaN(_settings.Left) && !double.IsNaN(_settings.Top))
        {
            Left = _settings.Left;
            Top = _settings.Top;
        }
        else
        {
            Left = SystemParameters.WorkArea.Right - ActualWidth - 20;
            Top = SystemParameters.WorkArea.Top + 20;
        }

        EnsureWindowWithinBounds();
        RegisterHotkey();

        _timer.Start();
        Timer_Tick(null, EventArgs.Empty);
    }

    protected override void OnLocationChanged(EventArgs e)
    {
        base.OnLocationChanged(e);
        if (IsLoaded && !double.IsNaN(Left) && !double.IsNaN(Top))
        {
            _settings.Left = Left;
            _settings.Top = Top;
        }
    }

    // =========================================
    // ACTUALIZACIÓN ASÍNCRONA (SIN BLOQUEO DE UI)
    // =========================================
    private async void Timer_Tick(object? sender, EventArgs e)
    {
        if (_settings.ShowMonthlyNetwork &&
            ((DateTime.UtcNow - _lastMonthlyUpdate).TotalSeconds >= 30 || !_hasMonthlyData))
        {
            _lastMonthlyUpdate = DateTime.UtcNow;
            _ = UpdateMonthlyNetworkStatsAsync();
        }

        if (_isUpdating)
            return;

        _isUpdating = true;

        try
        {
            var stats = await Task.Run(() => _monitor.GetStats());

            // CPU
            CpuText.Text = $"{stats.CpuUsage:0}%";

            // TEMPERATURA
            if (stats.CpuTemperature > 0)
            {
                CpuTemperatureText.Text = $"{stats.CpuTemperature:0}°C";
                UpdateTemperatureColor(stats.CpuTemperature);
            }
            else
            {
                CpuTemperatureText.Text = "--°C";
                CpuTemperatureText.Foreground = Brushes.White;
            }

            // RAM
            RamText.Text = $"{stats.RamUsage:0}%";
            RamDetailsText.Text = $"{stats.UsedRamGb:0.0} / {stats.TotalRamGb:0.0} GB";

            // NETWORK
            DownloadText.Text = $"↓ {FormatNetworkSpeed(stats.DownloadMbps)}";
            UploadText.Text = $"↑ {FormatNetworkSpeed(stats.UploadMbps)}";

            // DISK
            DiskText.Text = $"{stats.DiskUsage:0}%";
        }
        catch
        {
            // Fallback silencioso ante excepciones transitorias
        }
        finally
        {
            _isUpdating = false;
        }
    }

    // =========================================
    // RED 30 DÍAS
    // =========================================
    private async Task UpdateMonthlyNetworkStatsAsync()
    {
        try
        {
            var stats = await PerformanceMonitor.GetLast30DaysNetworkUsageAsync();
            _hasMonthlyData = true;

            MonthlyNetworkTotalText.Text = PerformanceMonitor.FormatDataSize(stats.TotalGb);
            MonthlyDownloadText.Text = $"↓ Descarga: {PerformanceMonitor.FormatDataSize(stats.DownloadGb)}";
            MonthlyUploadText.Text = $"↑ Subida: {PerformanceMonitor.FormatDataSize(stats.UploadGb)}";
        }
        catch
        {
        }
    }

    // =========================================
    // RED
    // =========================================
    private static string FormatNetworkSpeed(double mbps)
    {
        if (mbps < 1)
        {
            return $"{mbps * 1000:0} Kbps";
        }

        if (mbps < 1000)
        {
            return $"{mbps:0.0} Mbps";
        }

        return $"{mbps / 1000:0.00} Gbps";
    }

    // =========================================
    // CAMBIAR COLOR TEMPERATURA
    // =========================================
    private Brush _normalTempBrush = Brushes.White;

    // =========================================
    // CAMBIAR COLOR TEMPERATURA
    // =========================================
    private void UpdateTemperatureColor(double temperature)
    {
        if (temperature >= 85)
        {
            CpuTemperatureText.Foreground = Brushes.IndianRed;
        }
        else if (temperature >= 70)
        {
            CpuTemperatureText.Foreground = Brushes.Gold;
        }
        else
        {
            CpuTemperatureText.Foreground = _normalTempBrush;
        }
    }

    // =========================================
    // CONFIGURACIÓN
    // =========================================
    private void ApplySettings()
    {
        Opacity = Math.Clamp(_settings.Opacity, 0.25, 1.0);
        Topmost = _settings.AlwaysOnTop;

        ApplyTheme();
        UpdateIndicatorLayout();
    }

    private void ApplyTheme()
    {
        if (ThemeBackgroundContainer == null || RootBorder == null)
            return;

        string theme = _settings.Theme?.Trim() ?? "Default";

        if (string.Equals(theme, "SpeedRunners", StringComparison.OrdinalIgnoreCase))
        {
            ApplySpeedRunnersTheme();
        }
        else if (string.Equals(theme, "WindowsXP", StringComparison.OrdinalIgnoreCase) ||
                 string.Equals(theme, "XP", StringComparison.OrdinalIgnoreCase))
        {
            ApplyWindowsXpTheme();
        }
        else if (string.Equals(theme, "Windows7", StringComparison.OrdinalIgnoreCase) ||
                 string.Equals(theme, "Win7", StringComparison.OrdinalIgnoreCase))
        {
            ApplyWindows7Theme();
        }
        else if (string.Equals(theme, "Windows10", StringComparison.OrdinalIgnoreCase) ||
                 string.Equals(theme, "Win10", StringComparison.OrdinalIgnoreCase))
        {
            ApplyWindows10Theme();
        }
        else
        {
            ApplyDefaultTheme();
        }
    }

    private void ApplyDefaultTheme()
    {
        var segoe = new FontFamily("Segoe UI");
        _normalTempBrush = Brushes.White;

        ThemeBackgroundContainer.Visibility = Visibility.Collapsed;
        AeroGlassOverlay.Visibility = Visibility.Collapsed;

        RootBorder.CornerRadius = new CornerRadius(18);
        RootBorder.Background = new SolidColorBrush(Color.FromArgb(0xE6, 0x11, 0x11, 0x11));
        RootBorder.BorderBrush = new SolidColorBrush(Color.FromArgb(0x55, 0xFF, 0xFF, 0xFF));
        RootBorder.BorderThickness = new Thickness(1);
        MainContentGrid.Margin = new Thickness(12, 10, 12, 12);

        HeaderBorder.Background = Brushes.Transparent;
        HeaderBorder.CornerRadius = new CornerRadius(0);
        HeaderBorder.Padding = new Thickness(2, 0, 2, 6);

        HeaderTitle1.Text = "SYSTEM";
        HeaderTitle1.Foreground = Brushes.White;
        HeaderTitle1.FontFamily = segoe;
        HeaderTitle1.FontSize = 13;

        HeaderTitleSep.Visibility = Visibility.Visible;
        HeaderTitleSep.Text = " // ";
        HeaderTitleSep.Foreground = new SolidColorBrush(Color.FromRgb(0x66, 0x66, 0x66));

        HeaderTitle2.Text = "MONITOR";
        HeaderTitle2.Foreground = new SolidColorBrush(Color.FromRgb(0x99, 0x99, 0x99));
        HeaderTitle2.FontFamily = segoe;
        HeaderTitle2.FontSize = 11;

        HeaderSeparator.Visibility = Visibility.Visible;
        HeaderSeparator.Fill = new SolidColorBrush(Color.FromRgb(0x33, 0x33, 0x33));
        HeaderSeparator.Height = 1;
        HeaderSeparator.Margin = new Thickness(0, 0, 0, 8);

        SettingsButton.Background = Brushes.Transparent;
        SettingsButton.Foreground = Brushes.White;
        SettingsButton.BorderThickness = new Thickness(0);
        SettingsButton.Width = 26;
        SettingsButton.Height = 24;

        CloseButton.Background = Brushes.Transparent;
        CloseButton.Foreground = Brushes.White;
        CloseButton.BorderThickness = new Thickness(0);
        CloseButton.Width = 26;
        CloseButton.Height = 24;

        if (MonthlyNetworkContainer != null)
        {
            MonthlyNetworkContainer.Background = new SolidColorBrush(Color.FromRgb(0x14, 0x14, 0x14));
            MonthlyNetworkContainer.BorderBrush = new SolidColorBrush(Color.FromRgb(0x2E, 0x2E, 0x2E));
            MonthlyNetworkContainer.BorderThickness = new Thickness(1);
            MonthlyNetworkContainer.CornerRadius = new CornerRadius(10);
            MonthlyNetworkHeaderLabel.Foreground = new SolidColorBrush(Color.FromRgb(0x9E, 0x9E, 0x9E));
            MonthlyNetworkHeaderLabel.FontFamily = segoe;
            MonthlyNetworkTotalLabel.Foreground = new SolidColorBrush(Color.FromRgb(0x88, 0x88, 0x88));
            MonthlyNetworkTotalLabel.FontFamily = segoe;
            MonthlyNetworkTotalText.Foreground = new SolidColorBrush(Color.FromRgb(0x38, 0xBD, 0xF8));
            MonthlyNetworkTotalText.FontFamily = segoe;
            MonthlyDownloadText.Foreground = new SolidColorBrush(Color.FromRgb(0xF1, 0xF5, 0xF9));
            MonthlyDownloadText.FontFamily = segoe;
            MonthlyUploadText.Foreground = new SolidColorBrush(Color.FromRgb(0x94, 0xA3, 0xB8));
            MonthlyUploadText.FontFamily = segoe;
        }

        var outerFill = new SolidColorBrush(Color.FromRgb(0x15, 0x15, 0x15));
        var outerStroke = new SolidColorBrush(Color.FromRgb(0x4A, 0x4A, 0x4A));
        var innerStroke = new SolidColorBrush(Color.FromRgb(0x29, 0x29, 0x29));
        var labelBrush = new SolidColorBrush(Color.FromRgb(0x88, 0x88, 0x88));
        var subBrush = new SolidColorBrush(Color.FromRgb(0xAA, 0xAA, 0xAA));

        StyleIndicator(CpuOuterShape, CpuInnerShape, CpuLabel, CpuText, CpuTemperatureText,
            outerFill, outerStroke, 2, Brushes.Transparent, innerStroke, 1, labelBrush, Brushes.White, Brushes.White, segoe);
        StyleIndicator(RamOuterShape, RamInnerShape, RamLabel, RamText, RamDetailsText,
            outerFill, outerStroke, 2, Brushes.Transparent, innerStroke, 1, labelBrush, Brushes.White, subBrush, segoe);
        StyleIndicator(NetworkOuterShape, NetworkInnerShape, NetworkLabel, DownloadText, UploadText,
            outerFill, outerStroke, 2, Brushes.Transparent, innerStroke, 1, labelBrush, Brushes.White, subBrush, segoe);
        StyleIndicator(DiskOuterShape, DiskInnerShape, DiskLabel, DiskText, DiskSubLabel,
            outerFill, outerStroke, 2, Brushes.Transparent, innerStroke, 1, labelBrush, Brushes.White, new SolidColorBrush(Color.FromRgb(0x55, 0x55, 0x55)), segoe);
    }

    private void ApplySpeedRunnersTheme()
    {
        var segoe = new FontFamily("Segoe UI");
        _normalTempBrush = new SolidColorBrush(Color.FromRgb(0x93, 0xC5, 0xFD));

        ThemeBackgroundContainer.Visibility = Visibility.Visible;
        AeroGlassOverlay.Visibility = Visibility.Collapsed;

        RootBorder.CornerRadius = new CornerRadius(18);
        RootBorder.Background = new SolidColorBrush(Color.FromArgb(0xFA, 0x0A, 0x0E, 0x1A));
        RootBorder.BorderBrush = new SolidColorBrush(Color.FromArgb(0xCC, 0x38, 0x9B, 0xEC));
        RootBorder.BorderThickness = new Thickness(1.5);
        MainContentGrid.Margin = new Thickness(12, 10, 12, 12);

        HeaderBorder.Background = Brushes.Transparent;
        HeaderBorder.CornerRadius = new CornerRadius(0);
        HeaderBorder.Padding = new Thickness(2, 0, 2, 6);

        HeaderTitle1.Text = "SPEED";
        HeaderTitle1.Foreground = new SolidColorBrush(Color.FromRgb(0x38, 0xBD, 0xF8));
        HeaderTitle1.FontFamily = segoe;
        HeaderTitle1.FontSize = 13;

        HeaderTitleSep.Visibility = Visibility.Visible;
        HeaderTitleSep.Text = " // ";
        HeaderTitleSep.Foreground = new SolidColorBrush(Color.FromRgb(0xFF, 0x6B, 0x00));

        HeaderTitle2.Text = "RUNNER";
        HeaderTitle2.Foreground = new SolidColorBrush(Color.FromRgb(0xF1, 0xF5, 0xF9));
        HeaderTitle2.FontFamily = segoe;
        HeaderTitle2.FontSize = 11;

        HeaderSeparator.Visibility = Visibility.Visible;
        HeaderSeparator.Fill = new SolidColorBrush(Color.FromArgb(0x66, 0x38, 0x9B, 0xEC));
        HeaderSeparator.Height = 1;
        HeaderSeparator.Margin = new Thickness(0, 0, 0, 8);

        SettingsButton.Background = Brushes.Transparent;
        SettingsButton.Foreground = new SolidColorBrush(Color.FromRgb(0x38, 0xBD, 0xF8));
        SettingsButton.BorderThickness = new Thickness(0);
        SettingsButton.Width = 26;
        SettingsButton.Height = 24;

        CloseButton.Background = Brushes.Transparent;
        CloseButton.Foreground = new SolidColorBrush(Color.FromRgb(0x38, 0xBD, 0xF8));
        CloseButton.BorderThickness = new Thickness(0);
        CloseButton.Width = 26;
        CloseButton.Height = 24;

        if (MonthlyNetworkContainer != null)
        {
            MonthlyNetworkContainer.Background = new SolidColorBrush(Color.FromArgb(0x80, 0x0A, 0x14, 0x2A));
            MonthlyNetworkContainer.BorderBrush = new SolidColorBrush(Color.FromArgb(0x66, 0x38, 0x9B, 0xEC));
            MonthlyNetworkContainer.BorderThickness = new Thickness(1);
            MonthlyNetworkContainer.CornerRadius = new CornerRadius(10);
            MonthlyNetworkHeaderLabel.Foreground = new SolidColorBrush(Color.FromRgb(0x93, 0xC5, 0xFD));
            MonthlyNetworkHeaderLabel.FontFamily = segoe;
            MonthlyNetworkTotalLabel.Foreground = new SolidColorBrush(Color.FromRgb(0x60, 0xA5, 0xFA));
            MonthlyNetworkTotalLabel.FontFamily = segoe;
            MonthlyNetworkTotalText.Foreground = new SolidColorBrush(Color.FromRgb(0x38, 0xBD, 0xF8));
            MonthlyNetworkTotalText.FontFamily = segoe;
            MonthlyDownloadText.Foreground = new SolidColorBrush(Color.FromRgb(0xF1, 0xF5, 0xF9));
            MonthlyDownloadText.FontFamily = segoe;
            MonthlyUploadText.Foreground = new SolidColorBrush(Color.FromRgb(0x94, 0xA3, 0xB8));
            MonthlyUploadText.FontFamily = segoe;
        }

        var outerFill = new SolidColorBrush(Color.FromArgb(0x99, 0x07, 0x0D, 0x18));
        var outerStroke = new SolidColorBrush(Color.FromRgb(0x38, 0x9B, 0xEC));
        var innerStroke = new SolidColorBrush(Color.FromRgb(0x1D, 0x4E, 0xD8));
        var labelBrush = new SolidColorBrush(Color.FromRgb(0x38, 0xBD, 0xF8));
        var subBrush = new SolidColorBrush(Color.FromRgb(0x93, 0xC5, 0xFD));

        StyleIndicator(CpuOuterShape, CpuInnerShape, CpuLabel, CpuText, CpuTemperatureText,
            outerFill, outerStroke, 2, Brushes.Transparent, innerStroke, 1, labelBrush, Brushes.White, subBrush, segoe);
        StyleIndicator(RamOuterShape, RamInnerShape, RamLabel, RamText, RamDetailsText,
            outerFill, outerStroke, 2, Brushes.Transparent, innerStroke, 1, labelBrush, Brushes.White, subBrush, segoe);
        StyleIndicator(NetworkOuterShape, NetworkInnerShape, NetworkLabel, DownloadText, UploadText,
            outerFill, outerStroke, 2, Brushes.Transparent, innerStroke, 1, labelBrush, Brushes.White, subBrush, segoe);
        StyleIndicator(DiskOuterShape, DiskInnerShape, DiskLabel, DiskText, DiskSubLabel,
            outerFill, outerStroke, 2, Brushes.Transparent, innerStroke, 1, labelBrush, Brushes.White, labelBrush, segoe);
    }

    private void ApplyWindowsXpTheme()
    {
        var tahoma = new FontFamily("Tahoma");
        _normalTempBrush = new SolidColorBrush(Color.FromRgb(0x00, 0x66, 0x00));

        ThemeBackgroundContainer.Visibility = Visibility.Collapsed;
        AeroGlassOverlay.Visibility = Visibility.Collapsed;

        RootBorder.CornerRadius = new CornerRadius(8, 8, 4, 4);
        RootBorder.Background = new SolidColorBrush(Color.FromRgb(0xEC, 0xE9, 0xD8));
        RootBorder.BorderBrush = new SolidColorBrush(Color.FromRgb(0x00, 0x1C, 0x99));
        RootBorder.BorderThickness = new Thickness(3);
        MainContentGrid.Margin = new Thickness(8, 6, 8, 8);

        HeaderBorder.Background = CreateXpTitleBarBrush();
        HeaderBorder.CornerRadius = new CornerRadius(5, 5, 0, 0);
        HeaderBorder.Padding = new Thickness(8, 5, 6, 5);

        HeaderTitle1.Text = "🪟 Windows XP";
        HeaderTitle1.Foreground = Brushes.White;
        HeaderTitle1.FontFamily = tahoma;
        HeaderTitle1.FontSize = 12;

        HeaderTitleSep.Visibility = Visibility.Collapsed;

        HeaderTitle2.Text = "• Rendimiento";
        HeaderTitle2.Foreground = new SolidColorBrush(Color.FromRgb(0xD8, 0xEB, 0xFF));
        HeaderTitle2.FontFamily = tahoma;
        HeaderTitle2.FontSize = 11;

        HeaderSeparator.Visibility = Visibility.Visible;
        HeaderSeparator.Fill = new SolidColorBrush(Color.FromRgb(0x00, 0x2A, 0x88));
        HeaderSeparator.Height = 1;
        HeaderSeparator.Margin = new Thickness(0, 4, 0, 8);

        SettingsButton.Background = CreateXpButtonBrush();
        SettingsButton.Foreground = Brushes.White;
        SettingsButton.BorderBrush = new SolidColorBrush(Color.FromRgb(0x00, 0x1C, 0x77));
        SettingsButton.BorderThickness = new Thickness(1);
        SettingsButton.Width = 22;
        SettingsButton.Height = 22;

        CloseButton.Background = CreateXpCloseButtonBrush();
        CloseButton.Foreground = Brushes.White;
        CloseButton.BorderBrush = new SolidColorBrush(Color.FromRgb(0x82, 0x17, 0x03));
        CloseButton.BorderThickness = new Thickness(1);
        CloseButton.Width = 22;
        CloseButton.Height = 22;

        if (MonthlyNetworkContainer != null)
        {
            MonthlyNetworkContainer.Background = Brushes.White;
            MonthlyNetworkContainer.BorderBrush = new SolidColorBrush(Color.FromRgb(0x7F, 0x9D, 0xB9));
            MonthlyNetworkContainer.BorderThickness = new Thickness(1.5);
            MonthlyNetworkContainer.CornerRadius = new CornerRadius(3);
            MonthlyNetworkHeaderLabel.Foreground = new SolidColorBrush(Color.FromRgb(0x00, 0x33, 0x99));
            MonthlyNetworkHeaderLabel.FontFamily = tahoma;
            MonthlyNetworkTotalLabel.Foreground = new SolidColorBrush(Color.FromRgb(0x55, 0x55, 0x55));
            MonthlyNetworkTotalLabel.FontFamily = tahoma;
            MonthlyNetworkTotalText.Foreground = new SolidColorBrush(Color.FromRgb(0x00, 0x33, 0x99));
            MonthlyNetworkTotalText.FontFamily = tahoma;
            MonthlyDownloadText.Foreground = new SolidColorBrush(Color.FromRgb(0x11, 0x11, 0x11));
            MonthlyDownloadText.FontFamily = tahoma;
            MonthlyUploadText.Foreground = new SolidColorBrush(Color.FromRgb(0x44, 0x44, 0x44));
            MonthlyUploadText.FontFamily = tahoma;
        }

        var outerFill = Brushes.White;
        var outerStroke = new SolidColorBrush(Color.FromRgb(0x7F, 0x9D, 0xB9));
        var innerFill = new SolidColorBrush(Color.FromRgb(0xF7, 0xF6, 0xF0));
        var innerStroke = new SolidColorBrush(Color.FromRgb(0xD4, 0xD0, 0xC8));
        var labelBrush = new SolidColorBrush(Color.FromRgb(0x00, 0x33, 0x99));
        var mainBrush = new SolidColorBrush(Color.FromRgb(0x0A, 0x24, 0x6A));
        var subBrush = new SolidColorBrush(Color.FromRgb(0x44, 0x44, 0x44));

        StyleIndicator(CpuOuterShape, CpuInnerShape, CpuLabel, CpuText, CpuTemperatureText,
            outerFill, outerStroke, 2, innerFill, innerStroke, 1, labelBrush, mainBrush, _normalTempBrush, tahoma);
        StyleIndicator(RamOuterShape, RamInnerShape, RamLabel, RamText, RamDetailsText,
            outerFill, outerStroke, 2, innerFill, innerStroke, 1, labelBrush, mainBrush, subBrush, tahoma);
        StyleIndicator(NetworkOuterShape, NetworkInnerShape, NetworkLabel, DownloadText, UploadText,
            outerFill, outerStroke, 2, innerFill, innerStroke, 1, labelBrush, mainBrush, subBrush, tahoma);
        StyleIndicator(DiskOuterShape, DiskInnerShape, DiskLabel, DiskText, DiskSubLabel,
            outerFill, outerStroke, 2, innerFill, innerStroke, 1, labelBrush, mainBrush, new SolidColorBrush(Color.FromRgb(0x88, 0x88, 0x88)), tahoma);
    }

    private void ApplyWindows7Theme()
    {
        var segoe = new FontFamily("Segoe UI");
        _normalTempBrush = new SolidColorBrush(Color.FromRgb(0xA0, 0xE0, 0xFF));

        ThemeBackgroundContainer.Visibility = Visibility.Collapsed;
        AeroGlassOverlay.Visibility = Visibility.Visible;

        RootBorder.CornerRadius = new CornerRadius(12);
        RootBorder.Background = CreateWin7AeroBackgroundBrush();
        RootBorder.BorderBrush = CreateWin7AeroBorderBrush();
        RootBorder.BorderThickness = new Thickness(1.5);
        MainContentGrid.Margin = new Thickness(12, 10, 12, 12);

        HeaderBorder.Background = Brushes.Transparent;
        HeaderBorder.CornerRadius = new CornerRadius(0);
        HeaderBorder.Padding = new Thickness(2, 0, 2, 6);

        HeaderTitle1.Text = "WINDOWS 7";
        HeaderTitle1.Foreground = Brushes.White;
        HeaderTitle1.FontFamily = segoe;
        HeaderTitle1.FontSize = 13;

        HeaderTitleSep.Visibility = Visibility.Visible;
        HeaderTitleSep.Text = " // ";
        HeaderTitleSep.Foreground = new SolidColorBrush(Color.FromRgb(0x52, 0xD3, 0xFF));

        HeaderTitle2.Text = "AERO";
        HeaderTitle2.Foreground = new SolidColorBrush(Color.FromRgb(0xA0, 0xE0, 0xFF));
        HeaderTitle2.FontFamily = segoe;
        HeaderTitle2.FontSize = 11;

        HeaderSeparator.Visibility = Visibility.Visible;
        HeaderSeparator.Fill = CreateWin7SeparatorBrush();
        HeaderSeparator.Height = 1.5;
        HeaderSeparator.Margin = new Thickness(0, 0, 0, 8);

        SettingsButton.Background = new SolidColorBrush(Color.FromArgb(0x33, 0xFF, 0xFF, 0xFF));
        SettingsButton.Foreground = Brushes.White;
        SettingsButton.BorderBrush = new SolidColorBrush(Color.FromArgb(0x66, 0x52, 0xD3, 0xFF));
        SettingsButton.BorderThickness = new Thickness(1);
        SettingsButton.Width = 24;
        SettingsButton.Height = 22;

        CloseButton.Background = new SolidColorBrush(Color.FromArgb(0x33, 0xFF, 0xFF, 0xFF));
        CloseButton.Foreground = Brushes.White;
        CloseButton.BorderBrush = new SolidColorBrush(Color.FromArgb(0x66, 0x52, 0xD3, 0xFF));
        CloseButton.BorderThickness = new Thickness(1);
        CloseButton.Width = 24;
        CloseButton.Height = 22;

        if (MonthlyNetworkContainer != null)
        {
            MonthlyNetworkContainer.Background = new SolidColorBrush(Color.FromArgb(0x45, 0x0A, 0x22, 0x3D));
            MonthlyNetworkContainer.BorderBrush = new SolidColorBrush(Color.FromArgb(0x60, 0x52, 0xD3, 0xFF));
            MonthlyNetworkContainer.BorderThickness = new Thickness(1);
            MonthlyNetworkContainer.CornerRadius = new CornerRadius(8);
            MonthlyNetworkHeaderLabel.Foreground = new SolidColorBrush(Color.FromRgb(0x93, 0xE2, 0xFF));
            MonthlyNetworkHeaderLabel.FontFamily = segoe;
            MonthlyNetworkTotalLabel.Foreground = new SolidColorBrush(Color.FromRgb(0xB3, 0xEC, 0xFF));
            MonthlyNetworkTotalLabel.FontFamily = segoe;
            MonthlyNetworkTotalText.Foreground = new SolidColorBrush(Color.FromRgb(0x38, 0xD9, 0xFF));
            MonthlyNetworkTotalText.FontFamily = segoe;
            MonthlyDownloadText.Foreground = new SolidColorBrush(Color.FromRgb(0xF0, 0xFD, 0xFF));
            MonthlyDownloadText.FontFamily = segoe;
            MonthlyUploadText.Foreground = new SolidColorBrush(Color.FromRgb(0x80, 0xDE, 0xEA));
            MonthlyUploadText.FontFamily = segoe;
        }

        var outerFill = new SolidColorBrush(Color.FromArgb(0x45, 0x0D, 0x25, 0x3E));
        var outerStroke = new SolidColorBrush(Color.FromRgb(0x42, 0xB8, 0xFF));
        var innerFill = new SolidColorBrush(Color.FromArgb(0x20, 0x00, 0x10, 0x20));
        var innerStroke = new SolidColorBrush(Color.FromArgb(0x30, 0x80, 0xD0, 0xFF));
        var labelBrush = new SolidColorBrush(Color.FromRgb(0x52, 0xD3, 0xFF));
        var subBrush = new SolidColorBrush(Color.FromRgb(0xA0, 0xE0, 0xFF));

        StyleIndicator(CpuOuterShape, CpuInnerShape, CpuLabel, CpuText, CpuTemperatureText,
            outerFill, outerStroke, 2, innerFill, innerStroke, 1, labelBrush, Brushes.White, subBrush, segoe);
        StyleIndicator(RamOuterShape, RamInnerShape, RamLabel, RamText, RamDetailsText,
            outerFill, outerStroke, 2, innerFill, innerStroke, 1, labelBrush, Brushes.White, subBrush, segoe);
        StyleIndicator(NetworkOuterShape, NetworkInnerShape, NetworkLabel, DownloadText, UploadText,
            outerFill, outerStroke, 2, innerFill, innerStroke, 1, labelBrush, Brushes.White, subBrush, segoe);
        StyleIndicator(DiskOuterShape, DiskInnerShape, DiskLabel, DiskText, DiskSubLabel,
            outerFill, outerStroke, 2, innerFill, innerStroke, 1, labelBrush, Brushes.White, labelBrush, segoe);
    }

    private void ApplyWindows10Theme()
    {
        var segoe = new FontFamily("Segoe UI");
        _normalTempBrush = new SolidColorBrush(Color.FromRgb(0x9E, 0x9E, 0x9E));

        ThemeBackgroundContainer.Visibility = Visibility.Collapsed;
        AeroGlassOverlay.Visibility = Visibility.Collapsed;

        RootBorder.CornerRadius = new CornerRadius(2);
        RootBorder.Background = new SolidColorBrush(Color.FromArgb(0xF2, 0x1F, 0x1F, 0x1F));
        RootBorder.BorderBrush = new SolidColorBrush(Color.FromRgb(0x00, 0x78, 0xD7));
        RootBorder.BorderThickness = new Thickness(1);
        MainContentGrid.Margin = new Thickness(12, 10, 12, 12);

        HeaderBorder.Background = Brushes.Transparent;
        HeaderBorder.CornerRadius = new CornerRadius(0);
        HeaderBorder.Padding = new Thickness(2, 0, 2, 6);

        HeaderTitle1.Text = "WINDOWS 10";
        HeaderTitle1.Foreground = new SolidColorBrush(Color.FromRgb(0x00, 0x78, 0xD7));
        HeaderTitle1.FontFamily = segoe;
        HeaderTitle1.FontSize = 13;

        HeaderTitleSep.Visibility = Visibility.Visible;
        HeaderTitleSep.Text = " // ";
        HeaderTitleSep.Foreground = new SolidColorBrush(Color.FromRgb(0x55, 0x55, 0x55));

        HeaderTitle2.Text = "MONITOR";
        HeaderTitle2.Foreground = new SolidColorBrush(Color.FromRgb(0xCC, 0xCC, 0xCC));
        HeaderTitle2.FontFamily = segoe;
        HeaderTitle2.FontSize = 11;

        HeaderSeparator.Visibility = Visibility.Visible;
        HeaderSeparator.Fill = new SolidColorBrush(Color.FromRgb(0x00, 0x78, 0xD7));
        HeaderSeparator.Height = 1;
        HeaderSeparator.Margin = new Thickness(0, 0, 0, 8);

        SettingsButton.Background = Brushes.Transparent;
        SettingsButton.Foreground = Brushes.White;
        SettingsButton.BorderThickness = new Thickness(0);
        SettingsButton.Width = 26;
        SettingsButton.Height = 24;

        CloseButton.Background = Brushes.Transparent;
        CloseButton.Foreground = Brushes.White;
        CloseButton.BorderThickness = new Thickness(0);
        CloseButton.Width = 26;
        CloseButton.Height = 24;

        if (MonthlyNetworkContainer != null)
        {
            MonthlyNetworkContainer.Background = new SolidColorBrush(Color.FromRgb(0x2D, 0x2D, 0x30));
            MonthlyNetworkContainer.BorderBrush = new SolidColorBrush(Color.FromRgb(0x3E, 0x3E, 0x42));
            MonthlyNetworkContainer.BorderThickness = new Thickness(1);
            MonthlyNetworkContainer.CornerRadius = new CornerRadius(0);
            MonthlyNetworkHeaderLabel.Foreground = new SolidColorBrush(Color.FromRgb(0xCC, 0xCC, 0xCC));
            MonthlyNetworkHeaderLabel.FontFamily = segoe;
            MonthlyNetworkTotalLabel.Foreground = new SolidColorBrush(Color.FromRgb(0x85, 0x85, 0x85));
            MonthlyNetworkTotalLabel.FontFamily = segoe;
            MonthlyNetworkTotalText.Foreground = new SolidColorBrush(Color.FromRgb(0x00, 0x99, 0xFF));
            MonthlyNetworkTotalText.FontFamily = segoe;
            MonthlyDownloadText.Foreground = new SolidColorBrush(Color.FromRgb(0xE1, 0xE1, 0xE1));
            MonthlyDownloadText.FontFamily = segoe;
            MonthlyUploadText.Foreground = new SolidColorBrush(Color.FromRgb(0xA6, 0xA6, 0xA6));
            MonthlyUploadText.FontFamily = segoe;
        }

        var outerFill = new SolidColorBrush(Color.FromRgb(0x25, 0x25, 0x26));
        var outerStroke = new SolidColorBrush(Color.FromRgb(0x00, 0x78, 0xD7));
        var innerStroke = new SolidColorBrush(Color.FromRgb(0x3E, 0x3E, 0x42));
        var labelBrush = new SolidColorBrush(Color.FromRgb(0x00, 0x99, 0xFF));
        var subBrush = new SolidColorBrush(Color.FromRgb(0x9E, 0x9E, 0x9E));

        StyleIndicator(CpuOuterShape, CpuInnerShape, CpuLabel, CpuText, CpuTemperatureText,
            outerFill, outerStroke, 1.5, Brushes.Transparent, innerStroke, 1, labelBrush, Brushes.White, subBrush, segoe);
        StyleIndicator(RamOuterShape, RamInnerShape, RamLabel, RamText, RamDetailsText,
            outerFill, outerStroke, 1.5, Brushes.Transparent, innerStroke, 1, labelBrush, Brushes.White, subBrush, segoe);
        StyleIndicator(NetworkOuterShape, NetworkInnerShape, NetworkLabel, DownloadText, UploadText,
            outerFill, outerStroke, 1.5, Brushes.Transparent, innerStroke, 1, labelBrush, Brushes.White, subBrush, segoe);
        StyleIndicator(DiskOuterShape, DiskInnerShape, DiskLabel, DiskText, DiskSubLabel,
            outerFill, outerStroke, 1.5, Brushes.Transparent, innerStroke, 1, labelBrush, Brushes.White, new SolidColorBrush(Color.FromRgb(0x66, 0x66, 0x66)), segoe);
    }

    private static void StyleIndicator(
        Ellipse outer,
        Ellipse inner,
        TextBlock label,
        TextBlock main,
        TextBlock? sub,
        Brush outerFill,
        Brush outerStroke,
        double outerThickness,
        Brush innerFill,
        Brush innerStroke,
        double innerThickness,
        Brush labelBrush,
        Brush mainBrush,
        Brush subBrush,
        FontFamily font)
    {
        if (outer != null)
        {
            outer.Fill = outerFill;
            outer.Stroke = outerStroke;
            outer.StrokeThickness = outerThickness;
        }

        if (inner != null)
        {
            inner.Fill = innerFill;
            inner.Stroke = innerStroke;
            inner.StrokeThickness = innerThickness;
        }

        if (label != null)
        {
            label.Foreground = labelBrush;
            label.FontFamily = font;
        }

        if (main != null)
        {
            main.Foreground = mainBrush;
            main.FontFamily = font;
        }

        if (sub != null)
        {
            sub.Foreground = subBrush;
            sub.FontFamily = font;
        }
    }

    private static LinearGradientBrush CreateXpTitleBarBrush()
    {
        var brush = new LinearGradientBrush
        {
            StartPoint = new Point(0, 0),
            EndPoint = new Point(0, 1)
        };
        brush.GradientStops.Add(new GradientStop(Color.FromRgb(0x00, 0x58, 0xEE), 0.0));
        brush.GradientStops.Add(new GradientStop(Color.FromRgb(0x3B, 0x8C, 0xF8), 0.12));
        brush.GradientStops.Add(new GradientStop(Color.FromRgb(0x1F, 0x69, 0xE9), 0.3));
        brush.GradientStops.Add(new GradientStop(Color.FromRgb(0x00, 0x50, 0xE0), 0.8));
        brush.GradientStops.Add(new GradientStop(Color.FromRgb(0x00, 0x2E, 0xA5), 1.0));
        return brush;
    }

    private static LinearGradientBrush CreateXpCloseButtonBrush()
    {
        var brush = new LinearGradientBrush
        {
            StartPoint = new Point(0, 0),
            EndPoint = new Point(0, 1)
        };
        brush.GradientStops.Add(new GradientStop(Color.FromRgb(0xEB, 0x7C, 0x56), 0.0));
        brush.GradientStops.Add(new GradientStop(Color.FromRgb(0xE0, 0x48, 0x28), 0.3));
        brush.GradientStops.Add(new GradientStop(Color.FromRgb(0xC7, 0x39, 0x1F), 0.8));
        brush.GradientStops.Add(new GradientStop(Color.FromRgb(0x9E, 0x20, 0x0D), 1.0));
        return brush;
    }

    private static LinearGradientBrush CreateXpButtonBrush()
    {
        var brush = new LinearGradientBrush
        {
            StartPoint = new Point(0, 0),
            EndPoint = new Point(0, 1)
        };
        brush.GradientStops.Add(new GradientStop(Color.FromRgb(0x42, 0x93, 0xF9), 0.0));
        brush.GradientStops.Add(new GradientStop(Color.FromRgb(0x24, 0x68, 0xD4), 1.0));
        return brush;
    }

    private static LinearGradientBrush CreateWin7AeroBackgroundBrush()
    {
        var brush = new LinearGradientBrush
        {
            StartPoint = new Point(0, 0),
            EndPoint = new Point(0, 1)
        };
        brush.GradientStops.Add(new GradientStop(Color.FromArgb(0x95, 0x1C, 0x3C, 0x60), 0.0));
        brush.GradientStops.Add(new GradientStop(Color.FromArgb(0xB0, 0x0E, 0x24, 0x3D), 0.45));
        brush.GradientStops.Add(new GradientStop(Color.FromArgb(0xC5, 0x08, 0x18, 0x2A), 0.5));
        brush.GradientStops.Add(new GradientStop(Color.FromArgb(0xE0, 0x05, 0x10, 0x1E), 1.0));
        return brush;
    }

    private static LinearGradientBrush CreateWin7AeroBorderBrush()
    {
        var brush = new LinearGradientBrush
        {
            StartPoint = new Point(0, 0),
            EndPoint = new Point(0, 1)
        };
        brush.GradientStops.Add(new GradientStop(Color.FromArgb(0xCC, 0xFF, 0xFF, 0xFF), 0.0));
        brush.GradientStops.Add(new GradientStop(Color.FromArgb(0x99, 0x52, 0xD3, 0xFF), 0.5));
        brush.GradientStops.Add(new GradientStop(Color.FromArgb(0x66, 0x1A, 0x5A, 0x99), 1.0));
        return brush;
    }

    private static LinearGradientBrush CreateWin7SeparatorBrush()
    {
        var brush = new LinearGradientBrush
        {
            StartPoint = new Point(0, 0),
            EndPoint = new Point(1, 0)
        };
        brush.GradientStops.Add(new GradientStop(Color.FromArgb(0x00, 0x52, 0xD3, 0xFF), 0.0));
        brush.GradientStops.Add(new GradientStop(Color.FromArgb(0xAA, 0x52, 0xD3, 0xFF), 0.5));
        brush.GradientStops.Add(new GradientStop(Color.FromArgb(0x00, 0x52, 0xD3, 0xFF), 1.0));
        return brush;
    }

    // =========================================
    // DISTRIBUCIÓN DE INDICADORES
    // =========================================
    private void UpdateIndicatorLayout()
    {
        if (MonthlyNetworkContainer != null)
        {
            MonthlyNetworkContainer.Visibility = _settings.ShowMonthlyNetwork
                ? Visibility.Visible
                : Visibility.Collapsed;
        }

        if (NetworkPanel == null || DiskPanel == null)
            return;

        bool showNetwork = _settings.ShowNetwork;
        bool showDisk = _settings.ShowDisk;

        int optionalCount = (showNetwork ? 1 : 0) + (showDisk ? 1 : 0);

        // SOLO CPU + RAM
        if (optionalCount == 0)
        {
            NetworkPanel.Visibility = Visibility.Collapsed;
            DiskPanel.Visibility = Visibility.Collapsed;
        }
        // CPU + RAM + UN INDICADOR
        else if (optionalCount == 1)
        {
            if (showNetwork)
            {
                NetworkPanel.Visibility = Visibility.Visible;
                Grid.SetRow(NetworkPanel, 1);
                Grid.SetColumn(NetworkPanel, 0);
                Grid.SetColumnSpan(NetworkPanel, 2);
                NetworkPanel.HorizontalAlignment = HorizontalAlignment.Center;
                DiskPanel.Visibility = Visibility.Collapsed;
            }
            else
            {
                DiskPanel.Visibility = Visibility.Visible;
                Grid.SetRow(DiskPanel, 1);
                Grid.SetColumn(DiskPanel, 0);
                Grid.SetColumnSpan(DiskPanel, 2);
                DiskPanel.HorizontalAlignment = HorizontalAlignment.Center;
                NetworkPanel.Visibility = Visibility.Collapsed;
            }
        }
        // LOS 4 INDICADORES
        else
        {
            NetworkPanel.Visibility = Visibility.Visible;
            Grid.SetRow(NetworkPanel, 1);
            Grid.SetColumn(NetworkPanel, 0);
            Grid.SetColumnSpan(NetworkPanel, 1);
            NetworkPanel.HorizontalAlignment = HorizontalAlignment.Center;

            DiskPanel.Visibility = Visibility.Visible;
            Grid.SetRow(DiskPanel, 1);
            Grid.SetColumn(DiskPanel, 1);
            Grid.SetColumnSpan(DiskPanel, 1);
            DiskPanel.HorizontalAlignment = HorizontalAlignment.Center;
        }

        UpdateLayout();
        EnsureWindowWithinBounds();
    }

    // =========================================
    // LIMITES DE PANTALLA (COMPATIBLE MULTI-MONITOR)
    // =========================================
    private void EnsureWindowWithinBounds()
    {
        double vLeft = SystemParameters.VirtualScreenLeft;
        double vTop = SystemParameters.VirtualScreenTop;
        double vWidth = SystemParameters.VirtualScreenWidth;
        double vHeight = SystemParameters.VirtualScreenHeight;

        double vRight = vLeft + vWidth;
        double vBottom = vTop + vHeight;

        // Solo reubicar si la ventana quedó totalmente fuera de TODOS los monitores conectados
        if (ActualWidth > 0 && ActualHeight > 0)
        {
            if (Left + ActualWidth < vLeft + 20 || Left > vRight - 20 ||
                Top + ActualHeight < vTop + 20 || Top > vBottom - 20)
            {
                var workArea = SystemParameters.WorkArea;
                Left = workArea.Right - ActualWidth - 20;
                Top = workArea.Top + 20;
                _settings.Left = Left;
                _settings.Top = Top;
                _settingsManager.Save(_settings);
            }
        }
    }

    // =========================================
    // ATAJO
    // =========================================
    private void RegisterHotkey()
    {
        _hotkeyManager.Unregister(this, HotkeyId);

        if (!_hotkeyManager.Register(
                this,
                HotkeyId,
                _settings.HotkeyModifiers,
                _settings.HotkeyKey))
        {
            MessageBox.Show(
                "No se pudo registrar el atajo. Puede que otra aplicación ya lo esté utilizando.",
                "CPU Monitor",
                MessageBoxButton.OK,
                MessageBoxImage.Warning);
        }

        _hotkeyManager.HotkeyPressed -= HotkeyManager_HotkeyPressed;
        _hotkeyManager.HotkeyPressed += HotkeyManager_HotkeyPressed;
    }

    private void HotkeyManager_HotkeyPressed(object? sender, EventArgs e)
    {
        Visibility = Visibility == Visibility.Visible
            ? Visibility.Hidden
            : Visibility.Visible;
    }

    // =========================================
    // ARRASTRAR
    // =========================================
    private void RootBorder_MouseLeftButtonDown(object sender, MouseButtonEventArgs e)
    {
        if (e.ChangedButton == MouseButton.Left)
        {
            DragMove();
            _settings.Left = Left;
            _settings.Top = Top;
            _settingsManager.Save(_settings);
        }
    }

    // =========================================
    // CONFIGURACIÓN
    // =========================================
    private void SettingsButton_Click(object sender, RoutedEventArgs e)
    {
        if (_settingsOpen)
            return;

        _settingsOpen = true;

        // Asegurar que las coordenadas actuales se transfieran al diálogo
        _settings.Left = Left;
        _settings.Top = Top;

        var dialog = new SettingsWindow(
            _settings,
            _settingsManager.GetHotkeyText(_settings))
        {
            Owner = this
        };

        if (dialog.ShowDialog() == true)
        {
            _settings = dialog.Settings;
            _settings.Left = Left;
            _settings.Top = Top;
            _settingsManager.Save(_settings);
            ApplySettings();
            RegisterHotkey();
        }

        _settingsOpen = false;
    }

    // =========================================
    // BANDEJA DEL SISTEMA (SYSTEM TRAY)
    // =========================================
    private void InitializeTrayIcon()
    {
        try
        {
            _notifyIcon = new System.Windows.Forms.NotifyIcon
            {
                Text = "CPU Monitor",
                Visible = true
            };

            // Cargar icono desde recursos
            try
            {
                var iconUri = new Uri("pack://application:,,,/Assets/app.ico");
                var streamInfo = Application.GetResourceStream(iconUri);
                if (streamInfo != null)
                {
                    _notifyIcon.Icon = new System.Drawing.Icon(streamInfo.Stream);
                }
                else
                {
                    _notifyIcon.Icon = System.Drawing.SystemIcons.Application;
                }
            }
            catch
            {
                _notifyIcon.Icon = System.Drawing.SystemIcons.Application;
            }

            // Clic izquierdo en el icono de la bandeja
            _notifyIcon.MouseClick += (s, e) =>
            {
                if (e.Button == System.Windows.Forms.MouseButtons.Left)
                {
                    ToggleWindowVisibility();
                }
            };

            _notifyIcon.DoubleClick += (s, e) =>
            {
                ToggleWindowVisibility();
            };

            // Menú contextual en segundo plano (clic derecho)
            var contextMenu = new System.Windows.Forms.ContextMenuStrip();

            var showHideItem = new System.Windows.Forms.ToolStripMenuItem("Mostrar / Ocultar");
            showHideItem.Click += (s, e) => ToggleWindowVisibility();

            var settingsItem = new System.Windows.Forms.ToolStripMenuItem("Configuración...");
            settingsItem.Click += (s, e) =>
            {
                Dispatcher.Invoke(() =>
                {
                    if (Visibility != Visibility.Visible)
                    {
                        Visibility = Visibility.Visible;
                        Activate();
                    }
                    SettingsButton_Click(this, new RoutedEventArgs());
                });
            };

            var exitItem = new System.Windows.Forms.ToolStripMenuItem("Salir");
            exitItem.Click += (s, e) =>
            {
                Dispatcher.Invoke(() =>
                {
                    ExitApplication();
                });
            };

            contextMenu.Items.Add(showHideItem);
            contextMenu.Items.Add(settingsItem);
            contextMenu.Items.Add(new System.Windows.Forms.ToolStripSeparator());
            contextMenu.Items.Add(exitItem);

            _notifyIcon.ContextMenuStrip = contextMenu;
        }
        catch
        {
        }
    }

    private void ToggleWindowVisibility()
    {
        Dispatcher.Invoke(() =>
        {
            if (Visibility == Visibility.Visible)
            {
                Visibility = Visibility.Hidden;
            }
            else
            {
                Visibility = Visibility.Visible;
                Activate();
                Focus();
            }
        });
    }

    private void ExitApplication()
    {
        _allowClose = true;
        Close();
        Application.Current.Shutdown();
    }

    // =========================================
    // CERRAR (MINIMIZAR A BANDEJA EN SEGUNDO PLANO)
    // =========================================
    private void CloseButton_Click(object sender, RoutedEventArgs e)
    {
        // Al presionar el botón cerrar se oculta a la bandeja del sistema
        Visibility = Visibility.Hidden;
    }

    // =========================================
    // OCULTAR DE ALT + TAB (WS_EX_TOOLWINDOW)
    // =========================================
    private const int GWL_EXSTYLE = -20;
    private const int WS_EX_TOOLWINDOW = 0x00000080;
    private const int WS_EX_APPWINDOW = 0x00040000;

    [System.Runtime.InteropServices.DllImport("user32.dll", EntryPoint = "GetWindowLongPtr", SetLastError = true)]
    private static extern IntPtr GetWindowLongPtr64(IntPtr hWnd, int nIndex);

    [System.Runtime.InteropServices.DllImport("user32.dll", EntryPoint = "GetWindowLong", SetLastError = true)]
    private static extern int GetWindowLong32(IntPtr hWnd, int nIndex);

    [System.Runtime.InteropServices.DllImport("user32.dll", EntryPoint = "SetWindowLongPtr", SetLastError = true)]
    private static extern IntPtr SetWindowLongPtr64(IntPtr hWnd, int nIndex, IntPtr dwNewLong);

    [System.Runtime.InteropServices.DllImport("user32.dll", EntryPoint = "SetWindowLong", SetLastError = true)]
    private static extern int SetWindowLong32(IntPtr hWnd, int nIndex, int dwNewLong);

    private static IntPtr GetWindowLongPtr(IntPtr hWnd, int nIndex)
    {
        if (IntPtr.Size == 8)
            return GetWindowLongPtr64(hWnd, nIndex);
        return (IntPtr)GetWindowLong32(hWnd, nIndex);
    }

    private static IntPtr SetWindowLongPtr(IntPtr hWnd, int nIndex, IntPtr dwNewLong)
    {
        if (IntPtr.Size == 8)
            return SetWindowLongPtr64(hWnd, nIndex, dwNewLong);
        return (IntPtr)SetWindowLong32(hWnd, nIndex, dwNewLong.ToInt32());
    }

    // =========================================
    // HOTKEY WINDOWS Y CONFIGURACIÓN DE VENTANA
    // =========================================
    protected override void OnSourceInitialized(EventArgs e)
    {
        base.OnSourceInitialized(e);
        _hotkeyManager.Initialize(this);

        // Ocultar ventana del menú Alt + Tab de Windows
        try
        {
            var helper = new System.Windows.Interop.WindowInteropHelper(this);
            IntPtr hwnd = helper.Handle;
            long exStyle = GetWindowLongPtr(hwnd, GWL_EXSTYLE).ToInt64();
            exStyle = (exStyle | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW;
            SetWindowLongPtr(hwnd, GWL_EXSTYLE, (IntPtr)exStyle);
        }
        catch
        {
        }
    }

    // =========================================
    // CERRAR VENTANA
    // =========================================
    private void Window_Closing(object? sender, CancelEventArgs e)
    {
        if (!_allowClose)
        {
            e.Cancel = true;
            Visibility = Visibility.Hidden;
            return;
        }

        _settings.Left = Left;
        _settings.Top = Top;

        _settingsManager.Save(_settings);

        _timer.Stop();
        _hotkeyManager.Unregister(this, HotkeyId);
        _monitor.Dispose();

        if (_notifyIcon != null)
        {
            _notifyIcon.Visible = false;
            _notifyIcon.Dispose();
            _notifyIcon = null;
        }
    }
}