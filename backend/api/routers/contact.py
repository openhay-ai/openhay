from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from backend.core.services.email import send_email
from backend.settings import settings
from fastapi import APIRouter, HTTPException, Request
from loguru import logger
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/api/contact", tags=["contact"])


class SupportRequest(BaseModel):
    email: EmailStr
    question: str


def _send_email(
    subject: str,
    html_body: str,
    text_body: str | None = None,
    extra_headers: dict[str, str] | None = None,
    reply_to: str | None = None,
    attachments: list[tuple[str, str, str]] | None = None,
) -> None:
    try:
        send_email(
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            extra_headers=extra_headers or {},
            reply_to=reply_to,
            attachments=attachments or [],
        )
    except Exception as exc:  # noqa: BLE001
        msg = f"SMTP send error: {type(exc).__name__}: {exc}"
        raise RuntimeError(msg) from exc


def _get_client_ip(request: Request) -> str:
    xfwd = request.headers.get("x-forwarded-for", "")
    ip = (xfwd.split(",")[0].strip() if xfwd else None) or (
        request.client.host if request.client else ""
    )
    return ip


def _truncate_ip(ip: str) -> str:
    try:
        # IPv4 /24
        if "." in ip:
            parts = ip.split(".")
            return ".".join(parts[:3]) + ".0"
        # IPv6 coarse
        if ":" in ip:
            hextets = ip.split(":")
            return ":".join((hextets + ["0000"] * 8)[:3] + ["0000"] * 5)
    except Exception:
        pass
    return ""


def _hash_ip(ip: str, salt: str | None) -> str:
    if not ip or not salt:
        return ""
    import hashlib

    return hashlib.sha256((salt + ip).encode()).hexdigest()[:16]


def _smtp_configured() -> bool:
    return all(
        [
            settings.smtp_host,
            settings.smtp_port,
            any(
                [
                    settings.support_owner_email,
                    settings.support_from_email,
                ]
            ),
        ]
    )


def _compose_context(request: Request) -> dict[str, str]:
    request_id = str(uuid4())
    submitted_at = datetime.now(timezone.utc).isoformat()
    client_ip = _get_client_ip(request)
    user_ip_trunc = _truncate_ip(client_ip) if settings.collect_client_ip else ""
    user_ip_hash = (
        _hash_ip(client_ip, settings.analytics_ip_salt) if settings.collect_client_ip else ""
    )
    user_agent = request.headers.get("user-agent", "")
    return {
        "request_id": request_id,
        "submitted_at": submitted_at,
        "client_ip": client_ip,
        "user_ip_trunc": user_ip_trunc,
        "user_ip_hash": user_ip_hash,
        "user_agent": user_agent,
    }


def _build_text_and_yaml(
    *,
    event: str,
    user_email: str,
    include_client_ip: bool,
    include_ip_hash: bool,
    message: str | None,
    ctx: dict[str, str],
) -> tuple[str, str]:
    text_lines = [
        "---",
        "openhay_version: 1",
        f"event: {event}",
        f"user_email: {user_email}",
        f"submitted_at: {ctx['submitted_at']}",
        f"request_id: {ctx['request_id']}",
        "locale: vi",
        "source: web",
        (f"user_ip_truncated: {ctx['user_ip_trunc']}" if ctx.get("user_ip_trunc") else ""),
        (f"client_ip: {ctx['client_ip']}" if include_client_ip and ctx.get("client_ip") else ""),
        (
            f"user_ip_hash: {ctx['user_ip_hash']}"
            if include_ip_hash and ctx.get("user_ip_hash")
            else ""
        ),
        (f"user_agent: {ctx['user_agent']}" if ctx.get("user_agent") else ""),
        "---",
        message or "(no message)",
    ]
    text = "\n".join([line for line in text_lines if line])

    metadata_yaml_lines = [
        "openhay_version: 1",
        f"event: {event}",
        f"user_email: {user_email}",
        f"submitted_at: {ctx['submitted_at']}",
        f"request_id: {ctx['request_id']}",
        "locale: vi",
        "source: web",
        *([f"user_ip_truncated: {ctx['user_ip_trunc']}"] if ctx.get("user_ip_trunc") else []),
        *([f"client_ip: {ctx['client_ip']}"] if include_client_ip and ctx.get("client_ip") else []),
        *(
            [f"user_ip_hash: {ctx['user_ip_hash']}"]
            if include_ip_hash and ctx.get("user_ip_hash")
            else []
        ),
        *([f"user_agent: {ctx['user_agent']}"] if ctx.get("user_agent") else []),
    ]
    metadata_yaml = "\n".join(metadata_yaml_lines)
    return text, metadata_yaml


