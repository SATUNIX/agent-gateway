# Release Checklist

1. **Pre-flight**
   - Ensure `main` is green in CI and `make lint && make test` pass locally.
   - Review dependency updates (`pip list --outdated`) and security advisories.
   - Confirm API keys in `src/config/security.yaml` have up-to-date expirations.

2. **Smoke & Integration**
   - Run `pytest tests/test_smoke_gateway.py`.
   - `docker-compose up --build` and verify gateway -> mock upstream path plus Prometheus scrape.

3. **Artifacts**
   - `make docker-build` to produce the release image.
   - `./scripts/generate_sbom.sh sbom-<version>.json` for SBOM.

4. **Tag & Publish**
   - Update `README.md`/docs with release notes.
   - `scripts/release.sh vX.Y.Z` (creates tag, runs tests, builds image).
   - Push commits and tags, upload SBOM/resulting artifacts.

5. **Post-release**
   - Monitor logs/metrics, ensure alerts configured.
   - Schedule key rotation reminders via `scripts/nightly_audit.py` output.
