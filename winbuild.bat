@echo off
setlocal
cd /d "%~dp0"
cd sideband_sources\sbapp
if errorlevel 1 exit /b 1
set "version="
for /f "delims=" %%v in ('python gv.py') do set "version=%%v"
if not defined version exit /b 1
cd ..\..
echo Compiling Sideband %version%

cd sideband_sources
python -m PyInstaller sideband.spec --noconfirm
if errorlevel 1 exit /b 1
cd ..

if not exist "sideband_sources\dist\main\Sideband.exe" exit /b 1
set "source_dir=Sideband_%version%"
if exist "%source_dir%" exit /b 1
move "sideband_sources\dist\main" "%source_dir%"
if errorlevel 1 exit /b 1
if not exist dist mkdir dist
powershell.exe -NoProfile -Command "$ErrorActionPreference = 'Stop'; Compress-Archive -LiteralPath '%source_dir%' -DestinationPath 'dist\%source_dir%_windows_x86_64.zip' -Force"
if errorlevel 1 exit /b 1

echo Build completed: dist\%source_dir%_windows_x86_64.zip
exit /b 0
