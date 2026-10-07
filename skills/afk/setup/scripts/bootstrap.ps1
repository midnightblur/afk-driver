# Run python_runtime.py on Windows with no Python installed: fetch the pinned uv, then let
# uv start the pinned CPython. Usage: powershell -NoProfile -ExecutionPolicy Bypass -File bootstrap.ps1 plan|install|check [--test]
$pins = Get-Content -Raw (Join-Path $PSScriptRoot '..\..\..\..\runtime\pyproject.toml')
$python = [regex]::Match($pins, '(?m)^requires-python\s*=\s*"==([0-9.]+)"').Groups[1].Value
$uvVersion = [regex]::Match($pins, '(?m)^required-version\s*=\s*"==([0-9.]+)"').Groups[1].Value
if (-not $python -or -not $uvVersion) {
    [Console]::Error.WriteLine('bootstrap: exact Python and uv pins not found in runtime\pyproject.toml')
    exit 2
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

$have = ''
if (Test-Path $uv) { $have = (& $uv --version 2>$null) -join '' }
if ($have -notmatch ('^uv ' + [regex]::Escape($uvVersion) + '(\s|$)')) {
    $url = "https://releases.astral.sh/github/uv/releases/download/$uvVersion/uv-installer.ps1"
    $env:UV_UNMANAGED_INSTALL = Split-Path $uv
    & powershell -NoProfile -ExecutionPolicy Bypass -Command "irm $url | iex"
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
    Remove-Item env:UV_UNMANAGED_INSTALL
}
& $uv python install $python --no-bin --no-registry
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& $uv run --no-project --managed-python --no-python-downloads --python $python `
    (Join-Path $PSScriptRoot 'python_runtime.py') @args
exit $LASTEXITCODE
