## Plan: Vue Frontend Migration

Replace the two Jinja pages with one Vue/Vite SPA served at `/` by FastAPI. The SPA first verifies a bearer key through a dedicated protected endpoint, stores it in `sessionStorage`, and exposes Indexing and File Management tabs only after success. Remove the former `/upload/web` and `/files/web` browser routes; retain the authenticated JSON APIs that power the new UI.

**Steps**
1. **Establish Vue/Vite project structure** (*blocks steps 2-5*)
   - Add `d:/Github/Fukae/frontend/package.json`, Vite/Vue configuration, entry HTML, and source layout. Use Vue 3 plus the existing project conventions where applicable, with a `dev` script, production `build`, and `preview` script.
   - Configure the production output path to a server-owned directory such as `d:/Github/Fukae/static/app/`. Configure Vite’s development proxy for `/auth`, `/upload`, `/status`, `/chunks`, `/download`, and `/files` to the local FastAPI server, avoiding separate CORS behavior during development.
   - Add an npm lockfile consistent with the selected package manager and ensure generated assets are ignored or committed according to the repository’s existing deployment convention (confirm after examining `.gitignore`, if present).

2. **Define the API access-check contract** (*parallel with step 1 after route approach is chosen*)
   - In `d:/Github/Fukae/api/server.py`, add a side-effect-free `GET /auth/verify` route guarded by the existing `verify_bearer_key` dependency. Return a small success payload such as `{ "authenticated": true }`.
   - Leave authentication on all existing data and indexing endpoints in place. This endpoint is only the SPA’s explicit credential check; it must not become the sole protection mechanism.
   - Remove `GET /upload/web`, `POST /upload/web`, and `GET /files/web`, including their Jinja/template-only plumbing. Do not retain redirects or compatibility endpoints, per the selected requirement to remove legacy URLs.

3. **Serve the SPA from FastAPI** (*depends on 1 and 2*)
   - Update `d:/Github/Fukae/api/server.py` static-file setup to mount the Vue build assets without conflicting with `/static` or API routes.
   - Add `GET /` to return the built Vue `index.html` and an SPA fallback for client-side paths only if routing is introduced. Ensure API routes still return their native 404/validation results rather than receiving the HTML fallback.
   - Decide and document development behavior: FastAPI continues running independently for API work; Vite is used for frontend development; the production FastAPI process serves the built files.

4. **Implement credential gate and app shell** (*depends on 1 and 2*)
   - Create the root Vue app titled `Fukae`. Before authentication, render only a compact bearer-key entry form with submit, validating, error, and pending states.
   - On submit, call `/auth/verify` with `Authorization: Bearer <entered key>`. Store a successful key in `sessionStorage`; on application load, revalidate any stored key before unlocking the app. Remove invalid or unauthorized values from storage.
   - Centralize authenticated fetch behavior in a small API client/composable that injects the header, handles `401`/`403` by clearing the stored key and returning the user to the locked state, and surfaces other request failures to the applicable view.
   - Once unlocked, present two tabs: `Indexing` and `File Management`, with the active tab reflected in local component state. No sensitive backend request should occur before successful authentication.

5. **Migrate indexing workflow** (*depends on 4*)
   - Implement the Indexing tab using the protected `POST /upload` API rather than the unprotected legacy `POST /upload/web` flow. Preserve supported file selection, upload progress/state, task polling via `GET /status/{task_id}`, success/error display, and download of generated chunks through `GET /download/chunks/{doc_stem}_chunks.json`.
   - Reuse the response schema in `d:/Github/Fukae/api/models.py` and status semantics from `d:/Github/Fukae/api/tasks.py`; do not reimplement indexing behavior in the browser.

6. **Migrate file management workflow** (*depends on 4; can proceed in parallel with 5*)
   - Implement the File Management tab using `GET /files/uploads/list` and `GET /files/chunks/list`, loading both lists after authentication and offering the currently supported downloads.
   - Use authenticated requests for upload downloads and chunk downloads. Include loading, empty, and failed-list states plus a manual refresh action; do not introduce deletion or other file mutation because the API does not currently provide it.

7. **Replace presentation assets and documentation** (*depends on 3-6*)
   - Move/recreate only the relevant styles from `d:/Github/Fukae/static/style.css` in Vue component or application CSS; retire `d:/Github/Fukae/templates/index.html`, `d:/Github/Fukae/templates/files.html`, and obsolete shared CSS if no server routes use them.
   - Update `d:/Github/Fukae/README.md` and Docker configuration as needed to document/install Node dependencies, build the frontend into the served directory, and make the container image include the production SPA assets. Resolve the existing port inconsistency among `main.py`, README, and Dockerfile only to the extent necessary to accurately document/build the new frontend deployment.

8. **Add focused tests and validate** (*depends on 2-7*)
   - Add API route tests for `/auth/verify` covering missing, invalid, and valid bearer keys; verify that `/` returns the SPA entry after a production build and removed legacy web routes return 404.
   - Add frontend unit tests for credential submission/revalidation, session-storage cleanup after failed authorization, tab visibility after authorization, and authenticated-header injection. If the repository does not yet have a frontend test runner, add the smallest Vite-compatible choice and scripts needed for this coverage.
   - Run Python tests (`pytest tests/`), frontend tests, production build, and a manual smoke test: open `/`, validate a bad and good key, index a small fixture, inspect the file-management lists, download a file/chunk, refresh to confirm session-only persistence, and confirm legacy URLs return 404.

**Relevant files**
- `d:/Github/Fukae/api/server.py` — current FastAPI app, bearer dependency, static/Jinja configuration, and the browser/API routes to replace.
- `d:/Github/Fukae/api/models.py` — retain API response contracts for Vue indexing UI.
- `d:/Github/Fukae/api/tasks.py` — retain task state/polling semantics.
- `d:/Github/Fukae/templates/index.html` — behavior reference for indexing flow; remove after migration.
- `d:/Github/Fukae/templates/files.html` — behavior reference for file-management flow; remove after migration.
- `d:/Github/Fukae/static/style.css` — visual behavior reference; retire or replace after migration.
- `d:/Github/Fukae/main.py`, `d:/Github/Fukae/Dockerfile`, `d:/Github/Fukae/docker-compose.yml`, `d:/Github/Fukae/README.md` — runtime/build/deployment documentation alignment.
- New `d:/Github/Fukae/frontend/` — Vue source, Vite config, API client, views/components, and frontend tests.

**Decisions**
- The Vue source lives in `frontend/`; FastAPI serves its compiled production output from a static directory.
- The new public entrance is `/`; legacy `/upload/web` and `/files/web` are removed and should return 404.
- A verified bearer key persists in `sessionStorage`: it survives reloads in the current browser session but not browser restarts.
- `Fukae` is the visible application title and the document title.
- The available file-management scope is listing and downloading only; delete/rename features are excluded.
- API authentication remains server-enforced even though the frontend is locked until verification.

**Further Considerations**
1. Add a dedicated `/auth/verify` endpoint rather than validate with an unrelated protected list endpoint. This keeps the login contract explicit and avoids coupling the gate to data availability.
2. The production build deployment needs a deliberate Docker step (multi-stage Node build or checked-in compiled assets). Prefer a multi-stage Docker build so source control contains Vue source, not generated bundles.
