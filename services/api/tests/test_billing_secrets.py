import pytest

from app.billing import BillingError
from app.billing_secrets import AwsBillingSecretProvider
from app.config import ConfigurationError, Settings


class FakeSecretsManager:
    def __init__(self, value: str) -> None:
        self.value = value
        self.calls = 0

    def get_secret_value(self, *, SecretId: str) -> dict:
        assert SecretId == 'arn:aws:secretsmanager:ap-south-1:123:secret:billing'
        self.calls += 1
        return {'SecretString': self.value}


def test_aws_billing_secrets_are_validated_and_cached():
    client = FakeSecretsManager(
        '{"secret_key":"sk_test_safe","webhook_secret":"whsec_safe"}'
    )
    provider = AwsBillingSecretProvider(
        'arn:aws:secretsmanager:ap-south-1:123:secret:billing',
        'ap-south-1', client=client,
    )
    assert provider.get().secret_key == 'sk_test_safe'
    assert provider.get().webhook_secret == 'whsec_safe'
    assert client.calls == 1


@pytest.mark.parametrize('value', [
    '{}', 'not-json', '{"secret_key":"public","webhook_secret":"whsec_safe"}',
])
def test_invalid_secret_payload_fails_closed(value: str):
    provider = AwsBillingSecretProvider(
        'arn:aws:secretsmanager:ap-south-1:123:secret:billing',
        'ap-south-1', client=FakeSecretsManager(value),
    )
    with pytest.raises(BillingError, match='unavailable'):
        provider.get()


def test_staging_rejects_inline_stripe_credentials():
    settings = Settings(
        _env_file=None, app_env='staging', nexus_provider='bedrock',
        bedrock_model_id='model', allowed_origins='https://app.example.com',
        auth_required=True, cognito_user_pool_id='pool', cognito_client_id='client',
        auth_profiles_table='table', stripe_secret_key='sk_test_safe',
        stripe_webhook_secret='whsec_safe', stripe_pro_price_id='price_safe',
    )
    with pytest.raises(ConfigurationError, match='development-only'):
        settings.validate_for_environment()
