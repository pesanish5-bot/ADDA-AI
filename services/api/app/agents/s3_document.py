"""Short-lived, token-protected document evidence in a private S3 bucket.

Only extracted bounded text is stored, not the original uploaded PDF. S3 is
shared across Lambda instances; the browser's separate document token is never
stored in plaintext in the object.
"""
import json
import re
import secrets
import time
from hashlib import sha256

import boto3
from botocore.exceptions import ClientError

from app.agents.document import DocumentStore, _Document
from app.providers import ProviderError


class S3DocumentStore(DocumentStore):
    def __init__(self, bucket: str, client=None, ttl_seconds: int = 3600):
        super().__init__(ttl_seconds=ttl_seconds)
        self.bucket = bucket
        self.client = client or boto3.client('s3')

    @staticmethod
    def _key(document_id: str) -> str:
        if not re.fullmatch(r'[A-Za-z0-9_-]{20,40}', document_id):
            raise ProviderError('Document unavailable or expired. Upload it again.', 'document_not_found', 404)
        return f'documents/{document_id}.json'

    def ingest(self, data: bytes, filename: str) -> dict:
        result = super().ingest(data, filename)
        document_id = result['document_id']
        with self._lock:
            document = self._documents.pop(document_id)
        payload = {
            'token_hash': sha256(document.token.encode()).hexdigest(),
            'filename': document.filename,
            'pages': document.pages,
            'chunks': document.chunks,
            'expires_at': time.time() + self.ttl_seconds,
        }
        try:
            self.client.put_object(Bucket=self.bucket, Key=self._key(document_id),
                                   Body=json.dumps(payload, separators=(',', ':')).encode(),
                                   ContentType='application/json', ServerSideEncryption='AES256')
        except ClientError as exc:
            raise ProviderError('Document storage is temporarily unavailable. Try again.',
                                'document_storage', 503) from exc
        return result

    def _get(self, document_id: str, token: str) -> _Document:
        key = self._key(document_id)
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            payload = json.loads(response['Body'].read())
        except ClientError as exc:
            if exc.response.get('Error', {}).get('Code') in ('NoSuchKey', '404', 'NotFound'):
                raise ProviderError('Document unavailable or expired. Upload it again.',
                                    'document_not_found', 404) from exc
            raise ProviderError('Document storage is temporarily unavailable. Try again.',
                                'document_storage', 503) from exc
        valid = secrets.compare_digest(payload['token_hash'], sha256((token or '').encode()).hexdigest())
        if not valid or payload['expires_at'] <= time.time():
            raise ProviderError('Document unavailable or expired. Upload it again.', 'document_not_found', 404)
        return _Document('', payload['filename'], payload['pages'],
                         tuple((int(page), text) for page, text in payload['chunks']), 0)

    def delete(self, document_id: str, document_token: str) -> None:
        self._get(document_id, document_token)
        try:
            self.client.delete_object(Bucket=self.bucket, Key=self._key(document_id))
        except ClientError as exc:
            raise ProviderError('Document storage is temporarily unavailable. Try again.',
                                'document_storage', 503) from exc
