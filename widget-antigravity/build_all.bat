@echo off
setlocal enabledelayedexpansion

echo =======================================================
echo   Antigravity Quota Monitor - Build Script
echo =======================================================
echo.

cd /d "%~dp0"

echo [1/3] Cleaning previous build artifacts...
if exist "build" rmdir /s /q "build"
if exist "dist\AntigravityQuotaMonitor.exe" del /f /q "dist\AntigravityQuotaMonitor.exe"
if exist "dist\installer" rmdir /s /q "dist\installer"

echo.
echo [2/3] Compiling standalone executable with PyInstaller...
python -m PyInstaller build.spec --clean -y
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] PyInstaller compilation failed.
    exit /b %ERRORLEVEL%
)

echo.
echo [3/3] Generating Windows Setup Installer with Inno Setup...
set "ISCC_PATH=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC_PATH%" (
    set "ISCC_PATH=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
)
if not exist "%ISCC_PATH%" (
    set "ISCC_PATH=%ProgramFiles%\Inno Setup 6\ISCC.exe"
)

if exist "%ISCC_PATH%" (
    "%ISCC_PATH%" "installer\installer.iss"
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Inno Setup compilation failed.
        exit /b %ERRORLEVEL%
    )
    echo.
    echo =======================================================
    echo   BUILD SUCCESSFUL!
    echo   Executable: dist\AntigravityQuotaMonitor.exe
    echo   Installer:  dist\installer\AntigravityQuotaMonitor-Setup.exe
    echo =======================================================
) else (
    echo [WARNING] ISCC.exe not found. Setup installer skipped.
    echo Standalone executable is available at dist\AntigravityQuotaMonitor.exe
)

echo.
pause
