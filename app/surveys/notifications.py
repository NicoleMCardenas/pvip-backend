
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.survey import Survey
from app.models.survey_notification import SurveyNotification


def create_pending_survey_notification(
    survey: Survey,
    client: Client,
    db: Session,
) -> SurveyNotification | None:
    """
    Register a pending email notification for a survey.

    This function does not send emails or commit transactions.
    """

    if not client.email:
        return None

    if client.status == "archived":
        return None

    if survey.status != "pending":
        return None

    notification = SurveyNotification(
        survey_id=survey.id,
        recipient_email=client.email,
        status="pending",
        attempts=0,
    )

    db.add(notification)
    db.flush()

    return notification
