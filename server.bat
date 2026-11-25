@echo off
setlocal

set PORT=8000
set SCRIPT_DIR=%~dp0

goto %1

:start
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT% " ^| findstr "LISTENING"') do (
        echo Server already running on port %PORT%
        goto :eof
    )
    echo Starting server...
    start /b python "%SCRIPT_DIR%main.py" > "%TEMP%\olt-server.log" 2>&1
    timeout /t 2 /nobreak >nul
    for /f "tokens=2" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
        echo Server started on http://%%a:%PORT%
        goto :eof
    )
    echo Server started on http://localhost:%PORT%
    goto :eof

:stop
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT% " ^| findstr "LISTENING"') do (
        taskkill /F /PID %%a >nul 2>&1
        echo Server stopped
        goto :eof
    )
    echo No server running
    goto :eof

:restart
    call :stop 2>nul
    timeout /t 1 /nobreak >nul
    start /b python "%SCRIPT_DIR%main.py" > "%TEMP%\olt-server.log" 2>&1
    timeout /t 2 /nobreak >nul
    for /f "tokens=2" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
        echo Server restarted on http://%%a:%PORT%
        goto :eof
    )
    echo Server restarted on http://localhost:%PORT%
    goto :eof

:status
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT% " ^| findstr "LISTENING"') do (
        echo Server running on port %PORT%
        goto :eof
    )
    echo Server not running
    goto :eof

:*
    echo Usage: server.bat {start^|stop^|restart^|status}
