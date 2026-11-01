@echo off
rem Builds Filip's Browser into dist\FilipsBrowser\FilipsBrowser.exe
rem Usage:  build.bat          (normal build, no console window)
rem         build.bat debug    (keeps a console window so errors are visible)

cd /d "%~dp0"

set MODE=--windowed
if /I "%1"=="debug" set MODE=

echo Installing PyInstaller...
py -3.12 -m pip install pyinstaller
if errorlevel 1 goto :error

echo Building...
py -3.12 -m PyInstaller --noconfirm %MODE% --name FilipsBrowser browser.py
if errorlevel 1 goto :error

rem Copy the optional files next to the exe, where the browser looks for them
if exist fonts xcopy /E /I /Y fonts dist\FilipsBrowser\fonts >nul
if exist home.html copy /Y home.html dist\FilipsBrowser\ >nul
if exist blocklist.txt copy /Y blocklist.txt dist\FilipsBrowser\ >nul

echo.
echo Done! Your browser is in: dist\FilipsBrowser\FilipsBrowser.exe
echo Keep the whole FilipsBrowser folder together.
pause
exit /b 0

:error
echo.
echo Something went wrong. See the messages above.
pause
exit /b 1
