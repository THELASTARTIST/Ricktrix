"""Stage the static site into backend/public so FastAPI can serve it.

The API and the site are served from one process on one port, which means one
origin, no CORS setup, and a URL your phone can open over the LAN.

Copying is deliberate: mounting the repo root would publish backend/.env and
backend/.venv over HTTP, and the service-role key in .env bypasses row-level
security. Only known static file types are copied, and only from the top level.

    python -m scripts.build_site
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
PUBLIC_DIR = BACKEND_ROOT / "public"

# Nothing else is copied, and never a dotfile or the backend directory itself.
ALLOWED_SUFFIXES = {
    ".html", ".js", ".css", ".json",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
    ".txt", ".md", ".webmanifest",
}

# Directories copied wholesale, extension-filtered. sw.js precaches
# './assets/icon.svg', so these have to land in public/ with the same paths.
ASSET_DIRS = ("assets",)


def collect() -> list[Path]:
    if not REPO_ROOT.is_dir():
        raise SystemExit(f"repository root not found at {REPO_ROOT}")
    return sorted(
        path
        for path in REPO_ROOT.iterdir()
        if path.is_file()
        and not path.name.startswith(".")
        and path.suffix.lower() in ALLOWED_SUFFIXES
    )


def collect_assets() -> list[Path]:
    files: list[Path] = []
    for name in ASSET_DIRS:
        directory = REPO_ROOT / name
        if not directory.is_dir():
            continue
        files.extend(
            sorted(
                path
                for path in directory.rglob("*")
                if path.is_file()
                and not path.name.startswith(".")
                and path.suffix.lower() in ALLOWED_SUFFIXES
            )
        )
    return files


def main() -> int:
    if PUBLIC_DIR.exists():
        shutil.rmtree(PUBLIC_DIR)
    PUBLIC_DIR.mkdir(parents=True)

    copied = []
    for source in collect():
        destination = PUBLIC_DIR / source.name
        shutil.copy2(source, destination)
        copied.append(source.name)

    # Assets keep their subdirectory, because sw.js precaches them by path.
    assets = collect_assets()
    for source in assets:
        relative = source.relative_to(REPO_ROOT)
        destination = PUBLIC_DIR / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(str(relative).replace("\\", "/"))

    if "index.html" not in copied:
        raise SystemExit("index.html was not copied - is the repo root correct?")

    missing = [name for name in ("sw.js", "pwa.js", "manifest.webmanifest")
               if name not in copied]
    if missing:
        # The app would install but not work offline. Worth failing loudly.
        raise SystemExit(f"missing PWA files: {missing}")

    print(f"staged {len(copied)} files into {PUBLIC_DIR}")
    for name in copied:
        print(f"  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
