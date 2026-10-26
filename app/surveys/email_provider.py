
from dataclasses import dataclass
from enum import Enum
from html import escape
from urllib.parse import quote

import httpx


RESEND_API_URL = "https://api.resend.com/emails"
REQUEST_TIMEOUT_SECONDS = 15


class EmailDeliveryStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class EmailDeliveryResult:
    status: EmailDeliveryStatus
    provider_message_id: str | None = None
    error: str | None = None
    permanent: bool = False


def build_survey_url(base_url: str, public_token: str) -> str:
    """
    Build the customer-facing survey URL.
    """
    if not base_url or not base_url.strip():
        raise ValueError("Survey public base URL is required.")

    if not public_token or not public_token.strip():
        raise ValueError("Survey public token is required.")

    base = base_url.strip().rstrip("/")

    if not base.startswith(("https://", "http://")):
        raise ValueError("Survey base URL must use HTTP or HTTPS.")

    token = quote(public_token.strip(), safe="")

    return f"{base}/survey/{token}"


def build_survey_email_html(survey_url: str) -> str:
    """
    Build a simple HTML invitation to complete a survey.
    """
    safe_url = escape(survey_url, quote=True)

    return f"""
    <!DOCTYPE html>
    <html lang="es">
      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Tu opinión es importante</title>
      </head>
      <body style="font-family: Arial, sans-serif;
                   color: #172033;
                   background-color: #f5f7fb;
                   padding: 32px 16px;">
        <div style="max-width: 560px;
                    margin: 0 auto;
                    padding: 32px;
                    background-color: #ffffff;
                    border-radius: 12px;">
          <h1 style="font-size: 24px;">Tu opinión es importante</h1>
          <p>
            Gracias por tu visita. Nos gustaría conocer
            tu experiencia para seguir mejorando.
          </p>
          <p>
            Responder esta breve encuesta nos ayudará
            a ofrecerte un mejor servicio.
          </p>
          <p style="margin: 32px 0;">
            <a href="{safe_url}"
               style="background-color: #2563eb;
                      color: #ffffff;
                      padding: 14px 24px;
                      border-radius: 8px;
                      text-decoration: none;">
              Responder encuesta
            </a>
          </p>
          <p style="font-size: 13px; color: #64748b;">
            Si el botón no funciona, copia este enlace:
          </p>
          <p style="font-size: 13px; overflow-wrap: anywhere;">
            <a href="{safe_url}">{safe_url}</a>
          </p>
        </div>
      </body>
    </html>
    """


def send_survey_email(
    *,
    api_key: str,
    email_from: str,
    recipient_email: str,
    survey_url: str,
    idempotency_key: str,
    client: httpx.Client | None = None,
) -> EmailDeliveryResult:
    """
    Request email delivery from Resend.

    ACCEPTED: Provider returned a valid message ID.
    REJECTED: Provider explicitly rejected the request.
    UNCERTAIN: Provider may have accepted the request,
               but the outcome could not be confirmed.

    This function does not access the database.
    """
    if not api_key or not api_key.strip():
        raise ValueError("Resend API key is required.")

    if not email_from or not email_from.strip():
        raise ValueError("Sender email is required.")

    if not recipient_email or not recipient_email.strip():
        raise ValueError("Recipient email is required.")

    if not survey_url or not survey_url.strip():
        raise ValueError("Survey URL is required.")

    if not idempotency_key or not idempotency_key.strip():
        raise ValueError("Idempotency key is required.")

    payload = {
        "from": email_from.strip(),
        "to": [recipient_email.strip()],
        "subject": "Tu opinión es importante | KAIRO",
        "html": build_survey_email_html(survey_url),
    }

    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "Idempotency-Key": idempotency_key.strip(),
    }

    owns_client = client is None

    if owns_client:
        client = httpx.Client(
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

    try:
        try:
            response = client.post(
                RESEND_API_URL,
                json=payload,
                headers=headers,
            )
        except httpx.RequestError as exc:
            return EmailDeliveryResult(
                status=EmailDeliveryStatus.UNCERTAIN,
                error=f"Provider request outcome uncertain: {type(exc).__name__}",
            )

        if 200 <= response.status_code < 300:
            try:
                data = response.json()
            except ValueError:
                return EmailDeliveryResult(
                    status=EmailDeliveryStatus.UNCERTAIN,
                    error="Provider returned an invalid success response.",
                )

            message_id = data.get("id") if isinstance(data, dict) else None

            if not isinstance(message_id, str) or not message_id.strip():
                return EmailDeliveryResult(
                    status=EmailDeliveryStatus.UNCERTAIN,
                    error="Provider did not return a valid message ID.",
                )

            return EmailDeliveryResult(
                status=EmailDeliveryStatus.ACCEPTED,
                provider_message_id=message_id.strip(),
            )

        if response.status_code in {408, 409, 425, 429} or response.status_code >= 500:
            return EmailDeliveryResult(
                status=EmailDeliveryStatus.UNCERTAIN,
                error=f"Provider response requires reconciliation: HTTP {response.status_code}",
            )

        return EmailDeliveryResult(
            status=EmailDeliveryStatus.REJECTED,
            error=f"Provider rejected request: HTTP {response.status_code}",
            permanent=response.status_code in {400, 401, 403, 404, 422},
        )

    finally:
        if owns_client:
            client.close()
