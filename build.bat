@echo off
setlocal enabledelayedexpansion

:: ==================================================================
::  X1YEH Account Generator - One-Click Build
::  - Downloads project from GitHub if not found locally
::  - Installs all dependencies
::  - Builds EXE to Downloads
:: ==================================================================

set "GITHUB_REPO=https://github.com/kenziebird009/x1yeh-account-generator.git"
set "OUTDIR=%USERPROFILE%\Downloads"
set "WORKDIR=%TEMP%\x1yeh_build"

echo ==============================================
echo    X1YEH Account Generator - Build
echo ==============================================
echo.

:: -- check python --
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 3.12+ required.
    echo         Download from https://python.org
    pause & exit /b 1
)

:: -- check git --
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Git required.
    echo         Download from https://git-scm.com
    pause & exit /b 1
)

:: -- step 1: clone or update project from GitHub --
echo [1/5] Downloading project from GitHub...
if exist "%WORKDIR%" rmdir /s /q "%WORKDIR%" 2>nul
git clone --depth 1 "%GITHUB_REPO%" "%WORKDIR%" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Failed to clone repo. Check your internet connection.
    pause & exit /b 1
)
echo        Downloaded OK.

:: -- step 2: install dependencies --
echo [2/5] Installing dependencies...
python -m pip install --upgrade pip --quiet 2>nul
python -m pip install --upgrade setuptools wheel --quiet 2>nul
python -m pip install -r "%WORKDIR%\requirements.txt" --quiet
if %errorlevel% neq 0 (
    echo [WARN] Retrying with verbose install...
    python -m pip install -r "%WORKDIR%\requirements.txt"
    if %errorlevel% neq 0 (
        echo [ERROR] Dependencies failed. Trying one-by-one...
        python -m pip install requests customtkinter pillow pyinstaller cryptography
    )
)
echo        Dependencies OK.

:: -- step 3: verify assets --
echo [3/5] Verifying source files...
if not exist "%WORKDIR%\app.py" (
    echo [ERROR] app.py missing from repo.
    pause & exit /b 1
)

:: -- step 4: build EXE --
echo [4/5] Building EXE...
if not exist "%OUTDIR%" mkdir "%OUTDIR%"

python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --clean ^
    --noconfirm ^
    --distpath "%OUTDIR%" ^
    --workpath "%TEMP%\pyi_work" ^
    --specpath "%TEMP%\pyi_spec" ^
    --add-data "%WORKDIR%\config.json;." ^
    --add-data "%WORKDIR%\assets;assets" ^
    --name "X1YEH_AccountGen" ^
    "%WORKDIR%\app.py"

if %errorlevel% neq 0 (
    echo [ERROR] Build failed.
    pause & exit /b 1
)

:: -- step 5: clean up and copy extras --
echo [5/5] Finalizing...
xcopy "%WORKDIR%\assets" "%OUTDIR%\assets\" /E /I /Y >nul 2>&1
copy /Y "%WORKDIR%\config.json" "%OUTDIR%\config.json" >nul 2>&1
copy /Y "%WORKDIR%\version.json" "%OUTDIR%\version.json" >nul 2>&1

rmdir /s /q "%WORKDIR%" 2>nul
rmdir /s /q "%TEMP%\pyi_work" 2>nul
rmdir /s /q "%TEMP%\pyi_spec" 2>nul

echo.
echo ==============================================
echo    SUCCESS
echo    %OUTDIR%\X1YEH_AccountGen.exe
echo ==============================================
pause
