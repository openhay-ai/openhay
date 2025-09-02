from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Iterable

from backend.settings import settings


def send_email(
    subject: str,
    text_body: str | None,
    html_body: str | None,
    *,
    extra_headers: dict[str, str] | None = None,
    reply_to: str | None = None,
    attachments: Iterable[tuple[str, str, str]] | None = None,
) -> None:
    """Send an email to the configured owner using SMTP.

    attachments: iterable of (filename, content, subtype), where subtype is
    used as the MIMEText subtype (e.g., "yaml" for text/yaml).
    """

    host = settings.smtp_host
    port = settings.smtp_port
    username = settings.smtp_username
    password = settings.smtp_password
    use_tls = settings.smtp_use_tls
    to_email = settings.support_owner_email or settings.support_from_email
    from_email = settings.support_from_email or username or to_email

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


__all__ = ["send_email"]
