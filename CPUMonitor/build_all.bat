@echo off
setlocal enabledelayedexpansion
title Compilar CPUMonitor (Optimizado)
echo ========================================================
echo       CPUMonitor - Compilacion y Optimizacion
echo ========================================================
echo.

:: Verificar dotnet
where dotnet >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    if exist "%USERPROFILE%\.dotnet\dotnet.exe" (
        set "PATH=%USERPROFILE%\.dotnet;%PATH%"
    ) else (
        echo [ERROR] .NET SDK no fue encontrado en PATH.
        echo Asegurate de tener instalado .NET 8, 9 o 10 SDK.
        pause
        exit /b 1
    )
)

echo Selecciona el modo de compilacion:
echo [1] Standalone - Todo incluido / Self-Contained (Recomendado, no pide instalar .NET)
echo [2] Ligero - Dependiente del Framework (.NET global)
echo.
set /p OPT="Elige una opcion (1 o 2, Enter=1): "
if "%OPT%"=="" set OPT=1

if exist publish rd /s /q publish

if "%OPT%"=="2" (
    echo.
    echo [INFO] Compilando version Ligera (Framework-Dependent Single-File)...
    dotnet publish CPUMonitor.csproj -c Release -r win-x64 --self-contained false -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -p:SatelliteResourceLanguages="en-US;es" -o publish
) else (
    echo.
    echo [INFO] Compilando version Standalone (Self-Contained Single-File)...
    dotnet publish CPUMonitor.csproj -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:EnableCompressionInSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -p:SatelliteResourceLanguages="en-US;es" -o publish
)

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================================
    echo  [OK] Compilacion finalizada con exito!
    echo  Ejecutable generado en: publish\CPUMonitor.exe
    echo ========================================================
) else (
    echo.
    echo [ERROR] La compilacion ha fallado. Revisa los mensajes anteriores.
)

echo.
pause
