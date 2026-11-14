#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${HELTEC_MESH_LOADER_REPO:-$HOME/mesh-loader-blefix}"

# Use the user's existing PlatformIO environment if it is available.
if [[ -f "$HOME/meshcore-flash/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "$HOME/meshcore-flash/bin/activate"
fi
if ! python -m platformio --version >/dev/null 2>&1; then
  echo 'STOP: PlatformIO is not available. Activate your working MeshCore Python environment and retry.' >&2
  exit 1
fi
if [[ ! -f "$SCRIPT_DIR/.pinned_v3_preparer.py" && -f "$HOME/Downloads/heltec-v4-companion-v05/.pinned_v3_preparer.py" ]]; then
  cp "$HOME/Downloads/heltec-v4-companion-v05/.pinned_v3_preparer.py" "$SCRIPT_DIR/.pinned_v3_preparer.py"
fi
printf 'Heltec V4 v0.5 STANDALONE build (NOT hardware tested)\n'
python "$SCRIPT_DIR/build_standalone_v05.py" --repo "$REPO" "$@"
