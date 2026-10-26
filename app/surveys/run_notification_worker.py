
import logging
import sys

from app.surveys.notification_processor import (
    ProcessingStatus,
    process_one_notification,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

logger = logging.getLogger("kairo.notification_worker")

MAX_NOTIFICATIONS_PER_RUN = 20


def main() -> int:
    """
    Process a limited batch of pending survey notifications.

    Email sending remains controlled by EMAIL_SENDING_ENABLED.
    This script does not run automatically or continuously.
    """
    processed = 0

    try:
        for _ in range(MAX_NOTIFICATIONS_PER_RUN):
            result = process_one_notification()

            if result.status == ProcessingStatus.DISABLED:
                logger.info("Email sending is disabled.")
                return 0

            if result.status == ProcessingStatus.EMPTY:
                logger.info(
                    "No more eligible notifications. Processed: %s",
                    processed,
                )
                return 0

            processed += 1

            logger.info(
                "Notification %s: %s",
                result.notification_id,
                result.status.value,
            )

        logger.info(
            "Batch limit reached. Processed: %s",
            processed,
        )
        return 0

    except Exception:
        logger.exception(
            "Notification processing stopped after %s items.",
            processed,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
