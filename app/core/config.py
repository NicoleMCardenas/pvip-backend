
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str
    app_env: str
    database_url: str

    jwt_secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int

    # Email notifications
    resend_api_key: str | None = None
    email_from: str | None = None
    survey_public_base_url: str | None = None
    email_sending_enabled: bool = False

    # Password recovery
    password_reset_token_expire_minutes: int = 30
    password_reset_request_cooldown_seconds: int = 60
    password_reset_public_base_url: str | None = None
    password_reset_email_enabled: bool = False

    # Staff invitations
    staff_invitation_token_expire_hours: int = 48
    staff_invitation_public_base_url: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )


settings = Settings()
