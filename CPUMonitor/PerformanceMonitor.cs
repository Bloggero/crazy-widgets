using System.Diagnostics;
using System.Management;
using System.Net.NetworkInformation;
using System.Runtime.InteropServices;
using LibreHardwareMonitor.Hardware;

namespace CPUMonitor;

public sealed class PerformanceMonitor : IDisposable
{
    [StructLayout(LayoutKind.Sequential)]
    private struct FILETIME
    {
        public uint LowDateTime;
        public uint HighDateTime;

        public long ToLong() =>
            ((long)HighDateTime << 32) + LowDateTime;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct MEMORYSTATUSEX
    {
        public uint Length;
        public uint MemoryLoad;
        public ulong TotalPhys;
        public ulong AvailPhys;
        public ulong TotalPageFile;
        public ulong AvailPageFile;
        public ulong TotalVirtual;
        public ulong AvailVirtual;
        public ulong AvailExtendedVirtual;
    }

    [DllImport("kernel32.dll")]
    private static extern bool GetSystemTimes(
        out FILETIME idleTime,
        out FILETIME kernelTime,
        out FILETIME userTime);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
    private static extern bool GlobalMemoryStatusEx(
        ref MEMORYSTATUSEX lpBuffer);

    private static readonly UpdateVisitor _sharedVisitor = new();

    private readonly Computer _computer;
    private readonly bool _lhmOpened;

    private long _previousIdle;
    private long _previousKernel;
    private long _previousUser;
    private bool _hasPreviousCpu;

    // =========================================
    // RED
    // =========================================
    private long _previousBytesReceived;
    private long _previousBytesSent;
    private DateTime _previousNetworkTime;
    private bool _hasPreviousNetwork;

    // =========================================
    // DISCO
    // =========================================
    private PerformanceCounter? _diskCounter;

    // =========================================
    // WMI FALLBACK CACHE
    // =========================================
    private DateTime _lastWmiCheck = DateTime.MinValue;
    private double _lastWmiTemperature;
    private string _lastWmiSource = "";

    public string TemperatureDebug { get; private set; } = "";
    public string TemperatureSource { get; private set; } = "Iniciando...";

    public PerformanceMonitor()
    {
        _computer = new Computer
        {
            IsCpuEnabled = true,
            IsMotherboardEnabled = true,
            IsGpuEnabled = true
        };

        try
        {
            _computer.Open();
            _lhmOpened = true;
        }
        catch (Exception ex)
        {
            _lhmOpened = false;
            TemperatureDebug = $"Error al abrir LibreHardwareMonitor: {ex.Message}";
        }

        // Inicializar contador de disco con fallback seguro
        try
        {
            _diskCounter = new PerformanceCounter(
                "PhysicalDisk",
                "% Disk Time",
                "_Total",
                true);

            _diskCounter.NextValue();
        }
        catch
        {
            _diskCounter = null;
        }

        _previousNetworkTime = DateTime.UtcNow;
    }

    // =========================================
    // ESTADÍSTICAS COMPLETAS
    // =========================================
    public PerformanceStats GetStats()
    {
        double cpu = GetCpuUsage();

        // RAM
        double ram = 0;
        double totalGb = 0;
        double usedGb = 0;

        var memory = new MEMORYSTATUSEX
        {
            Length = (uint)Marshal.SizeOf<MEMORYSTATUSEX>()
        };

        if (GlobalMemoryStatusEx(ref memory))
        {
            ram = memory.MemoryLoad;
            totalGb = memory.TotalPhys / 1024d / 1024d / 1024d;
            usedGb = (memory.TotalPhys - memory.AvailPhys) / 1024d / 1024d / 1024d;
        }

        // TEMPERATURA (CPU, GPU, Placa Base o WMI)
        GetSystemTemperatures(
            out double cpuTemp,
            out double gpuTemp,
            out string tempSource);

        // RED
        GetNetworkUsage(
            out double downloadMbps,
            out double uploadMbps);

        // DISCO
        double diskUsage = GetDiskUsage();

        return new PerformanceStats(
            cpu,
            ram,
            usedGb,
            totalGb,
            cpuTemp,
            gpuTemp,
            tempSource,
            downloadMbps,
            uploadMbps,
            diskUsage);
    }

