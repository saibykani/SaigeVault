"""Cloudflare R2 (S3-compatible) and in-memory object stores."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, BinaryIO

import anyio
import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from saige_api.core.logging import get_logger
from saige_api.storage.base import StorageNotFoundError, StorageUnavailableError

logger = get_logger("saige_api.storage")
CHUNK = 1024 * 1024


class R2ObjectStore:
    """Talks to R2 through boto3 (run in worker threads). Objects are private;
    content is only ever served through the API."""

    name = "r2"

    def __init__(
        self,
        *,
        endpoint: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
    ) -> None:
        self._bucket = bucket
        self._client: Any = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
            config=Config(
                retries={"max_attempts": 4, "mode": "standard"},
                connect_timeout=5,
                read_timeout=60,
                # R2 rejects the newer default integrity headers on some operations.
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )

    async def _call(self, fn: Any, **kwargs: Any) -> Any:
        try:
            return await anyio.to_thread.run_sync(lambda: fn(**kwargs))
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in {"NoSuchKey", "404", "NotFound"}:
                raise StorageNotFoundError("object not found") from exc
            logger.warning("r2_error", code=code)
            raise StorageUnavailableError("storage request failed") from exc
        except BotoCoreError as exc:
            logger.warning("r2_unreachable", error=type(exc).__name__)
            raise StorageUnavailableError("storage unreachable") from exc

    async def put(self, key: str, stream: BinaryIO, *, size: int, content_type: str) -> None:
        stream.seek(0)
        await self._call(
            self._client.upload_fileobj,
            Fileobj=stream,
            Bucket=self._bucket,
            Key=key,
            ExtraArgs={"ContentType": content_type},
        )

    async def get(self, key: str) -> AsyncIterator[bytes]:
        response = await self._call(self._client.get_object, Bucket=self._bucket, Key=key)
        body = response["Body"]
        try:
            while True:
                chunk = await anyio.to_thread.run_sync(body.read, CHUNK)
                if not chunk:
                    break
                yield chunk
        finally:
            body.close()

    async def delete(self, key: str) -> None:
        await self._call(self._client.delete_object, Bucket=self._bucket, Key=key)

    async def ping(self) -> None:
        await self._call(self._client.head_bucket, Bucket=self._bucket)


class MemoryObjectStore:
    """Process-local store for tests and local development without R2."""

    name = "memory"

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    async def put(self, key: str, stream: BinaryIO, *, size: int, content_type: str) -> None:
        stream.seek(0)
        self.objects[key] = (stream.read(), content_type)

    async def get(self, key: str) -> AsyncIterator[bytes]:
        if key not in self.objects:
            raise StorageNotFoundError("object not found")
        data = self.objects[key][0]
        for i in range(0, max(len(data), 1), CHUNK):
            yield data[i : i + CHUNK]

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    async def ping(self) -> None:
        return None


class MongoObjectStore:
    """File content in MongoDB GridFS (the `files_content` bucket).

    Needs no extra account: it uses the same database as the metadata. Good for
    small vaults (the Atlas free tier is 512 MB in total).
    """

    name = "mongodb"

    def __init__(self, db: Any) -> None:
        from gridfs import AsyncGridFSBucket  # noqa: PLC0415

        self._bucket = AsyncGridFSBucket(db, bucket_name="files_content")

    async def put(self, key: str, stream: BinaryIO, *, size: int, content_type: str) -> None:
        stream.seek(0)
        await self._bucket.upload_from_stream(
            key, stream, chunk_size_bytes=CHUNK // 4, metadata={"content_type": content_type}
        )

    async def get(self, key: str) -> AsyncIterator[bytes]:
        from gridfs.errors import NoFile  # noqa: PLC0415

        try:
            download = await self._bucket.open_download_stream_by_name(key)
        except NoFile as exc:
            raise StorageNotFoundError("object not found") from exc
        try:
            while chunk := await download.read(CHUNK):
                yield chunk
        finally:
            await download.close()

    async def delete(self, key: str) -> None:
        from gridfs.errors import NoFile  # noqa: PLC0415

        try:
            await self._bucket.delete_by_name(key)
        except NoFile:
            return

    async def ping(self) -> None:
        return None
