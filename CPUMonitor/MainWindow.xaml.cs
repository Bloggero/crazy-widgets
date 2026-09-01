using System.ComponentModel;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Threading;

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
                string tooltipText = $"Temperatura: {stats.CpuTemperature:0.1}°C\nFuente: {stats.TemperatureSource}";
                if (stats.GpuTemperature > 0)
                {
                    tooltipText += $"\nGPU: {stats.GpuTemperature:0.1}°C";
                }
                CpuPanel.ToolTip = tooltipText;
                UpdateTemperatureColor(stats.CpuTemperature);
            }
            else
            {
                CpuTemperatureText.Text = "--°C";
                CpuPanel.ToolTip = $"Sin lectura de temperatura.\n{stats.TemperatureSource}\nEjecutar como Administrador para lectura completa de hardware.";
                CpuTemperatureText.Foreground = Brushes.White;
            }

            // RAM
            RamText.Text = $"{stats.RamUsage:0}%";
            RamDetailsText.Text = $"{stats.UsedRamGb:0.0} / {stats.TotalRamGb:0.0} GB";
            RamPanel.ToolTip = $"RAM: {stats.RamUsage:0}% ({stats.UsedRamGb:0.2} GB de {stats.TotalRamGb:0.2} GB)";

            // NETWORK
            DownloadText.Text = $"↓ {FormatNetworkSpeed(stats.DownloadMbps)}";
            UploadText.Text = $"↑ {FormatNetworkSpeed(stats.UploadMbps)}";
            NetworkPanel.ToolTip = $"Descarga: {FormatNetworkSpeed(stats.DownloadMbps)}\nSubida: {FormatNetworkSpeed(stats.UploadMbps)}";

            // DISK
            DiskText.Text = $"{stats.DiskUsage:0}%";
            DiskPanel.ToolTip = $"Actividad de Disco: {stats.DiskUsage:0}%";
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
            CpuTemperatureText.Foreground = Brushes.White;
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
        if (ThemeBackgroundContainer == null)
            return;

        if (string.Equals(_settings.Theme, "SpeedRunners", StringComparison.OrdinalIgnoreCase))
        {
            ThemeBackgroundContainer.Visibility = Visibility.Visible;
            RootBorder.Background = new SolidColorBrush(Color.FromArgb(0xFA, 0x0A, 0x0E, 0x1A));
            RootBorder.BorderBrush = new SolidColorBrush(Color.FromArgb(0xCC, 0x38, 0x9B, 0xEC));
        }
        else
        {
            ThemeBackgroundContainer.Visibility = Visibility.Collapsed;
            RootBorder.Background = new SolidColorBrush(Color.FromArgb(0xE6, 0x11, 0x11, 0x11));
            RootBorder.BorderBrush = new SolidColorBrush(Color.FromArgb(0x55, 0xFF, 0xFF, 0xFF));
        }
    }

    // =========================================
    // DISTRIBUCIÓN DE INDICADORES
    // =========================================
    private void UpdateIndicatorLayout()
    {
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
    // CERRAR
    // =========================================
    private void CloseButton_Click(object sender, RoutedEventArgs e)
    {
        _allowClose = true;
        Close();
    }

    // =========================================
    // HOTKEY WINDOWS
    // =========================================
    protected override void OnSourceInitialized(EventArgs e)
    {
        base.OnSourceInitialized(e);
        _hotkeyManager.Initialize(this);
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
    }
}