    // =========================================
    // CPU USAGE
    // =========================================
    private double GetCpuUsage()
    {
        if (!GetSystemTimes(out var idle, out var kernel, out var user))
            return 0;

        long idleNow = idle.ToLong();
        long kernelNow = kernel.ToLong();
        long userNow = user.ToLong();

        if (!_hasPreviousCpu)
        {
            _previousIdle = idleNow;
            _previousKernel = kernelNow;
            _previousUser = userNow;
            _hasPreviousCpu = true;
            return 0;
        }

        long idleDelta = idleNow - _previousIdle;
        long kernelDelta = kernelNow - _previousKernel;
        long userDelta = userNow - _previousUser;

        _previousIdle = idleNow;
        _previousKernel = kernelNow;
        _previousUser = userNow;

        long total = kernelDelta + userDelta;
        if (total <= 0)
            return 0;

        double usage = (total - idleDelta) * 100.0 / total;
        return Math.Clamp(usage, 0, 100);
    }

    // =========================================
    // RED USAGE
    // =========================================
    private void GetNetworkUsage(out double downloadMbps, out double uploadMbps)
    {
        downloadMbps = 0;
        uploadMbps = 0;

        try
        {
            long totalReceived = 0;
            long totalSent = 0;

            foreach (NetworkInterface nic in NetworkInterface.GetAllNetworkInterfaces())
            {
                if (nic.OperationalStatus != OperationalStatus.Up)
                    continue;

                if (nic.NetworkInterfaceType == NetworkInterfaceType.Loopback ||
                    nic.NetworkInterfaceType == NetworkInterfaceType.Tunnel)
                    continue;

                IPv4InterfaceStatistics stats = nic.GetIPv4Statistics();
                totalReceived += stats.BytesReceived;
                totalSent += stats.BytesSent;
            }

            DateTime now = DateTime.UtcNow;

            if (!_hasPreviousNetwork)
            {
                _previousBytesReceived = totalReceived;
                _previousBytesSent = totalSent;
                _previousNetworkTime = now;
                _hasPreviousNetwork = true;
                return;
            }

            double seconds = (now - _previousNetworkTime).TotalSeconds;
            if (seconds <= 0)
                return;

            long receivedDelta = Math.Max(0, totalReceived - _previousBytesReceived);
            long sentDelta = Math.Max(0, totalSent - _previousBytesSent);

            downloadMbps = receivedDelta * 8d / seconds / 1_000_000d;
            uploadMbps = sentDelta * 8d / seconds / 1_000_000d;

            _previousBytesReceived = totalReceived;
            _previousBytesSent = totalSent;
            _previousNetworkTime = now;
        }
        catch
        {
            downloadMbps = 0;
            uploadMbps = 0;
        }
    }

    // =========================================
    // DISK USAGE
    // =========================================
    private double GetDiskUsage()
    {
        try
        {
            if (_diskCounter == null)
                return 0;

            float value = _diskCounter.NextValue();
            if (float.IsNaN(value) || float.IsInfinity(value))
                return 0;

            return Math.Clamp(value, 0, 100);
        }
        catch
        {
            return 0;
        }
    }

