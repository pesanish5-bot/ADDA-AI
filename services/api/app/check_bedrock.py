"""Local AWS readiness check. No model invocation unless --invoke is supplied."""
import argparse
import json
import os

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.config import Settings
from app.providers import CodingProvider, ProviderError, aws_error


def check(settings: Settings, *, invoke: bool = False, session=None) -> dict:
    report = {'region': settings.aws_region, 'checks': [], 'ready': False}
    checks = report['checks']
    try:
        session = session or boto3.Session(region_name=settings.aws_region)
        if session.get_credentials() is None:
            checks.append({'step': 'AWS sign-in', 'ok': False,
                           'message': 'No local AWS credentials found. Complete AWS sign-in first.'})
            return report
        session.client('sts', config=Config(connect_timeout=3, read_timeout=5,
                       retries={'total_max_attempts': 1})).get_caller_identity()
        # Caller identity is deliberately not included in the report.
        checks.append({'step': 'AWS sign-in', 'ok': True, 'message': 'AWS accepted the local session.'})
        if not settings.bedrock_model_id.strip():
            checks.append({'step': 'Model configuration', 'ok': False,
                           'message': 'Choose a Converse model or inference profile and set BEDROCK_MODEL_ID.'})
            return report
        checks.append({'step': 'Model configuration', 'ok': True,
                       'message': 'Model ID configured; access is not yet verified.'})
        if not invoke:
            checks.append({'step': 'Live inference', 'ok': None,
                           'message': 'Not run. Use --invoke to send two small Coding requests.'})
            return report
        provider = CodingProvider(settings.model_copy(update={'nexus_provider': 'bedrock'}))
        for prompt in ('Write a Python function to reverse a string. Keep the answer short.',
                       'Write a JavaScript function to add two numbers. Keep the answer short.'):
            generation = provider.generate(prompt, max_tokens=300)
            checks.append({'step': 'Live inference', 'ok': True, 'prompt': prompt,
                           'answer': generation.text, 'usage': generation.usage()})
        report['ready'] = True
        return report
    except (BotoCoreError, ClientError, ProviderError) as exc:
        safe = exc if isinstance(exc, ProviderError) else aws_error(exc)
        checks.append({'step': 'AWS verification', 'ok': False, 'code': safe.code, 'message': safe.message})
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--invoke', action='store_true', help='Make two billable model requests to verify Coding.')
    parser.add_argument('--profile', help='Existing AWS profile to use for this process only.')
    parser.add_argument('--region', help='AWS region override for this check only.')
    parser.add_argument('--model', help='Model or inference profile override for this check only.')
    args = parser.parse_args()
    # This is a local developer check, not an EC2 workload.
    os.environ.setdefault('AWS_EC2_METADATA_DISABLED', 'true')
    if args.profile:
        os.environ['AWS_PROFILE'] = args.profile
    settings = Settings()
    if args.region:
        settings.aws_region = args.region
    if args.model:
        settings.bedrock_model_id = args.model
    report = check(settings, invoke=args.invoke)
    print(json.dumps(report, indent=2))
    failed = any(item['ok'] is False for item in report['checks'])
    raise SystemExit(2 if failed else 0)


if __name__ == '__main__':
    main()
