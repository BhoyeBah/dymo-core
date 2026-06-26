import os
import shutil
import structlog
from abc import ABC, abstractmethod
from typing import Optional
from pathlib import Path

logger = structlog.get_logger(__name__)

class StorageProvider(ABC):
    @abstractmethod
    def upload_file(self, file_name: str, file_data: bytes, content_type: Optional[str] = None) -> str:
        """
        Uploads a file and returns its public URL/path.
        """
        pass

    @abstractmethod
    def delete_file(self, file_url: str) -> bool:
        """
        Deletes a file by its URL/path.
        """
        pass


class LocalStorageProvider(StorageProvider):
    def __init__(self, base_dir: str = "storage/uploads"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def upload_file(self, file_name: str, file_data: bytes, content_type: Optional[str] = None) -> str:
        dest_path = self.base_dir / file_name
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(file_data)
        return str(dest_path.absolute())

    def delete_file(self, file_url: str) -> bool:
        try:
            path = Path(file_url)
            if path.exists():
                path.unlink()
                return True
        except Exception as e:
            logger.error("Failed to delete local file", file_url=file_url, error=str(e))
        return False


class S3StorageProvider(StorageProvider):
    def __init__(
        self,
        bucket_name: str,
        access_key_id: str,
        secret_access_key: str,
        endpoint_url: Optional[str] = None,
        region_name: Optional[str] = None
    ):
        import boto3
        session = boto3.Session(
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region_name
        )
        self.s3_client = session.client("s3", endpoint_url=endpoint_url)
        self.bucket_name = bucket_name
        self.endpoint_url = endpoint_url
        self.region_name = region_name

    def upload_file(self, file_name: str, file_data: bytes, content_type: Optional[str] = None) -> str:
        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type
        # Add public-read ACL to make the uploaded object readable via URL
        extra_args["ACL"] = "public-read"
        
        from io import BytesIO
        self.s3_client.upload_fileobj(
            BytesIO(file_data),
            self.bucket_name,
            file_name,
            ExtraArgs=extra_args
        )
        
        if self.endpoint_url:
            url = f"{self.endpoint_url.rstrip('/')}/{self.bucket_name}/{file_name}"
        else:
            region_part = f".{self.region_name}" if self.region_name else ""
            url = f"https://{self.bucket_name}.s3{region_part}.amazonaws.com/{file_name}"
        return url

    def delete_file(self, file_url: str) -> bool:
        # Extract object key from the end of the URL
        key = file_url.split("/")[-1]
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except Exception as e:
            logger.error("Failed to delete S3 file", file_url=file_url, error=str(e))
            return False


def get_storage_service() -> StorageProvider:
    from dymo_saas_core.core.config import settings
    if settings.STORAGE_PROVIDER == "s3":
        if not all([settings.S3_BUCKET_NAME, settings.S3_ACCESS_KEY_ID, settings.S3_SECRET_ACCESS_KEY]):
            logger.warning("S3 Storage provider requested but credentials/bucket missing. Falling back to Local.")
            return LocalStorageProvider()
        try:
            return S3StorageProvider(
                bucket_name=settings.S3_BUCKET_NAME,
                access_key_id=settings.S3_ACCESS_KEY_ID,
                secret_access_key=settings.S3_SECRET_ACCESS_KEY,
                endpoint_url=settings.S3_ENDPOINT_URL,
                region_name=settings.S3_REGION_NAME
            )
        except Exception as e:
            logger.warning("Failed to initialize S3 storage provider. Falling back to Local.", error=str(e))
    return LocalStorageProvider()

storage_service = get_storage_service()
