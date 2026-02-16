@echo off
REM ---------------------------------------------------------
REM  O.R.I.O.N. Unified Launcher -- Gateway + Brain
REM
REM  Usage:  bin\start.bat
REM          bin\start.bat --dev
REM          bin\start.bat --no-brain
REM          bin\start.bat --trust-mode
REM ---------------------------------------------------------

set "SCRIPT_DIR=%~dp0"
set "PS_ARGS="

:parse_args
if "%~1"=="" goto run
if /i "%~1"=="--dev"          set "PS_ARGS=%PS_ARGS% -DevMode"    & shift & goto parse_args
if /i "%~1"=="--no-brain"     set "PS_ARGS=%PS_ARGS% -NoBrain"    & shift & goto parse_args
if /i "%~1"=="--trust-mode"   set "PS_ARGS=%PS_ARGS% -TrustMode"  & shift & goto parse_args
if /i "%~1"=="--no-dream"     set "PS_ARGS=%PS_ARGS% -NoDream"    & shift & goto parse_args
if /i "%~1"=="--no-vision"    set "PS_ARGS=%PS_ARGS% -NoVision"   & shift & goto parse_args
if /i "%~1"=="--no-scout"     set "PS_ARGS=%PS_ARGS% -NoScout"    & shift & goto parse_args
echo Unknown argument: %~1
shift
goto parse_args

:run
powershell -ExecutionPolicy Bypass -NoProfile -File "%SCRIPT_DIR%start.ps1"%PS_ARGS%
exit /b %ERRORLEVEL%
