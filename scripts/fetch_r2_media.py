"""Fetch R2 media to the local gitignored cache.

Reads pointers from assets/character-meshes/manifest.json and
comedy/theory/manifest.json, downloads bytes to data/character-meshes/
and data/comedy-theory/.

Credentials come from the environment only — never from the tree:

    export R2_S3_ENDPOINT="https://<account>.r2.cloudflarestorage.com"
    export R2_ACCESS_KEY_ID="..."
    export R2_SECRET_ACCESS_KEY="..."
    export R2_BUCKET="freak-town"   # optional, this is the default

    python3 scripts/fetch_r2_media.py --meshes
    python3 scripts/fetch_r2_media.py --theory
    python3 scripts/fetch_r2_media.py --papers
    python3 scripts/fetch_r2_media.py --all

Skips files already present with matching size.
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _client():
    try:
        import boto3
    except ImportError:
        sys.exit("boto3 not installed. Run: pip install boto3")
    endpoint = os.getenv("R2_S3_ENDPOINT", "")
    key = os.getenv("R2_ACCESS_KEY_ID", "")
    secret = os.getenv("R2_SECRET_ACCESS_KEY", "")
    if not (endpoint and key and secret):
        sys.exit("R2 not configured: set R2_S3_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY in env")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=key,
        aws_secret_access_key=secret,
        region_name="auto",
    )


def _fetch(s3, bucket, entries, dest_dir, kind):
    dest_dir.mkdir(parents=True, exist_ok=True)
    ok = 0
    for e in entries:
        key = e["r2_key"]
        target = dest_dir / e["filename"]
        if target.exists() and target.stat().st_size == e["size"]:
            print(f"SKIP {target} (size matches)")
            ok += 1
            continue
        print(f"GET {key} -> {target} ({e['size']} bytes)")
        s3.download_file(bucket, key, str(target))
        actual = target.stat().st_size
        if actual != e["size"]:
            sys.exit(f"SIZE MISMATCH {target}: manifest={e['size']} got={actual}")
        ok += 1
    print(f"{kind}: {ok}/{len(entries)} present")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meshes", action="store_true")
    ap.add_argument("--theory", action="store_true")
    ap.add_argument("--papers", action="store_true")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    if not (args.meshes or args.theory or args.papers or args.all):
        ap.print_help()
        sys.exit(1)

    bucket = os.getenv("R2_BUCKET", "freak-town")
    s3 = _client()

    if args.meshes or args.all:
        m = json.loads((ROOT / "assets/character-meshes/manifest.json").read_text())
        assert m["bucket"] == bucket, f"manifest bucket {m['bucket']} != R2_BUCKET {bucket}"
        _fetch(s3, bucket, m["meshes"], ROOT / "data/character-meshes", "meshes")

    if args.theory or args.all:
        m = json.loads((ROOT / "comedy/theory/manifest.json").read_text())
        assert m["bucket"] == bucket, f"manifest bucket {m['bucket']} != R2_BUCKET {bucket}"
        _fetch(s3, bucket, m["texts"], ROOT / "data/comedy-theory", "theory")

    if args.papers or args.all:
        m = json.loads((ROOT / "comedy/theory/papers.json").read_text())
        assert m["bucket"] == bucket, f"manifest bucket {m['bucket']} != R2_BUCKET {bucket}"
        entries = [p for p in m["papers"] if "filename" in p]
        _fetch(s3, bucket, [{"r2_key": p["r2_key"], "filename": p["filename"], "size": p["size"]} for p in entries],
                ROOT / "data/comedy-theory/papers", "papers")


if __name__ == "__main__":
    main()
