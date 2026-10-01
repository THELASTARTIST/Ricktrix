# RICKTRIX API + static site, as one container.
#
# Build from the REPOSITORY ROOT, not from backend/:
#
#   docker build -f backend/Dockerfile -t ricktrix .
#
# The context has to be the root because two things reach outside backend/:
# ml/data.py parses ../../autofare.js, and scripts/build_site.py stages the
# html, js, css and PWA files that sit beside it. Building from backend/ would
# produce an image with neither the site nor the data.
#
# The image does not train, and does not contain TensorFlow -- app/predict.py
# runs the model from the .npz that ml/export.py writes. Retraining is a
# separate step producing a new image, not something that happens at boot.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# /app mirrors the repository layout exactly, so every REPO_ROOT =
# Path(__file__).resolve().parents[n] in the backend still resolves correctly
# inside the container. Nothing needs a path shim.
WORKDIR /app

# Dependencies first, on their own layer, cached until the pins change.
COPY backend/requirements-serve.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Everything else. .dockerignore keeps .git, .venv and backend/.env out --
# that last one matters, because the service-role key in it bypasses Supabase's
# row-level security.
COPY . /app

WORKDIR /app/backend

# Stage the site into public/ so FastAPI serves the API and the app from one
# origin. No CORS, no second URL to configure, and a phone needs one address.
RUN python -m scripts.build_site

# Fail the build rather than ship something broken. Both of these produce an
# app that installs and then quietly does nothing, which is the worst failure
# mode there is.
RUN test -f ml/artifacts/fare_model.npz || test -f ml/artifacts/fare_model.keras \
 || (echo "no trained model in ml/artifacts." \
     && echo "  run locally:  python -m ml.train && python -m ml.export" \
     && exit 1)
RUN test -f public/manifest.webmanifest \
 && test -f public/sw.js \
 && test -f public/assets/icon-192.png \
 && test -f public/assets/icon-512.png \
 || (echo "the staged site is missing its PWA files." \
     && echo "  run locally:  python -m scripts.make_icons" \
     && exit 1)

ENV PORT=8000
EXPOSE 8000

# One worker on purpose. The model and vocabulary load once at startup and are
# read-only, so a second worker costs memory for no gain. Scale with more
# containers, not more workers.
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
