# CPU Monitor para Windows

Widget ligero para Windows hecho con C# + WPF + .NET.

## Características

- Monitor de CPU.
- Monitor de RAM.
- Ventana sin bordes.
- Transparencia configurable.
- Siempre encima configurable.
- Se puede mover arrastrándolo.
- Atajo global configurable para mostrar/ocultar.
- Inicio automático con Windows.
- Configuración guardada en `%APPDATA%\CPUMonitor\settings.json`.
- No utiliza Electron.
- No necesita conexión a Internet para funcionar.

## Requisitos para compilar

- Windows 10/11.
- .NET 10 SDK.
- Visual Studio Code.
- Extensión "C# Dev Kit" de Microsoft (recomendada).

## Compilar

Abrir una terminal en esta carpeta:

```powershell
dotnet restore
dotnet build
```

Para generar un EXE independiente:

```powershell
dotnet publish -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -o publish
```

El ejecutable estará en:

```text
publish\CPUMonitor.exe
```

## Inicio con Windows

Desde el widget:

1. Pulsar ⚙.
2. Activar "Iniciar automáticamente con Windows".
3. Guardar.

La aplicación crea una entrada en:

`HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`

No necesita permisos de administrador.

## Atajo

Por defecto:

`Ctrl + Shift + M`

Para cambiarlo:

1. Pulsar ⚙.
2. Hacer clic en el campo del atajo.
3. Presionar la combinación deseada.
4. Guardar.

La combinación debe incluir Ctrl, Alt, Shift o Windows.

## Nota

El botón X oculta/cierra el programa de forma intencional. El atajo permite volver a mostrarlo si fue ocultado con la combinación.
