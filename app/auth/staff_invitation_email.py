
from html import escape
from typing import Literal
from urllib.parse import quote

import httpx

from app.surveys.email_provider import (
    EmailDeliveryResult,
    EmailDeliveryStatus,
    REQUEST_TIMEOUT_SECONDS,
    RESEND_API_URL,
)


def build_staff_invitation_url(
    base_url: str,
    token: str,
    language: Literal["es", "en"] = "es",
) -> str:
    if not base_url or not base_url.strip():
        raise ValueError("Staff invitation base URL is required.")

    if not token or not token.strip():
        raise ValueError("Staff invitation token is required.")

    if language not in ("es", "en"):
        raise ValueError("Unsupported staff invitation language.")

    base = base_url.strip().rstrip("/")

    if not base.startswith(("https://", "http://")):
        raise ValueError("Staff invitation URL must use HTTP or HTTPS.")

    return (
        f"{base}/accept-invitation"
        f"?token={quote(token, safe='')}"
        f"&lang={language}"
    )


def build_staff_invitation_email_html(
    invitation_url: str,
    language: Literal["es", "en"] = "es",
) -> str:
    if language not in ("es", "en"):
        raise ValueError("Unsupported staff invitation language.")

    safe_url = escape(invitation_url, quote=True)

    content = {
        "es": {
            "title": "Te invitaron a KAIRO",
            "eyebrow": "INVITACIÓN A TU EQUIPO",
            "intro": (
                "Has recibido una invitación para acceder "
                "a KAIRO como profesional de un negocio."
            ),
            "instruction": (
                "Para activar tu cuenta, establece tu "
                "contraseña mediante el siguiente botón."
            ),
            "button": "Activar mi cuenta",
            "expiry": "Este enlace caduca en 48 horas.",
            "ignore": (
                "Si no esperabas esta invitación, "
                "puedes ignorar este correo."
            ),
            "fallback": (
                "Si el botón no funciona, copia "
                "este enlace en tu navegador:"
            ),
        },
        "en": {
            "title": "You've been invited to KAIRO",
            "eyebrow": "TEAM INVITATION",
            "intro": (
                "You've received an invitation to access "
                "KAIRO as a business team member."
            ),
            "instruction": (
                "To activate your account, set your "
                "password using the button below."
            ),
            "button": "Activate my account",
            "expiry": "This link expires in 48 hours.",
            "ignore": (
                "If you weren't expecting this invitation, "
                "you can ignore this email."
            ),
            "fallback": (
                "If the button doesn't work, copy "
                "this link into your browser:"
            ),
        },
    }[language]

    return f"""<!DOCTYPE html>
<html lang="{language}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(content['title'])} | KAIRO</title>
</head>
<body style="margin:0;padding:40px 16px;background-color:#020617;color:#ffffff;font-family:Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:auto;background-color:#0f172a;border:1px solid #334155;border-radius:14px;">
    <tr>
      <td style="padding:30px 32px;background-color:#020617;">
        <div style="font-size:27px;font-weight:800;letter-spacing:1px;">KAIRO</div>
        <p style="font-size:11px;letter-spacing:1.4px;color:#94a3b8;">CUSTOMER INTELLIGENCE</p>
        <div style="width:48px;height:3px;background-color:#38bdf8;"></div>
      </td>
    </tr>
    <tr>
      <td style="padding:36px 32px;">
        <p style="font-size:11px;font-weight:700;letter-spacing:1.3px;color:#38bdf8;">{content['eyebrow']}</p>
        <h1 style="font-size:26px;line-height:1.3;color:#ffffff;">{content['title']}</h1>
        <p style="font-size:15px;line-height:1.7;color:#cbd5e1;">{content['intro']}</p>
        <p style="font-size:15px;line-height:1.7;color:#cbd5e1;">{content['instruction']}</p>
        <p style="margin:28px 0;">
          <a href="{safe_url}" style="display:block;padding:16px 20px;background-color:#38bdf8;border-radius:8px;text-align:center;color:#020617;text-decoration:none;font-size:15px;font-weight:700;">{content['button']}</a>
        </p>
        <p style="padding:16px;background-color:#1e293b;border-radius:8px;font-size:13px;color:#cbd5e1;">{content['expiry']}</p>
        <p style="margin-top:28px;font-size:13px;line-height:1.7;color:#94a3b8;">{content['ignore']}</p>
        <p style="font-size:12px;color:#94a3b8;">{content['fallback']}</p>
        <p style="font-size:12px;overflow-wrap:anywhere;word-break:break-all;">
          <a href="{safe_url}" style="color:#7dd3fc;">{safe_url}</a>
        </p>
      </td>
    </tr>
    <tr>
      <td style="padding:24px;text-align:center;background-color:#020617;">
        <p style="font-size:12px;color:#cbd5e1;">KAIRO · Customer Intelligence</p>
      </td>
    </tr>
  </table>
</body>
</html>"""


def send_staff_invitation_email(
    *,
    api_key: str,
    email_from: str,
    recipient_email: str,
    invitation_url: str,
    idempotency_key: str,
    language: Literal["es", "en"] = "es",
    client: httpx.Client | None = None,
) -> EmailDeliveryResult:
    if language not in ("es", "en"):
        raise ValueError("Unsupported staff invitation language.")

    if not all(
        value and value.strip()
        for value in (
            api_key,
            email_from,
            recipient_email,
            invitation_url,
            idempotency_key,
        )
    ):
        raise ValueError("Missing staff invitation email configuration.")

    payload = {
        "from": email_from.strip(),
        "to": [recipient_email.strip()],
        "subject": (
            "Activa tu cuenta | KAIRO"
            if language == "es"
            else "Activate your account | KAIRO"
        ),
        "html": build_staff_invitation_email_html(
            invitation_url,
            language,
        ),
    }

    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "Idempotency-Key": idempotency_key.strip(),
    }

    owns_client = client is None

    if owns_client:
        client = httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS)

    try:
        try:
            response = client.post(
                RESEND_API_URL,
                json=payload,
                headers=headers,
            )
        except httpx.RequestError:
            return EmailDeliveryResult(
                status=EmailDeliveryStatus.UNCERTAIN,
                error="Staff invitation email delivery outcome uncertain.",
            )

        if 200 <= response.status_code < 300:
            try:
                data = response.json()
            except ValueError:
                data = None

            message_id = (
                data.get("id")
                if isinstance(data, dict)
                else None
            )

            if not isinstance(message_id, str) or not message_id.strip():
                return EmailDeliveryResult(
                    status=EmailDeliveryStatus.UNCERTAIN,
                    error="Provider returned no valid message ID.",
                )

            return EmailDeliveryResult(
                status=EmailDeliveryStatus.ACCEPTED,
                provider_message_id=message_id.strip(),
            )

        if (
            response.status_code in {408, 409, 425, 429}
            or response.status_code >= 500
        ):
            return EmailDeliveryResult(
                status=EmailDeliveryStatus.UNCERTAIN,
                error=f"Provider response: HTTP {response.status_code}",
            )

        return EmailDeliveryResult(
            status=EmailDeliveryStatus.REJECTED,
            error=f"Provider rejected request: HTTP {response.status_code}",
            permanent=response.status_code in {400, 401, 403, 404, 422},
        )

    finally:
        if owns_client:
            client.close()
