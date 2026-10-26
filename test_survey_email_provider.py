
import httpx

from app.surveys.email_provider import (
    EmailDeliveryStatus,
    build_survey_email_html,
    build_survey_url,
    send_survey_email,
)


API_KEY = "test-api-key"
EMAIL_FROM = "KAIRO <test@example.com>"
RECIPIENT = "customer@example.com"
SURVEY_URL = "https://kairo.example.com/survey/test-token"
IDEMPOTENCY_KEY = "survey-notification-test-123"


def send_with_mock(handler):
    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        return send_survey_email(
            api_key=API_KEY,
            email_from=EMAIL_FROM,
            recipient_email=RECIPIENT,
            survey_url=SURVEY_URL,
            idempotency_key=IDEMPOTENCY_KEY,
            client=client,
        )


def test_survey_url():
    url = build_survey_url(
        "https://kairo.example.com/",
        "abc-123",
    )

    assert url == "https://kairo.example.com/survey/abc-123"
    print("PASS: Survey URL generated correctly")


def test_survey_url_encodes_token():
    url = build_survey_url(
        "https://kairo.example.com",
        "token with spaces",
    )

    assert url.endswith("/survey/token%20with%20spaces")
    print("PASS: Survey token URL encoded")


def test_invalid_survey_url():
    try:
        build_survey_url("kairo.example.com", "abc")
    except ValueError:
        print("PASS: Invalid survey base URL rejected")
    else:
        raise AssertionError("Invalid base URL must be rejected")


def test_html_escaping():
    html = build_survey_email_html(
        'https://example.com/?value="unsafe"&other=1'
    )

    assert "&quot;" in html
    assert "&amp;" in html
    assert 'href="https://example.com/?value=&quot;unsafe&quot;&amp;other=1"' in html

    print("PASS: Email HTML escapes URL content")


def test_successful_delivery():
    def handler(request):
        assert request.method == "POST"
        assert str(request.url) == "https://api.resend.com/emails"
        assert request.headers["Idempotency-Key"] == IDEMPOTENCY_KEY
        assert request.headers["Authorization"] == f"Bearer {API_KEY}"

        payload = __import__("json").loads(request.content)

        assert payload["to"] == [RECIPIENT]
        assert payload["from"] == EMAIL_FROM
        assert SURVEY_URL in payload["html"]

        return httpx.Response(
            200,
            json={"id": "email_123"},
        )

    result = send_with_mock(handler)

    assert result.status == EmailDeliveryStatus.ACCEPTED
    assert result.provider_message_id == "email_123"
    assert result.error is None

    print("PASS: Successful provider acceptance")


def test_missing_provider_message_id():
    result = send_with_mock(
        lambda request: httpx.Response(200, json={})
    )

    assert result.status == EmailDeliveryStatus.UNCERTAIN
    assert result.provider_message_id is None

    print("PASS: Missing provider message ID classified as uncertain")


def test_invalid_success_response():
    result = send_with_mock(
        lambda request: httpx.Response(
            200,
            text="not-json",
        )
    )

    assert result.status == EmailDeliveryStatus.UNCERTAIN

    print("PASS: Invalid success response classified as uncertain")


def test_permanent_rejection():
    result = send_with_mock(
        lambda request: httpx.Response(
            422,
            json={"message": "Invalid recipient"},
        )
    )

    assert result.status == EmailDeliveryStatus.REJECTED
    assert result.permanent is True

    print("PASS: Permanent provider rejection")


def test_rate_limit():
    result = send_with_mock(
        lambda request: httpx.Response(429)
    )

    assert result.status == EmailDeliveryStatus.UNCERTAIN

    print("PASS: Rate limit classified as uncertain")


def test_server_error():
    result = send_with_mock(
        lambda request: httpx.Response(503)
    )

    assert result.status == EmailDeliveryStatus.UNCERTAIN

    print("PASS: Server error classified as uncertain")


def test_timeout():
    def handler(request):
        raise httpx.ReadTimeout("Simulated timeout", request=request)

    result = send_with_mock(handler)

    assert result.status == EmailDeliveryStatus.UNCERTAIN

    print("PASS: Network timeout classified as uncertain")


def test_missing_api_key():
    def handler(request):
        raise AssertionError("HTTP request must not be sent")

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        try:
            send_survey_email(
                api_key="",
                email_from=EMAIL_FROM,
                recipient_email=RECIPIENT,
                survey_url=SURVEY_URL,
                idempotency_key=IDEMPOTENCY_KEY,
                client=client,
            )
        except ValueError:
            print("PASS: Missing API key rejected before HTTP request")
        else:
            raise AssertionError("Missing API key must be rejected")


def run_tests():
    tests = [
        test_survey_url,
        test_survey_url_encodes_token,
        test_invalid_survey_url,
        test_html_escaping,
        test_successful_delivery,
        test_missing_provider_message_id,
        test_invalid_success_response,
        test_permanent_rejection,
        test_rate_limit,
        test_server_error,
        test_timeout,
        test_missing_api_key,
    ]

    for test in tests:
        test()

    print()
    print(f"ALL {len(tests)} SURVEY EMAIL PROVIDER TESTS PASSED")
    print("No real emails were sent.")


if __name__ == "__main__":
    run_tests()
