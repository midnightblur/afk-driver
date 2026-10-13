# Run python_runtime.py on Windows with no Python installed: fetch the pinned uv, then let
# uv start the pinned CPython. Usage: powershell -NoProfile -ExecutionPolicy Bypass -File bootstrap.ps1 plan|install|check [--test]
$ErrorActionPreference = 'Stop'
function Fail([string]$why, [int]$code = 1) {
    [Console]::Error.WriteLine("bootstrap: $why")
    exit $code
}
$forward = $args
try { $pins = Get-Content -Raw (Join-Path $PSScriptRoot '..\..\..\..\runtime\pyproject.toml') }
catch { Fail "cannot read runtime\pyproject.toml: $($_.Exception.Message)" 2 }
$python = [regex]::Match($pins, '(?m)^requires-python\s*=\s*"==([0-9.]+)"').Groups[1].Value
$uvVersion = [regex]::Match($pins, '(?m)^required-version\s*=\s*"==([0-9.]+)"').Groups[1].Value
if (-not $python -or -not $uvVersion) { Fail 'exact Python and uv pins not found in runtime\pyproject.toml' 2 }
# Fully qualified: a drive and a separator (C:\x) or UNC (\\host\share); C:x and \x stay relative.
if ($env:LOCALAPPDATA -notmatch '^([A-Za-z]:[\\/]|[\\/]{2}[^\\/]+[\\/]+[^\\/]+)') {
    Fail 'LOCALAPPDATA is not an absolute path; setup installs under it' 2
}
$base = Join-Path $env:LOCALAPPDATA 'afk'
$uv = Join-Path $base 'uv\uv.exe'

# The same settings python_runtime.py drops (UV_KEEP, INSTALLER_OVERRIDES): none may move a download.
$keep = 'UV_NATIVE_TLS', 'UV_SYSTEM_CERTS', 'UV_HTTP_TIMEOUT', 'UV_HTTP_CONNECT_TIMEOUT',
        'UV_REQUEST_TIMEOUT', 'UV_HTTP_RETRIES', 'UV_CONCURRENT_DOWNLOADS'
$drop = 'INSTALLER_DOWNLOAD_URL', 'INSTALLER_NO_MODIFY_PATH', 'CARGO_DIST_FORCE_INSTALL_DIR', 'CARGO_HOME', 'VIRTUAL_ENV'
foreach ($item in @(Get-ChildItem env:)) {
    $name = $item.Name.ToUpper()
    if (($name.StartsWith('UV_') -and $keep -notcontains $name) -or $drop -contains $name) {
        Remove-Item "env:$($item.Name)"
    }
}
$env:UV_PYTHON_INSTALL_DIR = Join-Path $base 'pythons'
$env:UV_CACHE_DIR = Join-Path $base 'cache'
$env:UV_NO_CONFIG = '1'

function Test-PinnedUv {
    if (-not (Test-Path -LiteralPath $uv -PathType Leaf)) { return $false }
    try { $have = (& $uv --version 2>$null) -join '' } catch { return $false }
    return $have -match ('^uv ' + [regex]::Escape($uvVersion) + '(\s|$)')
}
# A native command that cannot start throws here; one that starts and fails sets its exit code.
function Invoke-Step([string]$what, [scriptblock]$step) {
    try { & $step } catch { Fail "$what could not start: $($_.Exception.Message)" }
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
}

if (-not (Test-PinnedUv)) {
    $url = "https://releases.astral.sh/github/uv/releases/download/$uvVersion/uv-installer.ps1"
    $env:UV_UNMANAGED_INSTALL = Split-Path $uv
    Invoke-Step 'the uv installer' { & powershell -NoProfile -ExecutionPolicy Bypass -Command "irm $url | iex" }
    Remove-Item env:UV_UNMANAGED_INSTALL
    if (-not (Test-PinnedUv)) { Fail "$uv is not uv $uvVersion after the installer ran" }
}
Invoke-Step 'uv python install' { & $uv python install $python --no-bin --no-registry }
$runtime = Join-Path $PSScriptRoot 'python_runtime.py'
Invoke-Step 'uv run' { & $uv run --no-project --managed-python --no-python-downloads --python $python $runtime @forward }
exit 0
