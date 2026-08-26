@echo off
setlocal EnableExtensions DisableDelayedExpansion
title AI-Novel-Studio Portable

rem This is a development/portable entry point, not an installer.
rem Keep the staged Application tree beside this file:
rem   <portable-root>\AI-Novel-Studio-Portable.cmd
rem   <portable-root>\Application\...
rem No credentials are read, accepted, persisted, or forwarded here.

set "APPLICATION_ROOT=%~dp0Application"
set "PYTHON=%APPLICATION_ROOT%\Runtime\Python\python.exe"

if not exist "%PYTHON%" goto :missing_runtime
if not exist "%APPLICATION_ROOT%\Backend\app\packaging\packaged_desktop_launcher.py" goto :missing_runtime
if not exist "%APPLICATION_ROOT%\Frontend\dist\index.html" goto :missing_runtime
if not exist "%APPLICATION_ROOT%\DesktopHost\AI-Novel-Studio.DesktopHost.exe" goto :missing_runtime
if not exist "%APPLICATION_ROOT%\PostgreSQL\bin\postgres.exe" goto :missing_runtime
if not exist "%APPLICATION_ROOT%\PostgreSQL\bin\initdb.exe" goto :missing_runtime
if not exist "%APPLICATION_ROOT%\release\version.json" goto :missing_runtime

pushd "%APPLICATION_ROOT%\Backend" >nul 2>&1
if errorlevel 1 goto :launch_failed

rem -I keeps the bundled Python isolated from user site packages and PYTHONPATH.
rem Do not append arbitrary command-line arguments: the entry point is fixed to
rem the staged application root and cannot be redirected to another payload.
"%PYTHON%" -I -m app.packaging.packaged_desktop_launcher --application-root "%APPLICATION_ROOT%"
set "EXIT_CODE=%ERRORLEVEL%"
popd >nul 2>&1
exit /b %EXIT_CODE%

:missing_runtime
echo AI-Novel-Studio portable payload is incomplete.>&2
echo Run the verified Windows application staging step first; no files were changed.>&2
set "EXIT_CODE=2"
goto :finish_error

:launch_failed
echo AI-Novel-Studio portable entry could not access the bundled Backend directory.>&2
set "EXIT_CODE=2"

:finish_error
if /I not "%AI_NOVEL_STUDIO_PORTABLE_NO_PAUSE%"=="1" pause
exit /b %EXIT_CODE%
