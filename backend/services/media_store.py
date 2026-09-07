"""Media Store — upload/download assets to R2.

Real R2 integration using boto3. Falls back gracefully if boto3 is not installed.
"""

import hashlib
import logging
import os
from pathlib import Path

logger = logging.getLogger("freak_town.media")

try:
    import boto3
    _HAS_BOTO3 = True
except ImportError:
    _HAS_BOTO3 = False
    logger.info("boto3 not installed — R2 media store disabled. Install with: pip install boto3")


class MediaStore:
    """Upload and retrieve media assets from Cloudflare R2."""

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if not _HAS_BOTO3:
            raise RuntimeError("boto3 not installed. Run: pip install boto3")
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=os.getenv("R2_S3_ENDPOINT", ""),
                aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID", ""),
                aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY", ""),
                region_name="auto",
            )
        return self._client

    @property
    def bucket(self) -> str:
        # Canonical bucket (matches Worker wrangler.jsonc R2 binding).
        # Two different defaults here vs there once meant two different
        # buckets in production — never again.
        return os.getenv("R2_BUCKET", "freak-town-assets")

    @property
    def configured(self) -> bool:
        if not _HAS_BOTO3:
            return False
        return bool(os.getenv("R2_S3_ENDPOINT")) and bool(os.getenv("R2_ACCESS_KEY_ID"))

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> dict:
        """Upload bytes to R2. Returns metadata dict."""
        sha256 = hashlib.sha256(data).hexdigest()

        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

        return {
            "r2_key": key,
            "file_size_bytes": len(data),
            "sha256": sha256,
        }

    def put_audio(self, draft_id: str, audio_bytes: bytes, format: str = "mp3") -> dict:
        """Upload TTS audio for a draft."""
        sha256 = hashlib.sha256(audio_bytes).hexdigest()
        key = f"drafts/{draft_id}/audio/{sha256[:16]}.{format}"

        content_type = "audio/mpeg" if format == "mp3" else "audio/ogg"
        return self.put_bytes(key, audio_bytes, content_type)

    def put_performance_plan(self, act_version_id: str, plan_json: bytes) -> dict:
        """Upload a sealed performance plan."""
        sha256 = hashlib.sha256(plan_json).hexdigest()
        key = f"acts/{act_version_id}/plan/{sha256[:16]}.json"
        return self.put_bytes(key, plan_json, "application/json")

    def put_word_timings(self, act_version_id: str, timings_json: bytes) -> dict:
        """Upload sealed word timings."""
        sha256 = hashlib.sha256(timings_json).hexdigest()
        key = f"acts/{act_version_id}/timings/{sha256[:16]}.json"
        return self.put_bytes(key, timings_json, "application/json")

    def put_manifest(self, act_version_id: str, manifest_json: bytes) -> dict:
        """Upload a sealed freaktown.performance.v1 manifest.

        Fixed key (acts/{id}/manifest.json): acts are immutable, so the
        manifest is written once and served back by GET /v1/performances.
        """
        key = f"acts/{act_version_id}/manifest.json"
        return self.put_bytes(key, manifest_json, "application/json")

    def put_set_audio(self, act_version_id: str, audio_bytes: bytes, format: str = "wav") -> dict:
        """Upload a sealed set recording under a fixed, servable key."""
        content_type = {
            "wav": "audio/wav", "mp3": "audio/mpeg", "ogg": "audio/ogg",
        }.get(format, "application/octet-stream")
        key = f"acts/{act_version_id}/set.{format}"
        return self.put_bytes(key, audio_bytes, content_type)

    def get_bytes(self, key: str) -> bytes:
        """Download an object. Raises RuntimeError when unconfigured."""
        if not self.configured:
            raise RuntimeError("R2 media store not configured")
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def get_signed_url(self, key: str, expires_in: int = 3600) -> str:
        """Get a signed URL for reading an object."""
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def head(self, key: str) -> dict | None:
        """Check if an object exists and get its metadata."""
        try:
            response = self.client.head_object(Bucket=self.bucket, Key=key)
            return {
                "content_length": response["ContentLength"],
                "content_type": response.get("ContentType", ""),
                "sha256": response.get("Metadata", {}).get("sha256", ""),
            }
        except self.client.exceptions.ClientError:
            return None

    def delete(self, key: str):
        """Delete an object."""
        self.client.delete_object(Bucket=self.bucket, Key=key)


# Singleton
media_store = MediaStore()
