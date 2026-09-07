"""Infra consistency tests — defaults that must never drift apart.

The canonical bucket is 'freak-town' (matching Cloudflare R2).
These tests pin the canonical names.
"""

import os


class TestCanonicalNames:
    def test_r2_bucket_default(self):
        from backend.services.media_store import MediaStore

        env = os.environ.pop("R2_BUCKET", None)
        try:
            assert MediaStore().bucket == "freak-town"
        finally:
            if env is not None:
                os.environ["R2_BUCKET"] = env

    def test_r2_bucket_config_default(self):
        from backend.config import Settings

        assert Settings().r2_bucket == "freak-town"

    def test_worker_bucket_matches(self):
        import json

        with open("apps/web/wrangler.jsonc") as f:
            raw = f.read()
        # jsonc: strip line comments for parsing
        cleaned = "\n".join(
            line for line in raw.splitlines()
            if not line.strip().startswith("//")
        )
        cfg = json.loads(cleaned)
        buckets = [b["bucket_name"] for b in cfg.get("r2_buckets", [])]
        assert buckets == ["freak-town"]
