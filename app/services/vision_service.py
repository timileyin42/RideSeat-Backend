"""Google Cloud Vision OCR service for document verification."""

import base64
import json
import re

from app.core.config import get_settings

_DVLA_PATTERN = re.compile(r"[A-Z9]{5}\d{6}[A-Z]{2}\d[A-Z]{2}")


class VisionService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _client(self):
        from google.cloud import vision as gv

        creds_json = self.settings.gcp_credentials_json
        if creds_json:
            raw = base64.b64decode(creds_json).decode("utf-8")
            info = json.loads(raw)
            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_info(info)
            return gv.ImageAnnotatorClient(credentials=credentials)
        return gv.ImageAnnotatorClient()

    def extract_text(self, image_bytes: bytes) -> str:
        from google.cloud import vision as gv

        client = self._client()
        image = gv.Image(content=image_bytes)
        response = client.text_detection(image=image)
        if response.error.message:
            return ""
        annotations = response.text_annotations
        return annotations[0].description if annotations else ""

    def extract_licence_number(self, image_bytes: bytes) -> str | None:
        """Return the first DVLA-format licence number found in the image, or None."""
        text = self.extract_text(image_bytes)
        normalised = text.upper().replace(" ", "").replace("\n", "")
        match = _DVLA_PATTERN.search(normalised)
        return match.group(0) if match else None
