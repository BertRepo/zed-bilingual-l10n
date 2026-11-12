@echo off
setlocal
set PYTHONUTF8=1
if not exist "%~dp0patch_zed.py" goto missing
where py >nul 2>nul
if not errorlevel 1 (set "PYTHON=py -3") else (set "PYTHON=")
if defined PYTHON goto run
where python >nul 2>nul
if not errorlevel 1 (set "PYTHON=python")
if defined PYTHON goto run
echo [Python 3 not found] Install Python 3.8+ from https://www.python.org/downloads/windows/ and enable "Add Python to PATH".
echo Then double-click Launch.cmd again.
goto finish
:run
if "%~1"=="" goto default_mode
%PYTHON% "%~dp0patch_zed.py" %*
goto finish
:default_mode
%PYTHON% "%~dp0patch_zed.py" --apply
goto finish
:missing
echo [patch_zed.py not found] Extract the whole package into one folder first.
:finish
echo.
pause
