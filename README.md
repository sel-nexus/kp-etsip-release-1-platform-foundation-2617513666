# KP ETSIP — identity foundation

This slice implements local sign-in, sign-out, profile preferences and password changes. The later dashboard and inventory slices are not included yet, so signed-in users land on My Profile until those destinations exist. There is no self-registration.

## Configuration and local deployment

Copy `backend/.env.example` to `backend/.env`. Replace `JWT_SECRET` with a private random value of at least 32 characters (for example generate one with `python -c 'import secrets; print(secrets.token_urlsafe(48))'`) and set `BOOTSTRAP_PASSWORD` to a private password of 12–72 UTF-8 bytes. Never use example secrets in deployment. The seed runs only when `SEED_ON_STARTUP=true`, is idempotent, and does not reset passwords on later starts. Existing accounts require explicit administration to reset.

Run `docker compose up --build` and open `http://localhost:8080`. Compose runs a single-node replica set because account mutations and their audit writes are transactional. This local compose database has no Mongo authentication and must not be exposed publicly. For deployment use authenticated MongoDB/Atlas, TLS, a replica set, a private network, strong unique credentials, and HTTPS at the ingress. Set `SEED_ON_STARTUP=false` after provisioning as appropriate. Mongo data is persisted in a named volume.

For direct development, install Python dependencies with `python -m venv .venv`, activate it, then `pip install -r backend/requirements.txt`. Start an accessible MongoDB replica set and set its URI and database in `backend/.env`; from `backend`, run `uvicorn app.main:app --reload`. In `frontend`, run `npm install` and `npm run dev`. The development proxy forwards `/api` to port 8000; `VITE_DEV_API_PROXY` can override the target. Set `CORS_ORIGINS` to the actual frontend origin when using separate origins.

The six accounts `admin@ketsip.local`, `executive@ketsip.local`, `leader@ketsip.local`, `engineer@ketsip.local`, `auditor@ketsip.local`, and `readonly@ketsip.local` initially share the configured `BOOTSTRAP_PASSWORD`. These are local demo accounts, not production identities. Change the password after signing in; changing it invalidates all existing tokens. Role-based landing preferences are stored but the target pages are delivered by later slices.

## Tests

Backend: from `backend`, run `PYTHONPATH=. python -m pytest -q tests/test_auth.py`. The tests start a separate temporary `mongod` replica set, or use `TEST_MONGODB_URI` pointing to a dedicated replica set; each test uses and drops its own uniquely named database. Frontend: from `frontend`, run `npm test` and `npm run build`. For browser testing, start the real API, replica set and frontend; set `E2E_PASSWORD` to the demo password and run `node node_modules/@playwright/test/cli.js test`. The browser test changes the demo admin's saved landing preference.
