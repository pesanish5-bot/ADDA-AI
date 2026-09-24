"""Build a Lambda deployment zip for services/api without Docker or SAM.

Installs the pinned runtime requirements as Linux x86_64 / CPython 3.13 wheels into a
staging directory, copies the application package, and writes a zip with POSIX paths.

Usage:
    python scripts/build_lambda_package.py [--out build/lambda/api.zip]

The output is suitable for `aws lambda update-function-code --zip-file fileb://...` or as
the S3 artifact referenced by the SAM template's CodeUri after `aws cloudformation package`.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / 'services' / 'api'
PY_TAG = '3.13'
PLATFORM = 'manylinux2014_x86_64'
EXCLUDE_DIRS = {'__pycache__', 'tests', '.pytest_cache'}


def install_dependencies(target: Path) -> None:
    cmd = [
        sys.executable, '-m', 'pip', 'install', '--quiet', '--no-compile',
        '--platform', PLATFORM, '--python-version', PY_TAG, '--implementation', 'cp',
        '--only-binary=:all:', '--target', str(target),
        '-r', str(API / 'requirements.txt'),
    ]
    subprocess.run(cmd, check=True)
    # Lambda ships boto3/botocore; keeping the pinned copy avoids version drift, but the
    # awscrt wheel is large and unused by the app. Drop it to stay well under size limits.
    for name in ('awscrt', 'awscrt.libs'):
        shutil.rmtree(target / name, ignore_errors=True)
    for dist in target.glob('awscrt-*.dist-info'):
        shutil.rmtree(dist, ignore_errors=True)


def copy_app(target: Path) -> None:
    shutil.copytree(
        API / 'app', target / 'app',
        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'),
    )


def write_zip(staging: Path, out: Path) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(staging.rglob('*')):
            if path.is_dir() or any(part in EXCLUDE_DIRS for part in path.relative_to(staging).parts):
                continue
            info = zipfile.ZipInfo(path.relative_to(staging).as_posix(), date_time=(2020, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, path.read_bytes())
    return out.stat().st_size


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default=str(ROOT / 'build' / 'lambda' / 'api.zip'))
    args = parser.parse_args()

    staging = ROOT / 'build' / 'lambda' / 'staging'
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    install_dependencies(staging)
    copy_app(staging)
    size = write_zip(staging, Path(args.out))
    print(f'wrote {args.out} ({size / 1_048_576:.1f} MiB)')


if __name__ == '__main__':
    main()
