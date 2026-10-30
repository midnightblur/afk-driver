@echo off
setlocal
if not "%~1"=="claude" if not "%~1"=="codex" exit /b 2
type "%~dp0built\afkv2-core-behaviors.txt" || exit /b 1
if not defined LOCALAPPDATA exit /b 0
set "AFKV2_DATA=%LOCALAPPDATA%\afkv2"
if not exist "%AFKV2_DATA%\" mkdir "%AFKV2_DATA%" 2>nul
2>nul (> "%AFKV2_DATA%\fired-%~1.txt" echo %~1 session-start "%DATE% %TIME%")
exit /b 0