    // =========================================
    // TEMPERATURA ROBUSTA (MULTIFUENTE + FALLBACK)
    // =========================================
    private void GetSystemTemperatures(
        out double cpuTemp,
        out double gpuTemp,
        out string source)
    {
        cpuTemp = 0;
        gpuTemp = 0;
        source = "";

        if (_lhmOpened)
        {
            try
            {
                _computer.Accept(_sharedVisitor);

                double bestCpuPackage = 0;
                double maxCpuCore = 0;
                double sumCpuCore = 0;
                int coreCount = 0;

                double bestMoboTemp = 0;
                double bestGpuTemp = 0;
                string gpuName = "";

                foreach (IHardware hw in _computer.Hardware)
                {
                    switch (hw.HardwareType)
                    {
                        case HardwareType.Cpu:
                            ProcessCpuHardware(hw, ref bestCpuPackage, ref maxCpuCore, ref sumCpuCore, ref coreCount);
                            break;

                        case HardwareType.Motherboard:
                            ProcessMoboHardware(hw, ref bestMoboTemp);
                            break;

                        case HardwareType.GpuNvidia:
                        case HardwareType.GpuAmd:
                        case HardwareType.GpuIntel:
                            ProcessGpuHardware(hw, ref bestGpuTemp, ref gpuName);
                            break;
                    }
                }

                // Determinar la mejor temperatura de CPU
                if (bestCpuPackage > 0)
                {
                    cpuTemp = bestCpuPackage;
                    source = "CPU (Package / Tctl)";
                }
                else if (maxCpuCore > 0)
                {
                    cpuTemp = maxCpuCore;
                    source = "CPU (Core Max)";
                }
                else if (coreCount > 0 && sumCpuCore > 0)
                {
                    cpuTemp = sumCpuCore / coreCount;
                    source = "CPU (Core Promedio)";
                }
                else if (bestMoboTemp > 0)
                {
                    cpuTemp = bestMoboTemp;
                    source = "Motherboard (CPU Socket)";
                }

                if (bestGpuTemp > 0)
                {
                    gpuTemp = bestGpuTemp;
                    if (cpuTemp <= 0)
                    {
                        // Si la CPU no tiene sensor legible (sin admin), mostrar temperatura GPU
                        cpuTemp = bestGpuTemp;
                        source = string.IsNullOrEmpty(gpuName) ? "GPU Core" : $"GPU ({gpuName})";
                    }
                }
            }
            catch (Exception ex)
            {
                TemperatureDebug = $"Error al leer LHM: {ex.Message}";
            }
        }

        // =========================================
        // FALLBACK WMI SI AÚN NO HAY TEMPERATURA
        // =========================================
        if (cpuTemp <= 0)
        {
            double wmiTemp = GetWmiThermalZoneTemperature(out string wmiSrc);
            if (wmiTemp > 0)
            {
                cpuTemp = wmiTemp;
                source = wmiSrc;
            }
            else
            {
                source = "Sin sensor (Ejecutar como Administrador)";
            }
        }

        TemperatureSource = source;
    }

    private static void ProcessCpuHardware(
        IHardware hw,
        ref double bestCpuPackage,
        ref double maxCpuCore,
        ref double sumCpuCore,
        ref int coreCount)
    {
        foreach (ISensor sensor in hw.Sensors)
        {
            if (sensor.SensorType != SensorType.Temperature || !sensor.Value.HasValue)
                continue;

            double val = sensor.Value.Value;
            if (val <= 5 || val > 125)
                continue;

            string name = sensor.Name.ToLowerInvariant();

            if (name.Contains("package") || name.Contains("tctl") || name.Contains("tdie") || name.Contains("total"))
            {
                if (val > bestCpuPackage)
                    bestCpuPackage = val;
            }
            else if (name.Contains("core max") || name.Contains("ccd"))
            {
                if (val > bestCpuPackage)
                    bestCpuPackage = val;
            }
            else if (name.Contains("core") || name.Contains("cpu"))
            {
                if (val > maxCpuCore)
                    maxCpuCore = val;

                sumCpuCore += val;
                coreCount++;
            }
        }

        foreach (IHardware sub in hw.SubHardware)
        {
            ProcessCpuHardware(sub, ref bestCpuPackage, ref maxCpuCore, ref sumCpuCore, ref coreCount);
        }
    }

    private static void ProcessMoboHardware(IHardware hw, ref double bestMoboTemp)
    {
        foreach (ISensor sensor in hw.Sensors)
        {
            if (sensor.SensorType != SensorType.Temperature || !sensor.Value.HasValue)
                continue;

            double val = sensor.Value.Value;
            if (val <= 10 || val > 115)
                continue;

            string name = sensor.Name.ToLowerInvariant();
            if (name.Contains("cpu") || name.Contains("system") || name.Contains("temp #1"))
            {
                if (val > bestMoboTemp)
                    bestMoboTemp = val;
            }
        }

        foreach (IHardware sub in hw.SubHardware)
        {
            ProcessMoboHardware(sub, ref bestMoboTemp);
        }
    }

