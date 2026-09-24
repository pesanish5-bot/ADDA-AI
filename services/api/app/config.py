from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal['development', 'staging', 'production']


class ConfigurationError(RuntimeError):
    """Raised at startup when settings are unsafe for the declared environment."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / '.env', extra='ignore'
    )
    app_env: AppEnv = 'development'
    app_version: str = '0.2.0'
    log_level: str = 'INFO'

    nexus_provider: Literal['demo', 'bedrock'] = 'demo'
    # The demo fixture is a connection test, never an AI answer. Production refuses it
    # unless this flag is set on purpose (for example a smoke-test stage).
    allow_demo_fixture: bool = False
    aws_region: str = 'ap-south-1'
    bedrock_model_id: str = ''

    allowed_origins: str = 'http://localhost:3000,http://127.0.0.1:3000'
    demo_access_token: str = ''
    tavily_api_key: str = ''
    document_enabled: bool = True
    document_bucket: str = ''

    # Amazon Cognito
    cognito_user_pool_id: str = ''
    cognito_client_id: str = ''
    cognito_region: str = ''
    auth_profiles_table: str = ''
    auth_dev_jwt_secret: str = ''
    admin_emails: str = ''
    auth_required: bool = True

    # Per-client, per-process limits. Edge throttling (API Gateway / WAF) remains the
    # authoritative control; this stops one client from exhausting one instance.
    rate_limit_chat_per_minute: int = 20
    rate_limit_upload_per_minute: int = 10
    rate_limit_default_per_minute: int = 60
    # Only trust X-Forwarded-For when a proxy you control sets it (ALB, nginx).
    # API Gateway + Mangum already supply the real source IP in the ASGI scope.
    trust_proxy_headers: bool = False

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(',') if origin.strip()]

    @property
    def search_enabled(self) -> bool:
        return bool(self.tavily_api_key.strip())

    @property
    def cognito_pool_region(self) -> str:
        return (self.cognito_region or self.aws_region or 'ap-south-1').strip()

    @property
    def cognito_configured(self) -> bool:
        return bool(self.cognito_user_pool_id.strip() and self.cognito_client_id.strip())

    @property
    def auth_configured(self) -> bool:
        return self.cognito_configured or bool(self.auth_dev_jwt_secret.strip())

    @property
    def api_requires_auth(self) -> bool:
        return bool(self.auth_required) and self.auth_configured

    @property
    def admin_email_set(self) -> set[str]:
        return {email.strip().lower() for email in self.admin_emails.split(',') if email.strip()}

    @property
    def is_production(self) -> bool:
        return self.app_env == 'production'

    def validate_for_environment(self) -> list[str]:
        """Return non-fatal warnings; raise ConfigurationError for unsafe production settings."""
        warnings: list[str] = []
        problems: list[str] = []
        if self.nexus_provider == 'demo' and not self.allow_demo_fixture:
            message = 'NEXUS_PROVIDER=demo returns a fixed fixture instead of AI output.'
            (problems if self.is_production else warnings).append(
                message + (' Set ALLOW_DEMO_FIXTURE=true to run a deliberate smoke stage.' if self.is_production else '')
            )
        if self.nexus_provider == 'bedrock' and not self.bedrock_model_id.strip():
            problems.append('NEXUS_PROVIDER=bedrock requires BEDROCK_MODEL_ID.')
        if self.app_env != 'development':
            insecure = [o for o in self.origins if not o.startswith('https://')]
            if insecure:
                problems.append(f'ALLOWED_ORIGINS must be https in {self.app_env}: {", ".join(insecure)}')
            if not self.origins:
                problems.append('ALLOWED_ORIGINS is empty.')
            if self.document_enabled and not self.document_bucket.strip():
                warnings.append('Documents use process memory without DOCUMENT_BUCKET; uploads are lost on restart and not shared across instances.')
        if problems:
            raise ConfigurationError(' '.join(problems))
        return warnings
