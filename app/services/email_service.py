"""Email delivery service."""

from pathlib import Path

import resend

from app.core.config import get_settings
from app.utils.email import build_reset_url, build_verify_url


class EmailService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.template_dir = Path(__file__).resolve().parents[1] / "email_templates"

    def _render_template(self, name: str, context: dict) -> str:
        template_path = self.template_dir / name
        if not template_path.exists():
            raise ValueError("Email template missing")
        return template_path.read_text(encoding="utf-8").format(**context)

    def _send(self, email: str, subject: str, html: str) -> None:
        if not self.settings.resend_api_key or not self.settings.email_from:
            raise ValueError("Email configuration missing")
        resend.api_key = self.settings.resend_api_key
        resend.Emails.send(
            {
                "from": self.settings.email_from,
                "to": email,
                "subject": subject,
                "html": html,
            }
        )

    def send_verification_email(self, email: str, first_name: str, token: str) -> None:
        if not self.settings.frontend_base_url:
            raise ValueError("Email configuration missing")
        verify_url = build_verify_url(self.settings.frontend_base_url, token)
        html = self._render_template(
            "verify_email.html",
            {
                "first_name": first_name,
                "otp_code": token,
                "verify_url": verify_url,
            },
        )
        self._send(email, "Verify your email", html)

    def send_password_reset_email(self, email: str, token: str) -> None:
        if not self.settings.frontend_base_url:
            raise ValueError("Email configuration missing")
        reset_url = build_reset_url(self.settings.frontend_base_url, token)
        html = self._render_template("reset_password.html", {"reset_url": reset_url})
        self._send(email, "Reset your password", html)

    def send_welcome_email(self, email: str, first_name: str) -> None:
        html = self._render_template("welcome_email.html", {"first_name": first_name})
        self._send(email, "Welcome to RideSeat", html)

    def send_trip_completed_email(
        self,
        email: str,
        first_name: str,
        origin_city: str,
        destination_city: str,
        departure_time: str,
    ) -> None:
        html = self._render_template(
            "trip_completed.html",
            {
                "first_name": first_name,
                "origin_city": origin_city,
                "destination_city": destination_city,
                "departure_time": departure_time,
            },
        )
        self._send(email, "Trip completed", html)