    private static void ProcessGpuHardware(IHardware hw, ref double bestGpuTemp, ref string gpuName)
    {
        foreach (ISensor sensor in hw.Sensors)
        {
            if (sensor.SensorType != SensorType.Temperature || !sensor.Value.HasValue)
                continue;

            double val = sensor.Value.Value;
            if (val <= 10 || val > 120)
                continue;

            string name = sensor.Name.ToLowerInvariant();
            if (name.Contains("core") || name.Contains("gpu") || name.Contains("temperature"))
            {
                if (val > bestGpuTemp)
                {
                    bestGpuTemp = val;
                    gpuName = hw.Name;
                }
            }
        }
    }

    // =========================================
    // FALLBACK WMI (ACPI Thermal Zone)
    // =========================================
    private double GetWmiThermalZoneTemperature(out string source)
    {
        // Consultar WMI cada 2 segundos máximo para no sobrecargar el subsistema WMI
        if ((DateTime.UtcNow - _lastWmiCheck).TotalSeconds < 2.0 && _lastWmiTemperature > 0)
        {
            source = _lastWmiSource;
            return _lastWmiTemperature;
        }

        _lastWmiCheck = DateTime.UtcNow;
        source = "";

        try
        {
            using var searcher = new ManagementObjectSearcher(
                @"root\WMI",
                "SELECT CurrentTemperature FROM MSAcpi_ThermalZoneTemperature");

            foreach (ManagementObject obj in searcher.Get())
            {
                if (obj["CurrentTemperature"] is uint tempTenthsKelvin && tempTenthsKelvin > 2732)
                {
                    double celsius = (tempTenthsKelvin - 2732) / 10.0;
                    if (celsius is > 10 and < 125)
                    {
                        _lastWmiTemperature = celsius;
                        _lastWmiSource = "ACPI Thermal Zone (WMI)";
                        source = _lastWmiSource;
                        return celsius;
                    }
                }
            }
        }
        catch
        {
            // Intentar WMI CIMv2 PerfFormattedData
            try
            {
                using var searcher2 = new ManagementObjectSearcher(
                    @"root\cimv2",
                    "SELECT Temperature FROM Win32_PerfFormattedData_Counters_ThermalZoneInformation");

                foreach (ManagementObject obj in searcher2.Get())
                {
                    if (obj["Temperature"] is uint tempKelvin && tempKelvin > 273)
                    {
                        double celsius = tempKelvin - 273.15;
                        if (celsius is > 10 and < 125)
                        {
                            _lastWmiTemperature = celsius;
                            _lastWmiSource = "Thermal Zone (WMI)";
                            source = _lastWmiSource;
                            return celsius;
                        }
                    }
                }
            }
            catch
            {
            }
        }

        return 0;
    }

    // =========================================
    // DISPOSE
    // =========================================
    public void Dispose()
    {
        try
        {
            _diskCounter?.Dispose();
        }
        catch
        {
        }

        try
        {
            if (_lhmOpened)
                _computer.Close();
        }
        catch
        {
        }
    }
}

// =============================================
// RECORD STRUCT ESTADÍSTICAS
// =============================================
public readonly record struct PerformanceStats(
    double CpuUsage,
    double RamUsage,
    double UsedRamGb,
    double TotalRamGb,
    double CpuTemperature,
    double GpuTemperature,
    string TemperatureSource,
    double DownloadMbps,
    double UploadMbps,
    double DiskUsage);

// =============================================
// VISITOR REUTILIZABLE (ZERO ALLOC)
// =============================================
internal sealed class UpdateVisitor : IVisitor
{
    public void VisitComputer(IComputer computer)
    {
        computer.Traverse(this);
    }

    public void VisitHardware(IHardware hardware)
    {
        hardware.Update();

        foreach (IHardware subHardware in hardware.SubHardware)
        {
            subHardware.Accept(this);
        }
    }

    public void VisitParameter(IParameter parameter)
    {
    }

    public void VisitSensor(ISensor sensor)
    {
    }
}