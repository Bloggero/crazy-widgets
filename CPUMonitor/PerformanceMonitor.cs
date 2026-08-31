using System.Diagnostics;
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

    private readonly Computer _computer;

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


    public PerformanceMonitor()
    {
        _computer = new Computer
        {
            IsCpuEnabled = true,
            IsMotherboardEnabled = true
        };

        try
        {
            _computer.Open();
        }
        catch
        {
            // Si no se puede abrir el hardware,
            // el resto del monitor seguirá funcionando.
        }


        // =====================================
        // INICIALIZAR DISCO
        // =====================================

        try
        {
            _diskCounter =
                new PerformanceCounter(
                    "PhysicalDisk",
                    "% Disk Time",
                    "_Total",
                    true);

            // Primera lectura necesaria para
            // inicializar el contador.
            _diskCounter.NextValue();
        }
        catch
        {
            _diskCounter = null;
        }


        _previousNetworkTime =
            DateTime.UtcNow;
    }


    public string TemperatureDebug { get; private set; } = "";


    // =========================================
    // ESTADÍSTICAS
    // =========================================

    public PerformanceStats GetStats()
    {
        double cpu =
            GetCpuUsage();


        // =====================================
        // RAM
        // =====================================

        double ram = 0;
        double totalGb = 0;
        double usedGb = 0;

        var memory = new MEMORYSTATUSEX
        {
            Length =
                (uint)Marshal.SizeOf<MEMORYSTATUSEX>()
        };

        if (GlobalMemoryStatusEx(ref memory))
        {
            ram =
                memory.MemoryLoad;

            totalGb =
                memory.TotalPhys /
                1024d /
                1024d /
                1024d;

            usedGb =
                (memory.TotalPhys -
                 memory.AvailPhys) /
                1024d /
                1024d /
                1024d;
        }


        // =====================================
        // TEMPERATURA
        // =====================================

        double temperature =
            GetCpuTemperature();


        // =====================================
        // RED
        // =====================================

        GetNetworkUsage(
            out double downloadMbps,
            out double uploadMbps);


        // =====================================
        // DISCO
        // =====================================

        double diskUsage =
            GetDiskUsage();


        return new PerformanceStats(
            cpu,
            ram,
            usedGb,
            totalGb,
            temperature,
            downloadMbps,
            uploadMbps,
            diskUsage);
    }


    // =========================================
    // CPU
    // =========================================

    private double GetCpuUsage()
    {
        if (!GetSystemTimes(
                out var idle,
                out var kernel,
                out var user))
        {
            return 0;
        }

        long idleNow =
            idle.ToLong();

        long kernelNow =
            kernel.ToLong();

        long userNow =
            user.ToLong();


        if (!_hasPreviousCpu)
        {
            _previousIdle =
                idleNow;

            _previousKernel =
                kernelNow;

            _previousUser =
                userNow;

            _hasPreviousCpu =
                true;

            return 0;
        }


        long idleDelta =
            idleNow -
            _previousIdle;

        long kernelDelta =
            kernelNow -
            _previousKernel;

        long userDelta =
            userNow -
            _previousUser;


        _previousIdle =
            idleNow;

        _previousKernel =
            kernelNow;

        _previousUser =
            userNow;


        long total =
            kernelDelta +
            userDelta;


        if (total <= 0)
            return 0;


        double usage =
            (total - idleDelta) *
            100.0 /
            total;


        return Math.Clamp(
            usage,
            0,
            100);
    }


    // =========================================
    // RED
    // =========================================

    private void GetNetworkUsage(
        out double downloadMbps,
        out double uploadMbps)
    {
        downloadMbps = 0;
        uploadMbps = 0;


        try
        {
            long totalReceived = 0;
            long totalSent = 0;


            foreach (
                NetworkInterface networkInterface
                in NetworkInterface.GetAllNetworkInterfaces())
            {
                if (networkInterface.OperationalStatus !=
                    OperationalStatus.Up)
                    continue;


                if (networkInterface.NetworkInterfaceType ==
                    NetworkInterfaceType.Loopback)
                    continue;


                if (networkInterface.NetworkInterfaceType ==
                    NetworkInterfaceType.Tunnel)
                    continue;


                IPv4InterfaceStatistics statistics =
                    networkInterface.GetIPv4Statistics();


                totalReceived +=
                    statistics.BytesReceived;

                totalSent +=
                    statistics.BytesSent;
            }


            DateTime now =
                DateTime.UtcNow;


            if (!_hasPreviousNetwork)
            {
                _previousBytesReceived =
                    totalReceived;

                _previousBytesSent =
                    totalSent;

                _previousNetworkTime =
                    now;

                _hasPreviousNetwork =
                    true;

                return;
            }


            double seconds =
                (now -
                 _previousNetworkTime)
                .TotalSeconds;


            if (seconds <= 0)
                return;


            long receivedDelta =
                totalReceived -
                _previousBytesReceived;

            long sentDelta =
                totalSent -
                _previousBytesSent;


            if (receivedDelta < 0)
                receivedDelta = 0;

            if (sentDelta < 0)
                sentDelta = 0;


            // =================================
            // BYTES -> MEGABITS
            // =================================

            downloadMbps =
                receivedDelta *
                8d /
                seconds /
                1_000_000d;


            uploadMbps =
                sentDelta *
                8d /
                seconds /
                1_000_000d;


            _previousBytesReceived =
                totalReceived;

            _previousBytesSent =
                totalSent;

            _previousNetworkTime =
                now;
        }
        catch
        {
            downloadMbps = 0;
            uploadMbps = 0;
        }
    }


    // =========================================
    // DISCO
    // =========================================

    private double GetDiskUsage()
    {
        try
        {
            if (_diskCounter == null)
                return 0;


            float value =
                _diskCounter.NextValue();


            if (float.IsNaN(value) ||
                float.IsInfinity(value))
            {
                return 0;
            }


            return Math.Clamp(
                value,
                0,
                100);
        }
        catch
        {
            return 0;
        }
    }


    // =========================================
    // TEMPERATURA CPU
    // =========================================

    private double GetCpuTemperature()
    {
        try
        {
            _computer.Accept(
                new UpdateVisitor());

            double highestTemperature = 0;

            var sensorsEncontrados =
                new List<string>();

            // 1. Sensores de la CPU directamente
            foreach (
                IHardware hardware
                in _computer.Hardware)
            {
                if (hardware.HardwareType !=
                    HardwareType.Cpu)
                    continue;

                CheckHardwareTemperature(
                    hardware,
                    ref highestTemperature,
                    sensorsEncontrados);
            }

            // 2. Si no se encontró en CPU, buscar en placa base
            if (highestTemperature <= 0)
            {
                foreach (
                    IHardware hardware
                    in _computer.Hardware)
                {
                    if (hardware.HardwareType !=
                        HardwareType.Motherboard)
                        continue;

                    CheckHardwareTemperature(
                        hardware,
                        ref highestTemperature,
                        sensorsEncontrados);
                }
            }

            TemperatureDebug =
                string.Join(
                    Environment.NewLine,
                    sensorsEncontrados);

            return highestTemperature;
        }
        catch (Exception ex)
        {
            TemperatureDebug =
                "ERROR: " +
                ex.Message;

            return 0;
        }
    }


    private void CheckHardwareTemperature(
        IHardware hardware,
        ref double highestTemperature,
        List<string> sensorsEncontrados)
    {
        foreach (
            ISensor sensor
            in hardware.Sensors)
        {
            if (sensor.SensorType !=
                SensorType.Temperature)
                continue;


            string valor =
                sensor.Value.HasValue
                    ? $"{sensor.Value.Value:0.0} °C"
                    : "SIN VALOR";


            sensorsEncontrados.Add(
                $"{hardware.Name} -> " +
                $"{sensor.Name} = " +
                $"{valor}");


            if (!sensor.Value.HasValue)
                continue;


            double temperature =
                sensor.Value.Value;


            if (temperature <= 0 ||
                temperature > 120)
                continue;


            if (temperature >
                highestTemperature)
            {
                highestTemperature =
                    temperature;
            }
        }


        foreach (
            IHardware subHardware
            in hardware.SubHardware)
        {
            CheckHardwareTemperature(
                subHardware,
                ref highestTemperature,
                sensorsEncontrados);
        }
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
            _computer.Close();
        }
        catch
        {
            // Ignorar errores al cerrar sensores.
        }
    }
}


// =============================================
// ESTADÍSTICAS
// =============================================

public readonly record struct PerformanceStats(
    double CpuUsage,
    double RamUsage,
    double UsedRamGb,
    double TotalRamGb,
    double CpuTemperature,
    double DownloadMbps,
    double UploadMbps,
    double DiskUsage);


// =============================================
// VISITOR
// =============================================

internal sealed class UpdateVisitor : IVisitor
{
    public void VisitComputer(
        IComputer computer)
    {
        computer.Traverse(this);
    }


    public void VisitHardware(
        IHardware hardware)
    {
        hardware.Update();


        foreach (
            IHardware subHardware
            in hardware.SubHardware)
        {
            subHardware.Accept(this);
        }
    }


    public void VisitParameter(
        IParameter parameter)
    {
    }


    public void VisitSensor(
        ISensor sensor)
    {
    }
}