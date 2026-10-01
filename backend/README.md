# RICKTRIX backend

FastAPI + TensorFlow + Supabase for the Kolkata share-auto route finder.

**Read this first:** the fare model here is a *fallback for stop pairs that are
not in the dataset*, not a price list. `autofare.js` states plainly that its
fares are user-provided and unverified, and it has no coordinates, distances or
timestamps — so the model cannot reason about how far a trip is. It learns how
a fare relates to how well-connected the two endpoints are, which is real but
weak signal. `python -m ml.train` prints its own out-of-fold error and compares
itself against a linear baseline; if it does not win, the training run says so
and you should treat the estimates as decorative.

---

## Start it

**Windows**

```
cd backend
run.bat
```

**macOS / Linux / WSL**

```
cd backend
chmod +x run.sh
./run.sh
```

That one command finds a suitable Python, creates `.venv`, installs
dependencies, trains the model if it has not been trained, and starts the API
on <http://localhost:8000>. Interactive docs at `/docs`.

Flags: `run.bat --seed` (also seed Supabase), `run.bat --retrain` (force a
fresh model).

**It works with no configuration at all.** With no `.env`, the API serves
`autofare.js` straight from the repo. Supabase is an upgrade, not a
prerequisite.

### Requirements

Python 3.9–3.12. **TensorFlow has no wheel for 3.13+** — use 3.11 or 3.12.
`run.bat` checks this and tells you if your Python is too new.

---

## Using it on your phone

`run.bat` binds to `0.0.0.0`, not `127.0.0.1`, so the server is reachable from
other devices. It also stages the site into `backend/public` and serves it from
the same port, so there is one URL for both the site and the API.

On startup it prints both addresses:

```
Laptop:  http://localhost:8000
Phone:   http://192.168.1.5:8000    <- same Wi-Fi, open this on your phone
```

Requirements for the phone to connect:

1. **Same Wi-Fi.** Guest networks often isolate clients from each other.
2. **Allow Python through the firewall.** Windows prompts on first run — choose
   *Private networks*. If you dismissed it, run PowerShell as admin:
   ```powershell
   New-NetFirewallRule -DisplayName "RICKTRIX dev" -Direction Inbound `
     -LocalPort 8000 -Protocol TCP -Action Allow -Profile Private
   ```
3. **Check with:** `curl http://192.168.1.5:8000/api/health` from the phone's
   browser. If that loads JSON, the wiring is fine and any problem is the page.

If the printed IP is wrong or missing, `ipconfig` shows the real IPv4 address
under the adapter you're connected through.

### The one thing that will not work over plain HTTP

`tracking.html` calls `navigator.geolocation`. Browsers only grant that in a
**secure context** — HTTPS, or `localhost`. On `http://192.168.1.5:8000` the
API is blocked and the page falls back to "Location unavailable". That is a
browser rule, not a bug in this code.

To test tracking on a real phone you need a tunnel, which gives you HTTPS:

```powershell
winget install --id Cloudflare.cloudflared
.\.venv\Scripts\python -m uvicorn app.main:app --port 8000   # in one window
cloudflared tunnel --url http://localhost:8000               # in another
```

It prints a `https://something.trycloudflare.com` URL that works from anywhere.
Two warnings: that URL is public, and on it the anonymous `POST /api/submissions`
endpoint accepts writes from anyone. Fine on a home network for an afternoon of
testing; do not leave it up. Set `ADMIN_EMAILS` so the moderation queue is not
readable, and stop the tunnel when you are done.

### Responsive layout

You do not need a separate mobile build. `style.css` and the per-page media
queries already collapse to one column below ~920px, and the pages use
`viewport-fit=cover` with safe-area insets. Test in the phone browser's
responsive mode first — the real value of the phone is the GPS and touch
behaviour, not the layout.

---

## Supabase (optional)

1. Create a project at <https://supabase.com>.
2. **SQL editor** → paste `migrations/001_schema.sql` → Run. It is idempotent.
3. Copy `backend/.env.example` to `backend/.env` and fill in the keys from
   **Project Settings → API**.
4. `run.bat --seed`, then `run.bat`.

---

## Installing it on a phone

The site is a **Progressive Web App**: it installs to the home screen, opens
without browser chrome, and — because the route data is a static file — keeps
working with no network at all. It is not a store app, and it does not need to
be: there is no Play Store listing involved and no review queue.

