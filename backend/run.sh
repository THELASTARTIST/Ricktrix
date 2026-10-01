#!/usr/bin/env bash
# ---------------------------------------------------------------------
# RICKTRIX backend - one-command start (macOS / Linux / WSL).
#
#   ./run.sh              start the API (trains the model if needed)
#   ./run.sh --seed       also seed Supabase, then start
#   ./run.sh --retrain    force a fresh model, then start
# ---------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")"

echo
echo " RICKTRIX backend"
echo " ================"
echo

# --- 1. find a usable Python (TensorFlow has no wheel for 3.13+) -----------
PY=""
for candidate in python3.12 python3.11 python3.10 python3.9 python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 &&
     "$candidate" -c 'import sys; sys.exit(0 if (3,9) <= sys.version_info[:2] < (3,13) else 1)' 2>/dev/null; then
    PY="$candidate"
    break
  fi
done

if [ -z "$PY" ]; then
  echo " ERROR: no Python 3.9-3.12 found."
  echo " TensorFlow has no wheel for 3.13+. Install Python 3.11 or 3.12."
  exit 1
fi
echo " Python $("$PY" -c 'import sys; print(sys.version.split()[0])') via $PY"

# --- 2. virtualenv -------------------------------------------------------
if [ ! -x ".venv/bin/python" ]; then
  echo " Creating virtualenv in backend/.venv ..."
  "$PY" -m venv .venv
fi
VPY=".venv/bin/python"

# --- 3. dependencies -----------------------------------------------------
if [ ! -f ".venv/installed" ]; then
  echo " Installing dependencies (first run takes a few minutes) ..."
  "$VPY" -m pip install --upgrade pip --quiet
  "$VPY" -m pip install -r requirements.txt
  touch .venv/installed
  echo " Dependencies installed."
else
  echo " Dependencies already installed."
fi

# --- 4. fare model -------------------------------------------------------
if [ "${1:-}" = "--retrain" ]; then
  echo " Retraining the fare model ..."
  "$VPY" -m ml.train
elif [ ! -f "ml/artifacts/fare_model.keras" ]; then
  echo " No trained model found - training now (a minute or two) ..."
  "$VPY" -m ml.train
else
  echo " Fare model already trained."
fi

# Export to plain numpy weights. The server evaluates those directly, which is
# what keeps TensorFlow out of the production image. Cheap, so it runs every
# start to pick up a freshly trained model.
"$VPY" -m ml.export

# --- 4b. app icons -------------------------------------------------------
# Chrome's install prompt and iOS's Add to Home Screen both want real PNGs.
# They are committed, so this is normally a fast no-op.
if [ ! -f "../assets/icon-512.png" ]; then
  echo " Generating app icons ..."
  "$VPY" -m scripts.make_icons
fi

# --- 5. seed -------------------------------------------------------------
if [ "${1:-}" = "--seed" ]; then
  echo
  echo " Seeding Supabase ..."
  "$VPY" -m scripts.seed || echo " (skipped - SUPABASE_SERVICE_ROLE_KEY not set)"
fi

# --- 6. stage the static site ---------------------------------------------
# Copied into backend/public so the API serves the site from one origin. The
# repo root is never served - that would expose backend/.env.
"$VPY" -m scripts.build_site

# --- 7. serve ------------------------------------------------------------
LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')"
echo
echo " Starting on port 8000"
echo "   Laptop:  http://localhost:8000"
if [ -n "$LAN_IP" ]; then
  echo "   Phone:   http://$LAN_IP:8000    <- same Wi-Fi, open this on your phone"
else
  echo "   Could not detect a LAN address."
fi
echo "   Docs:    http://localhost:8000/docs"
echo
echo " Press Ctrl+C to stop."
echo
exec "$VPY" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
