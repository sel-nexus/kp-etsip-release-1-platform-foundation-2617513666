# KP ETSIP — Release 1 platform foundation

An enterprise inventory and insight application with local identity, scoped portfolios and applications, executive metrics, administration, audit history and CSV reports. The React/Vite client uses a FastAPI REST API backed by MongoDB. There is no self-registration or live external integration.

## Configuration and local deployment

Copy `backend/.env.example` to `backend/.env`. Replace `JWT_SECRET` with a private random value of at least 32 characters (for example generate one with `python -c 'import secrets; print(secrets.token_urlsafe(48))'`) and set `BOOTSTRAP_PASSWORD` to a private password of 12–72 UTF-8 bytes. Never use example secrets in deployment. The seed runs only when `SEED_ON_STARTUP=true`, is idempotent, and does not reset passwords on later starts. Existing accounts require explicit administration to reset.

Run `docker compose up --build` and open `http://localhost:8080`. Compose runs a single-node replica set because account mutations and their audit writes are transactional. This local compose database has no Mongo authentication and must not be exposed publicly. For deployment use authenticated MongoDB/Atlas, TLS, a replica set, a private network, strong unique credentials, and HTTPS at the ingress. Set `SEED_ON_STARTUP=false` after provisioning as appropriate. Mongo data is persisted in a named volume.

For direct development, install Python dependencies with `python -m venv .venv`, activate it, then `pip install -r backend/requirements.txt`. Start an accessible MongoDB replica set and set its URI and database in `backend/.env`; from `backend`, run `uvicorn app.main:app --reload`. In `frontend`, run `npm install` and `npm run dev`. The development proxy forwards `/api` to port 8000; `VITE_DEV_API_PROXY` can override the target. Set `CORS_ORIGINS` to the actual frontend origin when using separate origins.

The six accounts `admin@ketsip.local`, `executive@ketsip.local`, `leader@ketsip.local`, `engineer@ketsip.local`, `auditor@ketsip.local`, and `readonly@ketsip.local` initially share the configured `BOOTSTRAP_PASSWORD`. These are local demo accounts, not production identities. Change the password after signing in; changing it invalidates all existing tokens. Landing preferences are persisted and determine the initial dashboard or application page.

## Tests

Backend: from `backend`, run `PYTHONPATH=. python -m pytest -q`. Tests start a separate temporary `mongod` replica set, or use `TEST_MONGODB_URI` pointing to a dedicated replica set; each test creates and drops its own uniquely named database. Frontend: from `frontend`, run `node node_modules/vitest/vitest.mjs run` and `node node_modules/typescript/bin/tsc --noEmit && node node_modules/vite/bin/vite.js build`. For browser testing, start a real API and isolated MongoDB replica set, set `E2E_PASSWORD` to the configured bootstrap password, and run `node node_modules/@playwright/test/cli.js test` in `frontend`; Playwright can start the Vite server. Browser tests modify and restore temporary test data and must never target production.

## Policies and operational limits

Administrator-only audit access was explicitly chosen for this implementation, differing from the PRD's Auditor audit-access acceptance criterion. Portfolio Leaders see and edit only assigned portfolios, with an empty assignment granting no access; Engineers and Read Only users can view all portfolios. Role permissions can narrow but cannot override hard role restrictions. Deleting a portfolio cascades to its applications, while user deletion retains audit history. Dashboard and reports are based on manually maintained inventory. CSV exports are limited to 10,000 records. The administrator and all demo users initially share the configured bootstrap password; change it immediately and disable demo seeding in production.

The browser E2E runner timed out in the development sandbox and the user approved proceeding without a passing journey suite; rerun it in the target environment. The container build reported 20 npm dependency advisories, including 17 high and two critical; review and remediate before production. Use TLS at the ingress, private authenticated MongoDB, strong credentials, and externally configured brute-force protection. This project does not implement login rate limiting.
