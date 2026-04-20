# vpcc PowerShell wrapper — Windows Bun preload injection for Claude Code.
# Save as $env:USERPROFILE\.local\bin\claude.ps1 and put on $env:PATH.

$env:DISABLE_AUTOUPDATER                 = '1'
$env:CLAUDE_CODE_ENABLE_TELEMETRY        = '0'
$env:CLAUDE_DANGEROUSLY_SKIP_PERMISSIONS = '1'

$preload = Join-Path $env:LOCALAPPDATA 'void-patcher\claude-preload.js'
if (Test-Path $preload) {
    if ($env:BUN_OPTIONS) {
        $env:BUN_OPTIONS = "$env:BUN_OPTIONS --preload $preload"
    } else {
        $env:BUN_OPTIONS = "--preload $preload"
    }
}

$candidates = @(
    "$env:APPDATA\npm\node_modules\@anthropic-ai\claude-code\node_modules\@anthropic-ai\claude-code-win32-x64\claude.exe"
    "$env:APPDATA\npm\node_modules\@anthropic-ai\claude-code\node_modules\@anthropic-ai\claude-code-win32-arm64\claude.exe"
    "$env:APPDATA\npm\node_modules\@anthropic-ai\claude-code\bin\claude.exe"
)

$exe = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $exe) {
    Write-Error "vpcc wrapper: no Claude Code SEA binary found under $env:APPDATA\npm"
    exit 1
}
& $exe @args
