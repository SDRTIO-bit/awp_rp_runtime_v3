# Clean Clone Verification

Run this procedure in a newly cloned working directory before relying on the
local development environment. It verifies the Python runtime, embedded Pi
harness, and web build without reusing generated artifacts from another clone.

```powershell
git clone <repository-url> awp-novel-runtime
cd awp-novel-runtime
pip install -e ".[dev,tui]"
cd agent_harness
npm ci
npm test
cd ..
cd web
npm ci
npm test
npm run build
cd ..
python -m pytest tests -q --tb=short
```

Each command must exit with status `0`. `npm run build` must produce
`frontend/dist/index.html`; otherwise `web.bat` will serve a 404 response instead of
the Novel Coding interface. The final pytest command verifies the Python API,
project storage, and embedded-host contracts.

CI is the reproducible baseline: it runs Python 3.10, 3.11, and 3.12 tests plus
Node 22 harness and web checks. A local clean-clone run remains necessary when
changing setup instructions, package manifests, or launcher behavior.
