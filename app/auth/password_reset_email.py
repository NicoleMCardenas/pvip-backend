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


def build_password_reset_url(
    base_url: str,
    token: str,
    language: Literal["es", "en"] = "es",
) -> str:
    if not base_url or not base_url.strip():
        raise ValueError("Password reset base URL is required.")
    if not token or not token.strip():
        raise ValueError("Password reset token is required.")
    if language not in ("es", "en"):
        raise ValueError("Unsupported password reset language.")

    base = base_url.strip().rstrip("/")
    if not base.startswith(("https://", "http://")):
        raise ValueError("Password reset URL must use HTTP or HTTPS.")

    return (
        f"{base}/reset-password"
        f"?token={quote(token, safe='')}"
        f"&lang={language}"
    )


def build_password_reset_email_html(
    reset_url: str,
    language: Literal["es", "en"] = "es",
) -> str:
    if language not in ("es", "en"):
        raise ValueError("Unsupported password reset language.")

    safe_url = escape(reset_url, quote=True)
    content = {
        "es": {
            "title": "Restablece tu contraseña",
            "eyebrow": "RECUPERACIÓN DE ACCESO",
            "greeting": "Hola,",
            "intro": "Recibimos una solicitud para restablecer la contraseña de tu cuenta de KAIRO.",
            "instruction": "Para continuar de forma segura, utiliza el siguiente botón.",
            "button": "Restablecer contraseña",
            "expiry": "Este enlace caduca en <strong>30 minutos</strong>.",
            "ignore": "¿No solicitaste este cambio? Puedes ignorar este correo. Tu contraseña permanecerá sin modificaciones.",
            "fallback": "Si el botón no funciona, copia y pega este enlace en tu navegador:",
            "footer": "Comunicación automática de seguridad",
        },
        "en": {
            "title": "Reset your password",
            "eyebrow": "ACCOUNT RECOVERY",
            "greeting": "Hello,",
            "intro": "We received a request to reset the password for your KAIRO account.",
            "instruction": "To continue securely, use the button below.",
            "button": "Reset password",
            "expiry": "This link expires in <strong>30 minutes</strong>.",
            "ignore": "Didn't request this change? You can ignore this email. Your password will remain unchanged.",
            "fallback": "If the button doesn't work, copy and paste this link into your browser:",
            "footer": "Automated security notification",
        },
    }[language]

    return f"""<!DOCTYPE html>
<html lang="{language}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark">
  <meta name="supported-color-schemes" content="dark">
  <title>{content['title']} | KAIRO</title>
</head>
<body style="margin:0;padding:0;background-color:#020617;color:#ffffff;font-family:Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" bgcolor="#020617" style="background-color:#020617;">
    <tr><td align="center" style="padding:40px 16px;">
      <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" bgcolor="#0f172a" style="max-width:560px;background-color:#0f172a;border:1px solid #334155;border-radius:14px;">
        <tr><td bgcolor="#020617" style="padding:30px 32px 26px;background-color:#020617;">
          <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0">
            <tr>
              <td valign="middle" style="font-size:27px;font-weight:800;letter-spacing:1px;color:#ffffff;">KAIRO</td>
              <td align="right" valign="middle">
                <span style="display:inline-block;padding:7px 11px;border-radius:20px;background-color:#1e293b;color:#7dd3fc;font-size:10px;font-weight:700;letter-spacing:0.7px;">ACCOUNT SECURITY</span>
              </td>
            </tr>
          </table>
          <p style="margin:8px 0 18px;font-size:11px;letter-spacing:1.4px;color:#94a3b8;">CUSTOMER INTELLIGENCE</p>
          <div style="width:48px;height:3px;background-color:#38bdf8;border-radius:3px;"></div>
        </td></tr>
        <tr><td bgcolor="#0f172a" style="padding:36px 32px 34px;background-color:#0f172a;">
          <p style="margin:0 0 12px;color:#38bdf8;font-size:11px;font-weight:700;letter-spacing:1.3px;">{content['eyebrow']}</p>
          <h1 style="margin:0 0 26px;font-size:26px;line-height:1.3;font-weight:700;color:#ffffff;">{content['title']}</h1>
          <p style="margin:0 0 16px;font-size:15px;line-height:1.7;color:#cbd5e1;">{content['greeting']}</p>
          <p style="margin:0 0 16px;font-size:15px;line-height:1.7;color:#cbd5e1;">{content['intro']}</p>
          <p style="margin:0 0 28px;font-size:15px;line-height:1.7;color:#cbd5e1;">{content['instruction']}</p>
          <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0">
            <tr><td align="center" bgcolor="#38bdf8" style="background-color:#38bdf8;border-radius:8px;">
              <a href="{safe_url}" style="display:block;padding:16px 20px;font-size:15px;line-height:1.4;font-weight:700;text-align:center;text-decoration:none;color:#020617;">{content['button']} &rarr;</a>
            </td></tr>
          </table>
          <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-top:24px;">
            <tr><td bgcolor="#1e293b" style="padding:16px;background-color:#1e293b;border-radius:8px;font-size:13px;line-height:1.6;color:#cbd5e1;">{content['expiry']}</td></tr>
          </table>
          <div style="height:1px;background-color:#334155;margin:28px 0 22px;"></div>
          <p style="margin:0 0 18px;font-size:13px;line-height:1.8;color:#94a3b8;">{content['ignore']}</p>
          <p style="margin:0 0 10px;font-size:12px;line-height:1.6;color:#94a3b8;">{content['fallback']}</p>
          <p style="margin:0;font-size:12px;line-height:1.7;overflow-wrap:anywhere;word-break:break-all;">
            <a href="{safe_url}" style="color:#7dd3fc;text-decoration:underline;">{safe_url}</a>
          </p>
        </td></tr>
        <tr><td align="center" bgcolor="#020617" style="padding:24px 20px;background-color:#020617;">
          <p style="margin:0 0 6px;color:#cbd5e1;font-size:12px;font-weight:700;">KAIRO · Customer Intelligence</p>
          <p style="margin:0;color:#64748b;font-size:11px;">{content['footer']}</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def send_password_reset_email(
    *,
    api_key: str,
    email_from: str,
    recipient_email: str,
    reset_url: str,
    idempotency_key: str,
    client: httpx.Client | None = None,
    language: Literal["es", "en"] = "es",
) -> EmailDeliveryResult:
    if not all(
        value and value.strip()
        for value in (
            api_key,
            email_from,
            recipient_email,
            reset_url,
            idempotency_key,
        )
    ):
        raise ValueError("Missing password reset email configuration.")

    payload = {
        "from": email_from.strip(),
        "to": [recipient_email.strip()],
        "subject": (
            "Restablece tu contraseña | KAIRO"
            if language == "es"
            else "Reset your password | KAIRO"
        ),
        "html": build_password_reset_email_html(reset_url, language),
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
                error="Password reset email delivery outcome uncertain.",
            )

        if 200 <= response.status_code < 300:
            try:
                data = response.json()
            except ValueError:
                data = None

            message_id = (
                data.get("id") if isinstance(data, dict) else None
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