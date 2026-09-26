import pytest
from botocore.exceptions import ClientError, NoCredentialsError

from app.check_bedrock import check
from app.config import Settings
from app.providers import Generation, aws_error


class LocalSession:
    def __init__(self, credentials=True):
        self.credentials = credentials

    def get_credentials(self):
        return object() if self.credentials else None

    def client(self, service, **kwargs):
        assert service == 'sts'
        return self

    def get_caller_identity(self):
        return {'Account': 'private-account', 'Arn': 'private-arn'}


def test_missing_credentials_stops_before_network():
    report = check(Settings(_env_file=None), session=LocalSession(False))
    assert report['ready'] is False
    assert report['checks'][0]['ok'] is False


def test_configured_model_is_not_verified_without_inference(monkeypatch):
    def forbidden(*args):
        raise AssertionError('Must not invoke model without --invoke')
    monkeypatch.setattr('app.check_bedrock.CodingProvider.generate', forbidden)
    report = check(Settings(_env_file=None, bedrock_model_id='test-model'), session=LocalSession())
    assert report['ready'] is False
    assert report['checks'][-1]['ok'] is None
    assert 'private-account' not in str(report)
    assert 'private-arn' not in str(report)


def test_live_check_uses_two_distinct_prompts(monkeypatch):
    prompts = []
    def answer(self, prompt, **kwargs):
        prompts.append(prompt)
        assert self.settings.nexus_provider == 'bedrock'
        return Generation('sample SDK answer', 'bedrock', 'test-model', 10, 20, 5, 'end_turn', False, 1)
    monkeypatch.setattr('app.check_bedrock.CodingProvider.generate', answer)
    report = check(Settings(_env_file=None, bedrock_model_id='test-model'), invoke=True, session=LocalSession())
    assert report['ready'] is True
    assert len(set(prompts)) == 2


@pytest.mark.parametrize('code,expected', [
    ('AccessDeniedException', 'aws_access_denied'),
    ('ExpiredToken', 'aws_session_invalid'),
    ('ThrottlingException', 'provider_rate_limited'),
    ('ValidationException', 'model_configuration_error'),
])
def test_error_messages_are_safe_and_specific(code, expected):
    error = aws_error(ClientError({'Error': {'Code': code, 'Message': 'secret detail'}}, 'Converse'))
    assert error.code == expected
    assert 'secret detail' not in error.message


def test_credentials_error_has_action():
    assert aws_error(NoCredentialsError()).code == 'aws_credentials_missing'
