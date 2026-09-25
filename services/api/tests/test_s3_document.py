from io import BytesIO

import pytest
from botocore.exceptions import ClientError

from app.agents.s3_document import S3DocumentStore
from app.providers import ProviderError


class FakeS3:
    def __init__(self):
        self.objects = {}

    def put_object(self, **kwargs):
        assert kwargs['ServerSideEncryption'] == 'AES256'
        self.objects[(kwargs['Bucket'], kwargs['Key'])] = kwargs['Body']

    def get_object(self, **kwargs):
        key = (kwargs['Bucket'], kwargs['Key'])
        if key not in self.objects:
            raise ClientError({'Error': {'Code': 'NoSuchKey', 'Message': 'missing'}}, 'GetObject')
        return {'Body': BytesIO(self.objects[key])}

    def delete_object(self, **kwargs):
        del self.objects[(kwargs['Bucket'], kwargs['Key'])]


def test_document_survives_new_instance_and_requires_its_own_token():
    s3 = FakeS3()
    upload = S3DocumentStore('private-test', s3).ingest(b'The approved budget is INR 180,000.', 'budget.txt')
    stored = next(iter(s3.objects.values()))
    assert upload['document_token'].encode() not in stored
    other_instance = S3DocumentStore('private-test', s3)
    answer = other_instance.answer(upload['document_id'], upload['document_token'], 'approved budget')
    assert 'INR 180,000' in answer['citations'][0]['excerpt']
    for bad_token in ('', 'wrong'):
        with pytest.raises(ProviderError) as denied:
            other_instance.answer(upload['document_id'], bad_token, 'budget')
        assert denied.value.status == 404
    other_instance.delete(upload['document_id'], upload['document_token'])
    with pytest.raises(ProviderError) as missing:
        other_instance.answer(upload['document_id'], upload['document_token'], 'budget')
    assert missing.value.status == 404


def test_expired_document_is_not_returned(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr('app.agents.s3_document.time.time', lambda: clock[0])
    s3 = FakeS3()
    upload = S3DocumentStore('private-test', s3, ttl_seconds=10).ingest(b'Green energy report.', 'report.txt')
    clock[0] = 111.0
    with pytest.raises(ProviderError) as expired:
        S3DocumentStore('private-test', s3).answer(upload['document_id'], upload['document_token'], 'energy')
    assert expired.value.status == 404


def test_s3_document_is_scoped_to_authenticated_owner():
    s3 = FakeS3()
    upload = S3DocumentStore('private-test', s3).ingest(
        b'Private account evidence.', 'evidence.txt', owner_id='user-a'
    )
    other_instance = S3DocumentStore('private-test', s3)
    assert other_instance.answer(
        upload['document_id'], upload['document_token'], 'account', owner_id='user-a'
    )['source_count'] == 1
    with pytest.raises(ProviderError) as denied:
        other_instance.answer(
            upload['document_id'], upload['document_token'], 'account', owner_id='user-b'
        )
    assert denied.value.status == 404
