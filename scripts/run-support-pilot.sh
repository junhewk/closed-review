#!/usr/bin/env bash
# Bundle launcher: installs only into a newly created disposable environment.
set -euo pipefail

pilot_bundle=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
command -v uv >/dev/null || { echo 'uv is required.' >&2; exit 2; }
(cd -- "$pilot_bundle" && sha256sum -c SHA256SUMS)
pilot_runtime=$(mktemp -d "${TMPDIR:-/tmp}/creview-support-runtime.XXXXXXXX")
printf 'Isolated runtime: %s\n' "$pilot_runtime"
printf 'No gateway or existing Hermes profile will be restarted or modified.\n'
uv venv --python python3 "$pilot_runtime/venv"
uv pip sync --python "$pilot_runtime/venv/bin/python" --require-hashes \
  "$pilot_bundle/runtime-requirements.txt"
pilot_wheels=("$pilot_bundle"/closed_review-*.whl)
if [ "${#pilot_wheels[@]}" -ne 1 ] || [ ! -f "${pilot_wheels[0]}" ]; then
  echo 'The pilot bundle must contain exactly one candidate wheel.' >&2
  exit 2
fi
uv pip install --python "$pilot_runtime/venv/bin/python" --no-deps \
  "${pilot_wheels[0]}"
uv pip freeze --python "$pilot_runtime/venv/bin/python" > "$pilot_runtime/installed.txt"
exec "$pilot_runtime/venv/bin/python" "$pilot_bundle/test-support-hermes.py" \
  --corpus "$pilot_bundle/manuscripts" --output "$pilot_runtime/results" "$@"
