#!/usr/bin/env bash
set -euo pipefail
VERSION=${1:-}
if [[ -z "$VERSION" ]]; then
  echo "Usage: scripts/release.sh vX.Y.Z"
  exit 1
fi
make lint
make test
make docker-build
./scripts/generate_sbom.sh "sbom-$VERSION.json"
git tag "$VERSION"
echo "Release $VERSION tagged. Push with 'git push --tags'."
