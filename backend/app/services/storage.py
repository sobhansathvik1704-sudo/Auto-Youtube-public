"""Unified storage service supporting local filesystem and AWS S3 backends.

Set ``STORAGE_BACKEND=s3`` in the environment and supply the AWS credentials
(``AWS_ACCESS_KEY_ID``, ``AWS_SECRET_ACCESS_KEY``, ``AWS_S3_BUCKET_NAME``,
``AWS_REGION``) to switch all asset persistence to S3.  The default backend
is ``local``, which writes files to ``ARTIFACTS_DIR`` on the local filesystem.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from app.core.config import get_settings
from app.utils.fs import ensure_dir

logger = logging.getLogger(__name__)


class StorageService:
    """Abstraction over local-disk and AWS S3 storage.

    All pipeline code should interact with assets exclusively through this
    class so that switching between backends requires only a configuration
    change.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.backend: str = self.settings.storage_backend
        self.local_root: Path = ensure_dir(Path(self.settings.artifacts_dir))
        self._s3 = None  # lazy-initialised boto3 client

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def _s3_client(self):
        """Return a boto3 S3 client, creating it on first access."""
        if self._s3 is None:
            import boto3  # noqa: PLC0415

            self._s3 = boto3.client(
                "s3",
                region_name=self.settings.aws_region,
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key,
            )
        return self._s3

    def _s3_key(self, project_id: str, job_id: str, relative_path: str) -> str:
        return f"{project_id}/{job_id}/{relative_path}"

    def _local_artifact_path(self, project_id: str, job_id: str, relative_path: str) -> Path:
        base = self.job_dir(project_id, job_id)
        rel = Path(relative_path)
        return ensure_dir(base / rel.parent) / rel.name

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def job_dir(self, project_id: str, job_id: str) -> Path:
        """Return (and create) the local working directory for a job.

        This directory is always on the local filesystem and is used for
        intermediate pipeline files such as TTS audio clips and FFmpeg
        inputs/outputs.  When using the S3 backend, final artifacts are
        uploaded after they have been written here.
        """
        return ensure_dir(self.local_root / project_id / job_id)

    def write_text(
        self,
        project_id: str,
        job_id: str,
        relative_path: str,
        content: str,
    ) -> str:
        """Write *content* to storage and return the storage key.

        For the ``local`` backend the storage key is the absolute local path.
        For the ``s3`` backend the file is written locally first and then
        uploaded; the returned storage key is the S3 object key.
        """
        local_path = self._local_artifact_path(project_id, job_id, relative_path)
        local_path.write_text(content, encoding="utf-8")
        if self.backend == "s3":
            key = self._s3_key(project_id, job_id, relative_path)
            self._upload_to_s3(local_path, key)
            return key
        return str(local_path)

    def write_bytes(
        self,
        project_id: str,
        job_id: str,
        relative_path: str,
        content: bytes,
    ) -> str:
        """Write binary *content* to storage and return the storage key."""
        local_path = self._local_artifact_path(project_id, job_id, relative_path)
        local_path.write_bytes(content)
        if self.backend == "s3":
            key = self._s3_key(project_id, job_id, relative_path)
            self._upload_to_s3(local_path, key)
            return key
        return str(local_path)

    def upload_file(
        self,
        local_path: Path,
        project_id: str,
        job_id: str,
        relative_path: str,
    ) -> str:
        """Upload an already-existing local file to storage.

        This is used after FFmpeg produces its output so that the rendered
        video is pushed to S3.  Returns the storage key (S3 key or local path).
        """
        if self.backend == "s3":
            key = self._s3_key(project_id, job_id, relative_path)
            self._upload_to_s3(local_path, key)
            return key
        return str(local_path)

    def download_file(self, storage_key: str, local_path: Path) -> None:
        """Download a file from storage to *local_path*.

        For the ``local`` backend *storage_key* is an absolute path and the
        file is copied.  For the ``s3`` backend it is an S3 object key.
        """
        local_path.parent.mkdir(parents=True, exist_ok=True)
        if self.backend == "s3":
            self._s3_client.download_file(
                self.settings.aws_s3_bucket_name,
                storage_key,
                str(local_path),
            )
        else:
            shutil.copy2(storage_key, local_path)

    def get_presigned_url(self, storage_key: str, expires_in: int = 3600) -> str | None:
        """Return a time-limited download URL for *storage_key*.

        Returns a presigned URL string for the S3 backend or ``None`` for the
        local backend (callers should fall back to a static-file endpoint).
        """
        if self.backend == "s3":
            return self._s3_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.settings.aws_s3_bucket_name,
                    "Key": storage_key,
                },
                ExpiresIn=expires_in,
            )
        return None

    @property
    def is_s3(self) -> bool:
        """``True`` when the active backend is AWS S3."""
        return self.backend == "s3"

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _upload_to_s3(self, local_path: Path, key: str) -> None:
        bucket = self.settings.aws_s3_bucket_name
        if not bucket:
            raise RuntimeError(
                "AWS_S3_BUCKET_NAME must be set when STORAGE_BACKEND=s3"
            )
        logger.debug("Uploading %s → s3://%s/%s", local_path, bucket, key)
        self._s3_client.upload_file(str(local_path), bucket, key)
        logger.info("Uploaded s3://%s/%s", bucket, key)
