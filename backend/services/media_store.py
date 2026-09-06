"""Media Store — upload/download assets to R2.

Real R2 integration using boto3. No fake URLs.

Cloudflare recommends bucket-scoped API tokens for R2.
Reference: https://developers.cloudflare.com/r2/examples/aws/boto3/
"""

import hashlib
import os
import uuid
from pathlib import Path

import boto3


class MediaStore:
    """Upload and retrieve media assets from Cloudflare R2."""

    def __init__(self):
        self._client = None

    @property
    def client(self):
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
        return os.getenv("R2_BUCKET", "freak-town")

    @property
    def configured(self) -> bool:
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
