"""Email delivery service."""

from pathlib import Path

import resend

from app.core.config import get_settings
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
        padded = token.ljust(6)
        html = self._render_template(
            "verify_email.html",
            {
                "first_name": first_name,
                "d0": padded[0], "d1": padded[1], "d2": padded[2],
                "d3": padded[3], "d4": padded[4], "d5": padded[5],
            },
        )
        self._send(email, "Verify your Rideway email", html)

    def send_welcome_email(self, email: str, first_name: str) -> None:
        html = self._render_template("welcome_email.html", {"first_name": first_name})
        self._send(email, "Welcome to RideWay", html)

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

    def send_password_reset_email(self, email: str, token: str) -> None:
        padded = token.ljust(6)
        html = self._render_template(
            "reset_password.html",
            {
                "d0": padded[0], "d1": padded[1], "d2": padded[2],
                "d3": padded[3], "d4": padded[4], "d5": padded[5],
            },
        )
        self._send(email, "Reset your Rideway password", html)

    def send_verification_submitted_email(self, email: str, first_name: str) -> None:
        html = self._render_template("verification_submitted.html", {"first_name": first_name})
        self._send(email, "We've received your documents — under review", html)

    def send_verification_approved_email(self, email: str, first_name: str) -> None:
        html = self._render_template("verification_approved.html", {"first_name": first_name})
        self._send(email, "You're verified on Rideway 🎉", html)

    def send_verification_rejected_email(self, email: str, first_name: str, reason: str | None = None) -> None:
        if reason:
            reason_block = (
                f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin:0 0 24px;">'
                f'<tr><td style="background:#FEF2F2;border-radius:12px;padding:16px 20px;border-left:4px solid #EF4444;">'
                f'<p style="margin:0 0 4px;font-size:13px;font-weight:700;color:#991B1B;">Reason from our team</p>'
                f'<p style="margin:0;font-size:13px;color:#7F1D1D;line-height:1.6;">{reason}</p>'
                f'</td></tr></table>'
            )
        else:
            reason_block = ""
        html = self._render_template(
            "verification_rejected.html",
            {"first_name": first_name, "reason_block": reason_block},
        )
        self._send(email, "Rideway verification — action required", html)

    def send_admin_verification_alert(
        self,
        admin_email: str,
        driver_name: str,
        driver_email: str,
        driver_id: str,
    ) -> None:
        html = self._render_template(
            "admin_verification_alert.html",
            {
                "driver_name": driver_name,
                "driver_email": driver_email,
                "driver_id": driver_id,
            },
        )
        self._send(admin_email, f"[Action required] Driver verification: {driver_name}", html)

    def send_booking_request_email(
        self,
        email: str,
        first_name: str,
        passenger_name: str,
        origin_city: str,
        destination_city: str,
        departure_time: str,
    ) -> None:
        html = self._render_template(
            "booking_request.html",
            {
                "first_name": first_name,
                "passenger_name": passenger_name,
                "origin_city": origin_city,
                "destination_city": destination_city,
                "departure_time": departure_time,
            },
        )
        self._send(email, "New booking request", html)
