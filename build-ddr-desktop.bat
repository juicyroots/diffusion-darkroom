@echo off
setlocal

set "BUILD_DIR=source\build"
set "DISTRO_DIR=distro"
set "VERSION_FILE=source\app-desktop\ddr-build-version.txt"
set "SPEC_FILE=source\app-desktop\ddr-desktop.spec"

call :next_version
if errorlevel 1 goto :build_failed

echo [DDR] Clearing old build artifacts...
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
if exist "%DISTRO_DIR%" rmdir /s /q "%DISTRO_DIR%"
mkdir "%BUILD_DIR%"
mkdir "%DISTRO_DIR%"

echo [DDR] Installing desktop build dependencies...
python -m pip install --upgrade pip
if errorlevel 1 goto :build_failed
python -m pip install -r "source/app-desktop/requirements-desktop.txt"
if errorlevel 1 goto :build_failed

echo [DDR] Generating ddr.ico from source/app-web/ddr.png...
python "source/app-desktop/make_ddr_icon.py"
if errorlevel 1 goto :build_failed

echo [DDR] Building Windows portable app...
pyinstaller --noconfirm --clean --distpath "%DISTRO_DIR%" --workpath "%BUILD_DIR%" "%SPEC_FILE%"
if errorlevel 1 goto :build_failed

call :flatten_distro
if errorlevel 1 goto :build_failed

if not exist "%DISTRO_DIR%\ddr.exe" (
  echo [DDR] Build output not found: %DISTRO_DIR%\ddr.exe
  goto :build_failed
)

ren "%DISTRO_DIR%\ddr.exe" "%EXE_NAME%"
if errorlevel 1 goto :build_failed

echo %VERSION%>"%VERSION_FILE%"

echo.
echo Build complete.
echo Build folder: %BUILD_DIR%
echo Distro folder: %DISTRO_DIR%
echo EXE: %DISTRO_DIR%\%EXE_NAME%
endlocal
goto :eof

:next_version
set "VERSION=1.00"
if exist "%VERSION_FILE%" (
  set /p VERSION=<"%VERSION_FILE%"
)

for /f "tokens=1,2 delims=." %%A in ("%VERSION%") do (
  set /a MAJOR=%%A
  set /a MINOR=1%%B-100
)

if not defined MAJOR set /a MAJOR=1
if not defined MINOR set /a MINOR=0

if %MINOR% GEQ 99 (
  set /a MAJOR=%MAJOR% + 1
  set /a MINOR=0
) else (
  set /a MINOR=%MINOR% + 1
)

set "MINOR_PAD=0%MINOR%"
set "MINOR_PAD=%MINOR_PAD:~-2%"
set "VERSION=%MAJOR%.%MINOR_PAD%"
set "EXE_NAME=ddr-v%VERSION%.exe"
echo [DDR] Version: %VERSION%
exit /b 0

:flatten_distro
if exist "%DISTRO_DIR%\ddr-portable\" (
  if exist "%DISTRO_DIR%\_internal\" rmdir /s /q "%DISTRO_DIR%\_internal"
  if exist "%DISTRO_DIR%\ddr-portable\_internal\" move "%DISTRO_DIR%\ddr-portable\_internal" "%DISTRO_DIR%\_internal" >nul
  if exist "%DISTRO_DIR%\ddr-portable\ddr.exe" move "%DISTRO_DIR%\ddr-portable\ddr.exe" "%DISTRO_DIR%\ddr.exe" >nul
  rmdir /s /q "%DISTRO_DIR%\ddr-portable"
)
exit /b 0

:build_failed
echo.
echo [DDR] Build failed. See errors above.
endlocal
exit /b 1
