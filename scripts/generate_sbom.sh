#!/usr/bin/env bash
set -euo pipefail
OUTPUT=${1:-sbom.json}
if ! command -v cyclonedx-py >/dev/null 2>&1; then
  python -m pip install --upgrade cyclonedx-bom >/dev/null
fi
python -m cyclonedx_py --environment --format json --output "$OUTPUT"
echo "SBOM written to $OUTPUT"
