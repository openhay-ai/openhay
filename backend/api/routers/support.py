from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from backend.settings import settings
from loguru import logger


router = APIRouter(prefix="/api/support", tags=["support"])


class SupportRequest(BaseModel):
    email: EmailStr
    question: str


def _send_email(subject: str, html_body: str, text_body: str | None = None) -> None:
    host = getattr(settings, "smtp_host", None)
    port = getattr(settings, "smtp_port", None)
    username = getattr(settings, "smtp_username", None)
    password = getattr(settings, "smtp_password", None)
    use_tls = getattr(settings, "smtp_use_tls", True)
    to_email = getattr(settings, "support_owner_email", None)
    from_email = getattr(settings, "support_from_email", username or to_email)

    if not host or not port or not to_email or not from_email:
        raise RuntimeError("SMTP not configured")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email

    if text_body:
        msg.attach(MIMEText(text_body, "plain", _charset="utf-8"))
    msg.attach(MIMEText(html_body, "html", _charset="utf-8"))

    try:
        if use_tls:
            server = smtplib.SMTP(host, port)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(host, port)
        if username and password:
            server.login(username, password)
        server.sendmail(from_email, [to_email], msg.as_string())
        server.quit()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"SMTP send error: {type(exc).__name__}: {exc}") from exc


@router.post("")
async def submit_support(req: SupportRequest) -> dict[str, str]:
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question is required")

    smtp_configured = bool(
        getattr(settings, "smtp_host", None)
        and getattr(settings, "smtp_port", None)
        and (
            getattr(settings, "support_owner_email", None)
            or getattr(settings, "support_from_email", None)
        )
    )

    if not smtp_configured:
        # Dev fallback: avoid 500s in environments without SMTP configured
        logger.warning(
            "SMTP not configured. Logging support request instead. email={}, len(question)={}",
            req.email,
            len(req.question or ""),
        )
        return {"status": "ok"}

    subject = "[OpenHay] Yêu cầu hỗ trợ mới"
    html = f"""
    <h3>Yêu cầu hỗ trợ mới</h3>
    <p><strong>Email người dùng:</strong> {req.email}</p>
    <p><strong>Nội dung:</strong></p>
    <pre style='white-space:pre-wrap;font-family:ui-monospace,Menlo,monospace'>{req.question}</pre>
    """
    text = f"Yêu cầu hỗ trợ mới\nEmail: {req.email}\n\nNội dung:\n{req.question}"

    try:
        _send_email(subject, html, text)
    except RuntimeError as exc:
        # Surface clear error for frontend to display
        logger.exception("Failed to send support email via SMTP")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"status": "ok"}


__all__ = ["router"]
