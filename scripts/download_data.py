#!/usr/bin/env python3
"""Download NASA PGDA high-resolution LOLA south-pole products (real data) into data/raw/<site>/.

Source: https://pgda.gsfc.nasa.gov/products/78  (5 m/pixel GeoTIFFs; files can be hundreds of MB each).
Standard library only; resumable; records size and SHA-256 in data/metadata/downloads.json.

Examples:
  python scripts/download_data.py --list
  python scripts/download_data.py --site Site04 --dry-run
  python scripts/download_data.py --site Site04 --site Site01            # all five products per site
  python scripts/download_data.py --site Site04 --products surf,toterr   # subset
  python scripts/download_data.py --site Site04 --clones 10              # also N DEM clones (optional)
"""
import argparse, hashlib, json, os, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from app.terrain.ingestion import registry  # noqa: E402


def head(url):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "lunar-moon-navigator/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return int(r.headers.get("Content-Length", 0))


def fetch(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    part = dest + ".part"
    have = os.path.getsize(part) if os.path.exists(part) else 0
    req = urllib.request.Request(url, headers={"User-Agent": "lunar-moon-navigator/1.0", **({"Range": f"bytes={have}-"} if have else {})})
    try:
        r = urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as e:
        if e.code == 416:      # already complete
            os.replace(part, dest); return
        raise
    mode = "ab" if (have and r.status == 206) else "wb"
    total = int(r.headers.get("Content-Length", 0)) + (have if mode == "ab" else 0)
    done = have if mode == "ab" else 0
    t0 = time.time()
    with open(part, mode) as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk); done += len(chunk)
            sys.stdout.write(f"\r  {done / 1e6:8.1f} / {total / 1e6:.1f} MB  {done / max(time.time() - t0, 1) / 1e6:5.1f} MB/s")
            sys.stdout.flush()
    print()
    os.replace(part, dest)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", action="append", default=[], help="PGDA site key, e.g. Site04 (repeatable)")
    ap.add_argument("--products", default=",".join(registry.PRODUCTS), help="comma list of: " + ",".join(registry.PRODUCTS))
    ap.add_argument("--clones", type=int, default=0, help="number of DEM clones to fetch (0 = none)")
    ap.add_argument("--dest", default=registry.data_dir(), help="data directory (default: $TERRAIN_DATA_DIR or ./data)")
    ap.add_argument("--dry-run", action="store_true", help="only print URLs and sizes")
    ap.add_argument("--list", action="store_true", help="list known site keys and the app sites they map to")
    a = ap.parse_args()
    if a.list:
        inv = {v: k for k, v in registry.DB_SITE_TO_PGDA.items()}
        for k, n in registry.SITES.items():
            print(f"{k:10s} {n:38s} {('-> app site: ' + inv[k]) if k in inv else ''}")
        return
    if not a.site:
        ap.error("--site is required (see --list)")
    log_path = os.path.join(a.dest, "metadata", "downloads.json")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    log = json.load(open(log_path)) if os.path.exists(log_path) else []
    suffixes = [s.strip() for s in a.products.split(",") if s.strip()]
    for s in suffixes:
        if s not in registry.PRODUCTS:
            ap.error(f"unknown product '{s}'")
    jobs = []
    for key in a.site:
        if key not in registry.SITES:
            print(f"warning: '{key}' is not in the registry (continuing; URL may not exist)")
        for s in suffixes:
            jobs.append((registry.product_url(key, s), os.path.join(a.dest, "raw", key, registry.filename(key, s)), key, s))
        for n in range(1, a.clones + 1):
            jobs.append((registry.clone_url(key, n), os.path.join(a.dest, "raw", key, "Clones", os.path.basename(registry.clone_url(key, n))), key, f"clone{n}"))
    for url, dest, key, role in jobs:
        print(url)
        if a.dry_run:
            try:
                print(f"  size: {head(url) / 1e6:.1f} MB")
            except Exception as e:
                print(f"  (size unavailable: {e})")
            continue
        if os.path.exists(dest):
            print("  already present, skipping"); continue
        try:
            fetch(url, dest)
        except Exception as e:
            print(f"  FAILED: {e}"); continue
        digest = sha256(dest)
        log.append({"site": key, "role": role, "url": url, "path": dest, "bytes": os.path.getsize(dest), "sha256": digest,
                    "downloaded_at": datetime.now(timezone.utc).isoformat()})
        json.dump(log, open(log_path, "w"), indent=1)
        print(f"  sha256 {digest}")
    print("Done. Source: " + registry.PRODUCT_PAGE + "  (cite NASA/GSFC PGDA, LRO LOLA team)")


if __name__ == "__main__":
    main()
