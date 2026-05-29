import base64
import json
from datetime import timedelta
from uuid import uuid4

from google.cloud import storage
from google.oauth2 import service_account

from app.core.config import get_settings

# Folders whose content is always publicly accessible (profile/vehicle photos)
_PUBLIC_FOLDERS = {"avatars", "vehicles"}

# Folders that are private — signed URLs generated on demand
_PRIVATE_FOLDERS = {"driver_licences", "selfies", "id_documents"}


class StorageService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _client(self) -> storage.Client:
        if self.settings.gcp_credentials_json:
            raw = base64.b64decode(self.settings.gcp_credentials_json).decode("utf-8")
            info = json.loads(raw)
            return storage.Client.from_service_account_info(info, project=self.settings.gcp_project_id or None)
        return storage.Client(project=self.settings.gcp_project_id or None)

    def _credentials(self):
        """Return service account credentials (needed for signed URL generation)."""
        if self.settings.gcp_credentials_json:
            raw = base64.b64decode(self.settings.gcp_credentials_json).decode("utf-8")
            info = json.loads(raw)
            return service_account.Credentials.from_service_account_info(info)
        return None

    def upload_bytes(
        self,
        content: bytes,
        content_type: str,
        folder: str | None = None,
    ) -> str:
        """Upload bytes and return a URL.

        Public folders (avatars, vehicles) return a permanent public URL.
        Private folders (driver_licences, selfies, id_documents) return the
        GCS object path (gs://bucket/path) — call signed_url() to get a
        time-limited link when you actually need to display the file.
        """
        if not self.settings.gcp_storage_bucket:
            raise ValueError("GCP storage bucket missing")
        client = self._client()
        bucket = client.bucket(self.settings.gcp_storage_bucket)
        folder_name = folder.strip("/") if folder else ""
        blob_name = f"{folder_name}/{uuid4()}" if folder_name else str(uuid4())
        blob = bucket.blob(blob_name)
        blob.upload_from_string(content, content_type=content_type)

        if folder_name in _PUBLIC_FOLDERS:
            blob.make_public()
            return blob.public_url

        # Private — store the GCS path; use signed_url() to view
        return f"gs://{self.settings.gcp_storage_bucket}/{blob_name}"

    def signed_url(self, gcs_path: str, expiry_minutes: int = 15) -> str:
        """Generate a time-limited signed URL for a private GCS object.

        Pass the gs://bucket/path string returned by upload_bytes() for
        private folders. Returns a URL valid for `expiry_minutes` minutes.
        """
        if not gcs_path.startswith("gs://"):
            # Already a public URL — return as-is
            return gcs_path
        without_scheme = gcs_path[len("gs://"):]
        bucket_name, _, blob_name = without_scheme.partition("/")
        credentials = self._credentials()
        client = self._client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        return blob.generate_signed_url(
            expiration=timedelta(minutes=expiry_minutes),
            method="GET",
            credentials=credentials,
        )
