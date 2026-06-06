"""
MinIO Client Wrapper

Provides file download from MinIO object storage.
Used by document parser to retrieve uploaded files for processing.
"""

from __future__ import annotations

import io
import logging
import tempfile
from pathlib import Path
from typing import Optional

from minio import Minio
from minio.error import S3Error

from app.core.config import settings

logger = logging.getLogger(__name__)


class MinioClient:
    """
    Singleton MinIO client wrapper.

    Usage::

        client = MinioClient.get_client()
        file_bytes = client.download_file("kb/1/pdf/abc123.pdf")
        tmp_path = client.download_to_temp("kb/1/pdf/abc123.pdf")
    """

    _instance: Optional["MinioClient"] = None
    _minio: Optional[Minio] = None

    def __init__(self) -> None:
        self._minio = Minio(
            endpoint=settings.minio_endpoint_clean,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        self._bucket = settings.MINIO_BUCKET
        self._ensure_bucket()

    # ---- Singleton ----

    @classmethod
    def get_client(cls) -> "MinioClient":
        """Return the singleton MinioClient instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ---- Download Methods ----

    def download_file(self, object_name: str) -> bytes:
        """
        Download file from MinIO and return raw bytes.

        Args:
            object_name: MinIO object path, e.g. "1/pdf/abc123.pdf"

        Returns:
            File content as bytes.

        Raises:
            FileNotFoundError: if object does not exist.
        """
        try:
            response = self._minio.get_object(self._bucket, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            logger.info(
                "MinIO download success: bucket=%s, object=%s, size=%d",
                self._bucket, object_name, len(data),
            )
            return data
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise FileNotFoundError(
                    f"MinIO object not found: bucket={self._bucket}, "
                    f"object={object_name}"
                ) from e
            logger.error("MinIO download error: %s", e)
            raise RuntimeError(f"MinIO download failed: {e}") from e

    def download_to_temp(self, object_name: str, suffix: str = "") -> Path:
        """
        Download file from MinIO to a temporary file.

        Useful for large files or when a file path is needed
        (e.g. python-docx requires a file path).

        Args:
            object_name: MinIO object path.
            suffix:   Optional file extension suffix for the temp file
                      (e.g. ".pdf", ".docx"). If empty, inferred from
                      object_name.

        Returns:
            Path to the temporary file.

        Note:
            The caller is responsible for deleting the temp file after use.
        """
        if not suffix and "." in object_name:
            suffix = "." + object_name.rsplit(".", 1)[-1]

        data = self.download_file(object_name)

        # Write to temp file (delete=False so caller controls lifecycle)
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp.write(data)
        tmp.flush()
        tmp.close()

        logger.debug(
            "MinIO file saved to temp: object=%s, tmp=%s, size=%d",
            object_name, tmp.name, len(data),
        )
        return Path(tmp.name)

    def download_to_stream(self, object_name: str) -> io.BytesIO:
        """
        Download file from MinIO and return as BytesIO stream.

        Args:
            object_name: MinIO object path.

        Returns:
            BytesIO stream positioned at the beginning.
        """
        data = self.download_file(object_name)
        return io.BytesIO(data)

    def file_exists(self, object_name: str) -> bool:
        """
        Check whether an object exists in MinIO.

        Args:
            object_name: MinIO object path.

        Returns:
            True if the object exists.
        """
        try:
            self._minio.stat_object(self._bucket, object_name)
            return True
        except S3Error:
            return False

    def get_file_size(self, object_name: str) -> int:
        """
        Get file size in bytes without downloading.

        Args:
            object_name: MinIO object path.

        Returns:
            File size in bytes.
        """
        try:
            stat = self._minio.stat_object(self._bucket, object_name)
            return stat.size
        except S3Error as e:
            raise FileNotFoundError(
                f"MinIO object not found: {object_name}"
            ) from e

    # ---- Private ----

    def _ensure_bucket(self) -> None:
        """Ensure the configured bucket exists, creating it if necessary."""
        try:
            exists = self._minio.bucket_exists(self._bucket)
            if not exists:
                self._minio.make_bucket(self._bucket)
                logger.info("MinIO bucket created: %s", self._bucket)
            else:
                logger.debug("MinIO bucket exists: %s", self._bucket)
        except S3Error as e:
            logger.error("MinIO bucket check failed: %s", e)
            raise RuntimeError(f"MinIO bucket initialization failed: {e}") from e


# ==================== Module-level convenience ====================

def download_file(object_name: str) -> bytes:
    """Convenience function: download file bytes from MinIO."""
    return MinioClient.get_client().download_file(object_name)


def download_to_temp(object_name: str, suffix: str = "") -> Path:
    """Convenience function: download to temp file path."""
    return MinioClient.get_client().download_to_temp(object_name, suffix)
