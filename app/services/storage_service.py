import json
from uuid import uuid4

from google.cloud import storage

from app.core.config import get_settings


class StorageService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _client(self) -> storage.Client:
        if self.settings.gcp_credentials_json:
            info = json.loads(self.settings.gcp_credentials_json)
            return storage.Client.from_service_account_info(info, project=self.settings.gcp_project_id or None)
        return storage.Client(project=self.settings.gcp_project_id or None)

    def upload_bytes(
        self,
        content: bytes,
        content_type: str,
        folder: str | None = None,
    ) -> str:
        if not self.settings.gcp_storage_bucket:
            raise ValueError("GCP storage bucket missing")
        client = self._client()
        bucket = client.bucket(self.settings.gcp_storage_bucket)
        name = f"{folder.strip('/')}/" if folder else ""
        blob = bucket.blob(f"{name}{uuid4()}")
        blob.upload_from_string(content, content_type=content_type)
        blob.make_public()
        return blob.public_url
