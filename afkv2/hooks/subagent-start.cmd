@echo off
setlocal
set "AFKV2_TEXT="
if "%~1"=="claude" set "AFKV2_TEXT=%~dp0built\afkv2-core-behaviors.claude-subagent.json"
if "%~1"=="codex" set "AFKV2_TEXT=%~dp0built\afkv2-core-behaviors.txt"
if not defined AFKV2_TEXT exit /b 2
type "%AFKV2_TEXT%" || exit /b 1
if not defined LOCALAPPDATA exit /b 0
set "AFKV2_DATA=%LOCALAPPDATA%\afkv2"
if not exist "%AFKV2_DATA%\" mkdir "%AFKV2_DATA%" 2>nul
2>nul (> "%AFKV2_DATA%\fired-%~1.txt" echo %~1 subagent-start %DATE% %TIME%)
exit /b 0