1. Start the server (`run.bat`).
2. On the phone, open the printed `http://<LAN-IP>:8000` address.
3. **Android / Chrome** — a download icon appears in the header. Tap it and
   confirm. (`pwa.js` captures Chrome's `beforeinstallprompt` and shows that
   button itself; if you dismissed Chrome's own prompt, reload the page.)
4. **iPhone / Safari** — tap **Share**, then **Add to Home Screen**.

The **Install app** button is wired to `RICKTRIX.install()`. On iOS it
explains the two-tap Share flow instead, because iOS has no install API to call
and `beforeinstallprompt` never fires.

### What is where

| File | Job |
|---|---|
| `manifest.webmanifest` | name, icons, colours, home-screen shortcuts |
| `sw.js` | precaches the shell; serves it when the network is gone |
| `pwa.js` | registers the worker, update banner, install button |
| `assets/icon-*.png` | generated by `scripts/make_icons.py` from the SVGs |
| `offline.html` | shown when a page is opened with no connection |

### Two constraints worth knowing before you test

**Service workers need a real origin.** Opened as a `file://` path the app
works, but cannot install or cache — `pwa.js` logs why and returns. Serve it
over `http://localhost` or HTTPS.

**Chrome will not offer to install over plain HTTP on a LAN address.** Only
`localhost` counts as a secure context, plus any real HTTPS origin. So the
`http://192.168.1.5:8000` address below lets you *browse* from the phone but
will not *install* there. For a real install you need HTTPS — either the tunnel
described above, or a deployed host.

That is the same reason `tracking.html`'s geolocation only works on
`localhost` or HTTPS. Both limits are browser rules, not bugs here.

### Offline is real, not decorative

`sw.js` precaches every page, script, stylesheet and icon, and the fares live in
`autofare.js` as a static file. So in aeroplane mode, route search, filtering
and saved routes all still work. What does *not* work is anything needing the
server: new fare estimates, route submissions, bookmark sync. `api.js` falls
back to the bundled arrays when a call fails, so those degrade rather than
break.

---

## Deploying it

The Docker image serves the API **and** the site from one process on one
origin, so a phone needs one URL and there is no CORS anywhere.

```bash
# from the repository root, not backend/
docker build -f backend/Dockerfile -t ricktrix .
docker run -p 8000:8000 ricktrix
```

`render.yaml` is a Render blueprint that builds the same image: push the repo
to GitHub, then **New → Blueprint** on Render and pick it. Set the Supabase
variables on the dashboard if you want them — the app works without them.

Before the first deploy the model has to exist. The Dockerfile fails on
purpose rather than shipping an API whose every prediction returns 503:

```
cd backend
python -m ml.train            # writes fare_model.keras
python -m ml.export           # writes fare_model.npz
python -m scripts.make_icons  # writes assets/*.png
```

`.dockerignore` keeps `backend/.env` out of the image. That is not tidiness:
the service-role key inside it bypasses row-level security, and anything baked
into an image on a public registry is readable by anyone.

### Why the image has no TensorFlow

`ml/export.py` lifts the trained weights into a `.npz`, and `app/predict.py`
evaluates them with numpy — an embedding lookup and three matrix multiplies.
That is not an optimisation, it is what makes the deployment affordable:
TensorFlow is ~600 MB of libraries and ~15 seconds of import time, which would
push the container well past the free tier of every host that exists.

`tests/test_smoke.py` checks the numpy and Keras paths agree to within 0.05
rupees on real rows, so this is verified rather than assumed. If the `.npz` is
missing the server falls back to Keras, and `/api/health` reports which backend
is live in `model_backend` — if that says `keras` in production, the export did
not make it into the image.

---

## Where things are served from

`run.bat` stages the site into `backend/public` and mounts it at `/`, so the API
and the pages share one port and one origin — no CORS, and a single URL that
works on a phone. The repo root is deliberately *not* served: it would publish
`backend/.env`, and the service-role key inside it bypasses row-level security.
`scripts/build_site.py` copies only known static file types from the top level.

| Variable | Needed for |
|---|---|
| `SUPABASE_URL` + `SUPABASE_ANON_KEY` | reading from the database |
| `SUPABASE_SERVICE_ROLE_KEY` | seeding, submissions, bookmark sync |
| `ADMIN_EMAILS` | who can read the moderation queue |
| `CORS_ORIGINS` | extra origins — unset means same-origin only, which is right |

The anon key is safe in the browser. The service-role key is not — it bypasses
row-level security and must never leave the server.

`ADMIN_EMAILS` empty means nobody is an admin. That is deliberate: a missing
env var should not open the moderation queue.

---

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | status, model metrics, data source, caveats |
| GET | `/api/stats` | real counts — stops the "450+" drift |
| GET | `/api/tariff` | official CNG tariff formula |
| GET | `/api/routes` | `?q= &area= &sort=fareAsc\|fareDesc\|az&limit=&offset=` |
| GET | `/api/routes/match` | `?from=&to=` — 404 if unmapped |
| GET | `/api/routes/{id}` | one route |
| GET | `/api/stops` | `?q=&limit=` — autocomplete |
| GET | `/api/stops/popular` | top stops by route count |
| POST | `/api/predict/fare` | observed fare, or a model estimate |
| POST | `/api/submissions` | community route submission → moderation |
| GET | `/api/submissions` | moderation queue (admin only) |
| GET/POST/DELETE | `/api/bookmarks` | saved routes across devices (auth) |

### `/api/predict/fare` is the interesting one

```jsonc
// a pair that is already mapped — authoritative
{ "fare_inr": 70, "source": "observed", "confidence": "high",
  "route": { "id": 1, "name": "Ahiritola Launch Ght ↔ Beadon Street…", … } }

// a pair we have never mapped — the model, hedged
{ "fare_inr": 42, "source": "estimated", "confidence": "low",
  "caveat": "No mapped route for this pair…",
  "tariff_floor_inr": 26.0 }
```

`source` is the field that matters. Show `observed` fares plainly and
`estimated` ones with a visible hedge. The endpoint returns **503, never a
made-up number**, if the model has not been trained.

---

## Wiring up the frontend

The PWA half *is* wired up: every page loads `pwa.js`, declares the manifest,
and carries the install metadata. What is not wired up is the **data** — the
site still runs entirely off `autofare.js`, deliberately, so it keeps working
with no server at all. `api.js` in the repo root is the opt-in bridge, and
every call in it falls back to the local arrays if the server is unreachable.

Per page:

- **index.html** — add `<script src="api.js"></script>` after `data.js`, then
  `const routes = await RICKTRIX.routes()`. Replace `handleSubmitRoute`
  (line ~329) with `RICKTRIX.submitRoute(...)`; it currently calls
  `e.target.reset()` and throws the submission away.
- **all_routes.html** — `RICKTRIX.routes({q, area, sort})` replaces the
  `routes.filter(...)` in `render()`. `area` is now a stored column, so the
  `routeArea()` regexes there can be deleted.
- **saved_routes.html** — keep reading `ricktrix-saved`; on login, push it to
  `/api/bookmarks` and adopt the server list. The key is `from + "|" + to`,
  not the numeric id, so migrate it as-is.
- **about.html** — point the donut chart at `/api/stats`. It currently plots a
  hardcoded `[450, 0, 0, 0]` against an actual dataset of 137.

Run a server for the pages too, or `file://` will block the `fetch` calls:

```
python -m http.server 8000     # from the repo root
```

---

## Tests

```
.venv\Scripts\python -m pytest -q
```

The dataset-parsing, area and data-source tests need only the standard library.
The model test skips until `ml.train` has run, and it fails if the model does
not beat predicting the mean fare.

`tests/test_smoke.py::test_dataset_is_consistent_with_the_ui_count` is the
canary for the 450-vs-137 discrepancy: it will start failing the day the
dataset legitimately reaches 450, at which point the hardcoded copy can be
raised.

---

## Layout

```
backend/
  app/
    main.py         FastAPI app, all HTTP routes
    data_source.py  LocalDataSource (autofare.js) | SupabaseDataSource
    predict.py      loads and calls the model; refuses to guess
    areas.py        area regexes ported from all_routes.html
    db.py           Supabase clients, JWT auth, admin guard
    schemas.py      pydantic models
    config.py       env loading, no dotenv dependency
  ml/
    data.py         parses autofare.js (the single source of truth)
    features.py     feature engineering, shared by training AND serving
    model.py        the Keras architecture
    train.py        5-fold CV, ridge baseline, saves artifacts
    export.py       Keras weights -> .npz, so serving needs no TensorFlow
    artifacts/      generated: model, vocab, metrics, exported weights
  migrations/001_schema.sql
  scripts/
    build_site.py   stages the site into public/ for same-origin serving
    make_icons.py   rasterises assets/icon.svg into the PNGs phones accept
    seed.py
  tests/test_smoke.py
  Dockerfile        build from the repo root: docker build -f backend/Dockerfile .
  requirements.txt       training (includes TensorFlow)
  requirements-serve.txt what the image installs (does not)
```

`ml/features.py` is imported by both `ml/train.py` and `app/predict.py`. That
is the only way to guarantee the vectors the model was fitted on are identical
to the ones it serves. Do not duplicate that logic.

---

## What is not built

Deliberately, because it needs more than a server:

- **Live tracking.** `tracking.html` moves four hardcoded rickshaws around with
  `Math.random()`. Real tracking needs a driver-side app, a location-reporting
  pipeline, and an abuse story. That is a second product.
- **Community chat.** `community.html` shows scripted messages and a "1,247
  online" counter that drifts via `setInterval`. The moderation queue for route
  submissions is the useful part, and that *is* built.
- **Phone OTP.** Email only — phone verification costs real money per message.
