using System.IO;
using System.Text.Json;

namespace CPUMonitor;

public sealed class AppSettings
{
    public double Opacity { get; set; } = 0.82;

    public bool AlwaysOnTop { get; set; } = true;

    public bool StartWithWindows { get; set; } = false;

    public double Left { get; set; } = double.NaN;

    public double Top { get; set; } = double.NaN;

    // =========================================
    // INDICADORES
    // =========================================

    // CPU y RAM siempre se muestran.

    public bool ShowNetwork { get; set; } = true;

    public bool ShowDisk { get; set; } = true;

    public bool ShowMonthlyNetwork { get; set; } = true;


    // =========================================
    // TEMA
    // =========================================

    public string Theme { get; set; } = "Default";

    // =========================================
    // ATAJO
    // =========================================

    public uint HotkeyModifiers { get; set; } =
        HotkeyManager.MOD_CONTROL |
        HotkeyManager.MOD_SHIFT;

    public uint HotkeyKey { get; set; } = 0x4D; // M
}


public sealed class SettingsManager
{
    private readonly string _folder;
    private readonly string _file;


    public SettingsManager()
    {
        _folder =
            Path.Combine(
                Environment.GetFolderPath(
                    Environment.SpecialFolder.ApplicationData),
                "CPUMonitor");

        _file =
            Path.Combine(
                _folder,
                "settings.json");
    }


    public AppSettings Load()
    {
        try
        {
            if (File.Exists(_file))
            {
                var json =
                    File.ReadAllText(_file);

                return
                    JsonSerializer.Deserialize<AppSettings>(json)
                    ?? new AppSettings();
            }
        }
        catch
        {
        }

        return new AppSettings();
    }


    public void Save(AppSettings settings)
    {
        Directory.CreateDirectory(_folder);

        var json =
            JsonSerializer.Serialize(
                settings,
                new JsonSerializerOptions
                {
                    WriteIndented = true
                });

        File.WriteAllText(
            _file,
            json);

        StartupManager.SetStartup(
            settings.StartWithWindows);
    }


    public string GetHotkeyText(
        AppSettings settings)
    {
        var parts =
            new List<string>();

        if ((settings.HotkeyModifiers &
             HotkeyManager.MOD_CONTROL) != 0)
        {
            parts.Add("Ctrl");
        }

        if ((settings.HotkeyModifiers &
             HotkeyManager.MOD_ALT) != 0)
        {
            parts.Add("Alt");
        }

        if ((settings.HotkeyModifiers &
             HotkeyManager.MOD_SHIFT) != 0)
        {
            parts.Add("Shift");
        }

        if ((settings.HotkeyModifiers &
             HotkeyManager.MOD_WIN) != 0)
        {
            parts.Add("Win");
        }

        parts.Add(
            KeyName(
                settings.HotkeyKey));

        return string.Join(
            " + ",
            parts);
    }


    private static string KeyName(
        uint key)
    {
        if (key >= 0x30 &&
            key <= 0x39)
        {
            return ((char)key).ToString();
        }

        if (key >= 0x41 &&
            key <= 0x5A)
        {
            return ((char)key).ToString();
        }

        if (key >= 0x70 &&
            key <= 0x87)
        {
            return $"F{key - 0x6F}";
        }

        return key switch
        {
            0x20 => "Space",
            0x1B => "Esc",
            0x2E => "Delete",
            0x2D => "Insert",
            _ => $"0x{key:X}"
        };
    }
}


public static class StartupManager
{
    private const string TaskName = "CPUMonitor_AutoStart";
    private const string RunKey =
        @"Software\Microsoft\Windows\CurrentVersion\Run";

    private const string AppName =
        "CPUMonitor";


    public static void SetStartup(
        bool enabled)
    {
        string exe =
            Environment.ProcessPath ?? "";

        if (string.IsNullOrEmpty(exe))
            return;

        try
        {
            if (enabled)
            {
                // Crear tarea programada al iniciar sesión con los privilegios más altos (sin aviso de UAC)
                var psi =
                    new System.Diagnostics.ProcessStartInfo
                    {
                        FileName = "schtasks.exe",
                        Arguments = $"/create /tn \"{TaskName}\" /tr \"\\\"{exe}\\\"\" /sc onlogon /rl highest /f",
                        UseShellExecute = false,
                        CreateNoWindow = true,
                        WindowStyle = System.Diagnostics.ProcessWindowStyle.Hidden
                    };

                using var p =
                    System.Diagnostics.Process.Start(psi);

                p?.WaitForExit(3000);

                // Limpiar clave de registro antigua para evitar duplicados
                using var regKey =
                    Microsoft.Win32.Registry.CurrentUser
                        .OpenSubKey(
                            RunKey,
                            true);

                regKey?.DeleteValue(
                    AppName,
                    false);
            }
            else
            {
                // Eliminar tarea programada
                var psi =
                    new System.Diagnostics.ProcessStartInfo
                    {
                        FileName = "schtasks.exe",
                        Arguments = $"/delete /tn \"{TaskName}\" /f",
                        UseShellExecute = false,
                        CreateNoWindow = true,
                        WindowStyle = System.Diagnostics.ProcessWindowStyle.Hidden
                    };

                using var p =
                    System.Diagnostics.Process.Start(psi);

                p?.WaitForExit(3000);

                // Limpiar registro si existe
                using var regKey =
                    Microsoft.Win32.Registry.CurrentUser
                        .OpenSubKey(
                            RunKey,
                            true);

                regKey?.DeleteValue(
                    AppName,
                    false);
            }
        }
        catch
        {
            // Fallback a registro de Windows
            try
            {
                using var key =
                    Microsoft.Win32.Registry.CurrentUser
                        .OpenSubKey(
                            RunKey,
                            true);

                if (key != null)
                {
                    if (enabled)
                    {
                        key.SetValue(
                            AppName,
                            $"\"{exe}\"");
                    }
                    else
                    {
                        key.DeleteValue(
                            AppName,
                            false);
                    }
                }
            }
            catch
            {
            }
        }
    }
}