# CPU & Hardware Monitor para Windows

Widget de escritorio ultra-ligero y moderno para Windows desarrollado en C# + WPF + .NET.

---

## Características

- **Monitor de CPU en Tiempo Real:** Porcentaje de uso global.
- **Monitor de Temperatura Multi-Fuente:**
  - Soporta Intel (Core / Package / Core Max) y AMD Ryzen (Tctl / Tdie / CCD).
  - Soporta GPU (NVIDIA, AMD Radeon, Intel Arc) y Placa Base (SuperIO).
  - Fallback automático a WMI (`MSAcpi_ThermalZoneTemperature` y contadores ACPI).
  - Colores dinámicos según el umbral térmico (Normal, >70°C Templado, >85°C Alerta).
- **Monitor de RAM:** Porcentaje de uso y memoria exacta en GB utilizados / totales.
- **Monitor de Red y Disco:** Descarga/Subida en tiempo real y porcentaje de actividad del disco.
- **Rendimiento Asíncrono:** La lectura de hardware se realiza en segundo plano sin congelar ni ralentizar el hilo de la interfaz gráfica.
- **Diseño Moderno & Temas:** Soporte para modo Oscuro Minimalista y tema SpeedRunners.
- **Ventana Flotante:** Sin bordes, arrastrable, transparencia configurable y modo Siempre Encima (`Topmost`).
- **Atajo Global Configurable:** Ocultar o mostrar rápidamente el widget (por defecto `Ctrl + Shift + M`).
- **Inicio Automático con Windows:** Configuración con privilegios elevados vía Programador de Tareas o Registro de Windows.
- **100% Nativo:** Sin Electron, sin consumo excesivo de RAM y sin requerir conexión a Internet.

---

## Compilación y Empaquetado Optimizado

Se incluye el script interactivo `build_all.bat` para compilar con un solo clic.

### Modos de compilación disponibles:

1. **Versión Ligera (Framework-Dependent Single-File, ~2 - 4 MB):**
   ```powershell
   dotnet publish CPUMonitor.csproj -c Release -r win-x64 --self-contained false -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -p:SatelliteResourceLanguages="en-US;es" -o publish
   ```

2. **Versión Standalone (Self-Contained Single-File Comprimido, ~45 - 55 MB):**
   ```powershell
   dotnet publish CPUMonitor.csproj -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:EnableCompressionInSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -p:SatelliteResourceLanguages="en-US;es" -o publish
   ```

El ejecutable optimizado se generará en:
```text
publish\CPUMonitor.exe
```

---

## Permisos de Administrador y Sensores

- Para la lectura precisa y completa de los registros MSR de la CPU (temperatura interna del silicio Intel/AMD), Windows requiere permisos de administrador para cargar el controlador de bajo nivel de LibreHardwareMonitor.
- El archivo `app.manifest` ya solicita elevación automática (`requireAdministrator`).
- En caso de ejecutarse sin permisos de administrador, el monitor activa automáticamente los sensores de GPU y los fallbacks ACPI/WMI del sistema.
