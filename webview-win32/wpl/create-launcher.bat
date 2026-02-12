@echo off
setlocal

REM ================== Script directory ==================
set CURR_DIR=%~dp0
if "%CURR_DIR:~-1%"=="\" set CURR_DIR=%CURR_DIR:~0,-1%

REM ================== Settings ==================

set SHORTCUT_NAME=Deep Studio
set SHORTCUT_DIR=%USERPROFILE%\Desktop
set PYTHON_ROOT=%CURR_DIR%\..\Python
set PYTHON_EXE=%PYTHON_ROOT%\pythonw.exe
set APP_URL=http://172.16.1.166:8081
set APP_PARAMS=-m wpl --url %APP_URL% --title \"%SHORTCUT_NAME%\" --icon %CURR_DIR%\deepstudio.ico --cache %CURR_DIR%\..\.webview2 --background #1e1e1e
set ICON_PATH=%CURR_DIR%\deepstudio.ico

REM ================== Execution ==================

::powershell -NoProfile -Command "$ws=New-Object -ComObject WScript.Shell; $lnk=$ws.CreateShortcut('%CURR_DIR%\%SHORTCUT_NAME%.lnk'); $lnk.TargetPath='%PYTHON_EXE%'; $lnk.Arguments='\"%SCRIPT_PATH%\"'; $lnk.WorkingDirectory='%CURR_DIR%'; $lnk.IconLocation='%ICON_PATH%'; $lnk.WindowStyle=2; $lnk.Save()"
powershell -NoProfile -Command "$ws=New-Object -ComObject WScript.Shell; $lnk=$ws.CreateShortcut('%SHORTCUT_DIR%\%SHORTCUT_NAME%.lnk'); $lnk.TargetPath='%PYTHON_EXE%'; $lnk.Arguments='%APP_PARAMS%'; $lnk.WorkingDirectory='%CURR_DIR%'; $lnk.IconLocation='%ICON_PATH%'; $lnk.WindowStyle=2; $lnk.Save()"

echo Generate %SHORTCUT_NAME% shortcut success!
echo %SHORTCUT_DIR%\%SHORTCUT_NAME%.lnk
::pause