def _build_headers(
    *,
    event: str,
    user_email: str,
    request_id: str,
    ip_header_value: str | None,
) -> dict[str, str]:
    headers = {
        "X-OpenHay-App": "openhay",
        "X-OpenHay-Event": event,
        "X-OpenHay-User-Email": user_email,
        "X-OpenHay-Request-Id": request_id,
    }
    if ip_header_value:
        headers["X-OpenHay-User-IP-Hash"] = ip_header_value
    return headers


@router.post("/support")
async def submit_support(req: SupportRequest, request: Request) -> dict[str, str]:
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question is required")

    if not _smtp_configured():
        # Dev fallback: avoid 500s in environments without SMTP configured
        logger.warning(
            "SMTP not configured. Logging support request instead. email={}, len(question)={}",
            req.email,
            len(req.question or ""),
        )
        return {"status": "ok"}

    ctx = _compose_context(request)

    subject = "[OpenHay][Support] New request"
    event = "support_request"

    text, metadata_yaml = _build_text_and_yaml(
        event=event,
        user_email=req.email,
        include_client_ip=bool(ctx.get("client_ip")),
        include_ip_hash=False,
        message=req.question,
        ctx=ctx,
    )

    html = (
        "<h3>Yêu cầu hỗ trợ mới</h3>"
        f"<p><strong>Email người dùng:</strong> {req.email}</p>"
        "<p><strong>Nội dung:</strong></p>"
        f"<pre>{req.question}</pre>"
    )

    headers = _build_headers(
        event=event,
        user_email=req.email,
        request_id=ctx["request_id"],
        ip_header_value=(ctx.get("client_ip") or None),
    )

    try:
        _send_email(
            subject,
            html,
            text,
            extra_headers=headers,
            reply_to=req.email,
            attachments=[("metadata.yaml", metadata_yaml, "yaml")],
        )
    except RuntimeError as exc:
        # Surface clear error for frontend to display
        logger.exception("Failed to send support email via SMTP")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"status": "ok"}


class WaitlistRequest(BaseModel):
    email: EmailStr


@router.post("/waitlist")
async def join_waitlist(req: WaitlistRequest, request: Request) -> dict[str, str]:
    if not _smtp_configured():
        logger.warning(
            "SMTP not configured. Logging waitlist join. email={}",
            req.email,
        )
        return {"status": "ok"}

    ctx = _compose_context(request)

    subject = "[OpenHay][Waitlist] New signup"
    event = "waitlist_join"

    text, metadata_yaml = _build_text_and_yaml(
        event=event,
        user_email=req.email,
        include_client_ip=settings.collect_client_ip,
        include_ip_hash=bool(ctx.get("user_ip_hash")),
        message=None,
        ctx=ctx,
    )

    html = (
        f"<h3>Đăng ký danh sách chờ mới</h3><p><strong>Email người dùng:</strong> {req.email}</p>"
    )

    headers = _build_headers(
        event=event,
        user_email=req.email,
        request_id=ctx["request_id"],
        ip_header_value=(ctx.get("user_ip_hash") or None),
    )

    try:
        _send_email(
            subject,
            html,
            text,
            extra_headers=headers,
            reply_to=req.email,
            attachments=[("metadata.yaml", metadata_yaml, "yaml")],
        )
    except RuntimeError as exc:
        logger.exception("Failed to send waitlist email via SMTP")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"status": "ok"}


__all__ = ["router"]
