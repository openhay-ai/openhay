from __future__ import annotations

import base64
import smtplib
from abc import ABC, abstractmethod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Iterable

from backend.settings import settings


class BaseEmailService(ABC):
    @abstractmethod
    def send(
        self,
        *,
        subject: str,
        text_body: str | None,
        html_body: str | None,
        extra_headers: dict[str, str] | None = None,
        reply_to: str | None = None,
        attachments: Iterable[tuple[str, str, str]] | None = None,
    ) -> None:
        """Send an email.

        attachments: iterable of (filename, content, subtype), where subtype is
        used as the MIMEText subtype (e.g., "yaml" for text/yaml).
        """


class SMTPEmailService(BaseEmailService):
    def send(
        self,
        *,
        subject: str,
        text_body: str | None,
        html_body: str | None,
        extra_headers: dict[str, str] | None = None,
        reply_to: str | None = None,
        attachments: Iterable[tuple[str, str, str]] | None = None,
    ) -> None:
        to_email = settings.support_owner_email or settings.support_from_email
        from_email = settings.support_from_email or settings.smtp_username or to_email
        host = settings.smtp_host
        port = settings.smtp_port
        username = settings.smtp_username
        password = settings.smtp_password
        use_tls = settings.smtp_use_tls

        if not host or not port or not to_email or not from_email:
            raise RuntimeError("SMTP not configured")

        root = MIMEMultipart("mixed")
        root["Subject"] = subject
        root["From"] = from_email
        root["To"] = to_email
        if reply_to:
            root["Reply-To"] = reply_to
        if extra_headers:
            for key, value in extra_headers.items():
                is_simple = all(ch.isalnum() or ch in "-" for ch in key)
                if key and is_simple:
                    root[key] = value

        alt = MIMEMultipart("alternative")
        if text_body:
            alt.attach(MIMEText(text_body, "plain", _charset="utf-8"))
        if html_body:
            alt.attach(MIMEText(html_body, "html", _charset="utf-8"))
        root.attach(alt)

        if attachments:
            for filename, content, subtype in attachments:
                part = MIMEText(content, _subtype=subtype, _charset="utf-8")
                part.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=filename,
                )
                root.attach(part)

        try:
            if port == 465:
                server = smtplib.SMTP_SSL(host, port)
            else:
                server = smtplib.SMTP(host, port)
                if use_tls:
                    server.starttls()
            if username and password:
                server.login(username, password)
            server.sendmail(from_email, [to_email], root.as_string())
            server.quit()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"SMTP send error: {type(exc).__name__}: {exc}") from exc


class ResendEmailService(BaseEmailService):
    def send(
        self,
        *,
        subject: str,
        text_body: str | None,
        html_body: str | None,
        extra_headers: dict[str, str] | None = None,
        reply_to: str | None = None,
        attachments: Iterable[tuple[str, str, str]] | None = None,
    ) -> None:
        to_email = settings.support_owner_email or settings.support_from_email
        from_email = settings.support_from_email or settings.smtp_username or to_email
        if not settings.resend_api_key:
            raise RuntimeError("Resend not configured: missing RESEND_API_KEY")
        if not to_email or not from_email:
            raise RuntimeError("Resend not configured: missing support emails")

        try:
            import resend  # type: ignore

            resend.api_key = settings.resend_api_key

            payload: dict[str, object] = {
                "from": from_email,
                "to": [to_email],
                "subject": subject,
            }
            if html_body:
                payload["html"] = html_body
            if text_body:
                payload["text"] = text_body
            if reply_to:
                payload["reply_to"] = reply_to
            if extra_headers:
                payload["headers"] = extra_headers

            if attachments:
                encoded_attachments: list[dict[str, str]] = []
                for filename, content, _subtype in attachments:
                    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
                    encoded_attachments.append({"filename": filename, "content": encoded})
                payload["attachments"] = encoded_attachments

            resend.Emails.send(payload)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Resend send error: {type(exc).__name__}: {exc}") from exc


def get_email_service() -> BaseEmailService:
    if settings.email_provider == "resend":
        return ResendEmailService()
    return SMTPEmailService()


def send_email(
    subject: str,
    text_body: str | None,
    html_body: str | None,
    *,
    extra_headers: dict[str, str] | None = None,
    reply_to: str | None = None,
    attachments: Iterable[tuple[str, str, str]] | None = None,
) -> None:
    """Backward-compatible wrapper around the configured email service."""
    service = get_email_service()
    service.send(
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        extra_headers=extra_headers,
        reply_to=reply_to,
        attachments=attachments,
    )


__all__ = [
    "BaseEmailService",
    "SMTPEmailService",
    "ResendEmailService",
    "get_email_service",
    "send_email",
]
