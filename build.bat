@echo off
setlocal enabledelayedexpansion

:: ------------------------------------------------------------------
::  X1YEH Account Generator - Setup + Build Script
::  Downloads from GitHub if not found locally, installs everything,
::  and builds the EXE to Downloads.
:: ------------------------------------------------------------------

set "PROJECT_DIR=%~dp0"
set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
cd /d "%PROJECT_DIR%"

set "REQUIREMENTS=%PROJECT_DIR%\requirements.txt"
set "CONFIG_JSON=%PROJECT_DIR%\config.json"
set "ASSETS_DIR=%PROJECT_DIR%\assets"
set "APP_PY=%PROJECT_DIR%\app.py"
set "OUTDIR=%USERPROFILE%\Downloads"
set "WORKDIR=%TEMP%\x1yeh_build_%RANDOM%"

echo ==============================================
echo    X1YEH Account Generator - Setup ^& Build
echo ==============================================
echo    Project dir: %PROJECT_DIR%
echo    Output dir:  %OUTDIR%
echo ==============================================
echo.

:: -- verify python --
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 3.12+ required. Install from https://python.org
    pause & exit /b 1
)

:: -- install / upgrade pip --
echo [1/5] Setting up pip...
python -m pip install --upgrade pip --quiet 2>nul
python -m pip install --upgrade setuptools wheel --quiet 2>nul

:: -- install project dependencies (absolute paths) --
echo [2/5] Installing project dependencies...
if not exist "%REQUIREMENTS%" (
    echo [ERROR] requirements.txt not found at: %REQUIREMENTS%
    echo         Make sure you extracted the full project folder.
    pause & exit /b 1
)
python -m pip install --force-reinstall --no-cache-dir -r "%REQUIREMENTS%"
if %errorlevel% neq 0 (
    echo [WARN] Some packages may have failed. Trying alternate install...
    python -m pip install requests customtkinter pillow pyinstaller cryptography
    if %errorlevel% neq 0 (
        echo [ERROR] Critical packages failed to install.
        pause & exit /b 1
    )
)
echo        All dependencies OK.

:: -- verify source files --
echo [3/5] Verifying source files...
if not exist "%APP_PY%" (
    echo [ERROR] app.py not found at: %APP_PY%
    pause & exit /b 1
)
if not exist "%CONFIG_JSON%" (
    echo [WARN] config.json missing, creating default...
    echo { > "%CONFIG_JSON%"
    echo   "api_base_url": "https://api.example.com", >> "%CONFIG_JSON%"
    echo   "version_url": "https://raw.githubusercontent.com/YOUR_USER/account-generator/main/version.json", >> "%CONFIG_JSON%"
    echo   "remember_login": true, >> "%CONFIG_JSON%"
    echo   "theme": "dark", >> "%CONFIG_JSON%"
    echo   "check_for_updates": true, >> "%CONFIG_JSON%"
    echo   "window_width": 1100, >> "%CONFIG_JSON%"
    echo   "window_height": 700, >> "%CONFIG_JSON%"
    echo   "version": "1.0.0" >> "%CONFIG_JSON%"
    echo } >> "%CONFIG_JSON%"
)

:: -- build EXE --
echo [4/5] Building EXE...
if not exist "%OUTDIR%" mkdir "%OUTDIR%"
python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --clean ^
    --noconfirm ^
    --distpath "%OUTDIR%" ^
    --workpath "%WORKDIR%" ^
    --specpath "%WORKDIR%" ^
    --add-data "%CONFIG_JSON%;." ^
    --add-data "%ASSETS_DIR%;assets" ^
    --name "X1YEH_AccountGen" ^
    "%APP_PY%"

if %errorlevel% neq 0 (
    echo [ERROR] Build failed. Check the output above for details.
    pause & exit /b 1
)

:: -- clean up --
echo [5/5] Cleaning temp files and copying assets...
if exist "%WORKDIR%" rmdir /s /q "%WORKDIR%" 2>nul
if exist "%PROJECT_DIR%\build" rmdir /s /q "%PROJECT_DIR%\build" 2>nul
for /d %%d in ("%PROJECT_DIR%\__pycache__") do rmdir /s /q "%%d" 2>nul

:: copy assets + config alongside EXE so it runs standalone
xcopy "%ASSETS_DIR%" "%OUTDIR%\assets\" /E /I /Y >nul 2>&1
copy /Y "%CONFIG_JSON%" "%OUTDIR%\config.json" >nul 2>&1
copy /Y "%PROJECT_DIR%\version.json" "%OUTDIR%\version.json" >nul 2>&1

:: create a README shortcut for the user
echo.
echo ==============================================
echo    BUILD SUCCESS !
echo ==============================================
echo    EXE:        %OUTDIR%\X1YEH_AccountGen.exe
echo    Assets:     %OUTDIR%\assets\
echo    Config:     %OUTDIR%\config.json
echo    Version:    %OUTDIR%\version.json
echo.
echo    To upload updates to GitHub:
echo      1. Update version.json with new version
echo      2. Create a GitHub Release with the EXE .zip
echo      3. Users will auto-update on next launch
echo ==============================================
pause
