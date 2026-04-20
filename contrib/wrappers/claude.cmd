@echo off
rem vpcc Windows wrapper — injects Bun preload hook + env flags before claude.exe.
rem Mirrors the Linux/macOS bash wrapper at ~/.local/bin/claude.
rem Drop on %PATH% (e.g. %USERPROFILE%\.local\bin\) to shadow the npm shim.

set "DISABLE_AUTOUPDATER=1"
set "CLAUDE_CODE_ENABLE_TELEMETRY=0"
set "CLAUDE_DANGEROUSLY_SKIP_PERMISSIONS=1"

set "VPCC_PRELOAD=%LOCALAPPDATA%\void-patcher\claude-preload.js"
if exist "%VPCC_PRELOAD%" (
    if defined BUN_OPTIONS (
        set "BUN_OPTIONS=%BUN_OPTIONS% --preload %VPCC_PRELOAD%"
    ) else (
        set "BUN_OPTIONS=--preload %VPCC_PRELOAD%"
    )
)

set "CLAUDE_EXE="
for %%I in (
    "%APPDATA%\npm\node_modules\@anthropic-ai\claude-code\node_modules\@anthropic-ai\claude-code-win32-x64\claude.exe"
    "%APPDATA%\npm\node_modules\@anthropic-ai\claude-code\node_modules\@anthropic-ai\claude-code-win32-arm64\claude.exe"
    "%APPDATA%\npm\node_modules\@anthropic-ai\claude-code\bin\claude.exe"
) do if exist "%%~I" (
    set "CLAUDE_EXE=%%~I"
    goto :found
)

:found
if "%CLAUDE_EXE%"=="" (
    echo vpcc wrapper: no Claude Code SEA binary found under %%APPDATA%%\npm 1>&2
    exit /b 1
)
"%CLAUDE_EXE%" %*
