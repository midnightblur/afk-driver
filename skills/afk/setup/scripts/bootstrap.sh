# Run python_runtime.py on macOS/Linux with no Python installed: fetch the pinned uv, then let
# uv start the pinned CPython. Usage: sh bootstrap.sh plan|install|check [--test]
set -eu
scripts=$(cd "$(dirname "$0")" && pwd)
pins="$scripts/../../../../runtime/pyproject.toml"
cpython=$(sed -n 's/^requires-python *= *"==\([0-9.]*\)".*/\1/p' "$pins")
uv_version=$(sed -n 's/^required-version *= *"==\([0-9.]*\)".*/\1/p' "$pins")
if [ -z "$cpython" ] || [ -z "$uv_version" ]; then
  echo "bootstrap: exact Python and uv pins not found in $pins" >&2
  exit 2
fi
base="${XDG_DATA_HOME:-$HOME/.local/share}/afk"
uv="$base/uv/uv"

# The same settings python_runtime.py drops (UV_KEEP, INSTALLER_OVERRIDES): none may move a download.
for name in $(env | sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\)=.*/\1/p'); do
  case "$name" in
    UV_NATIVE_TLS|UV_SYSTEM_CERTS|UV_HTTP_TIMEOUT|UV_HTTP_CONNECT_TIMEOUT|UV_REQUEST_TIMEOUT|UV_HTTP_RETRIES|UV_CONCURRENT_DOWNLOADS) ;;
    UV_*|INSTALLER_DOWNLOAD_URL|INSTALLER_NO_MODIFY_PATH|CARGO_DIST_FORCE_INSTALL_DIR|CARGO_HOME|VIRTUAL_ENV) unset "$name" ;;
  esac
done
export UV_PYTHON_INSTALL_DIR="$base/pythons" UV_CACHE_DIR="$base/cache" UV_NO_CONFIG=1

case "$("$uv" --version 2>/dev/null || true)" in
  "uv $uv_version"|"uv $uv_version "*) ;;
  *)
    url="https://releases.astral.sh/github/uv/releases/download/$uv_version/uv-installer.sh"
    curl --proto =https --tlsv1.2 -LsSf "$url" | UV_UNMANAGED_INSTALL="$base/uv" sh ;;
esac
"$uv" python install "$cpython" --no-bin
exec "$uv" run --no-project --managed-python --no-python-downloads --python "$cpython" \
  "$scripts/python_runtime.py" "$@"
