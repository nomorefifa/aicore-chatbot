"""
GCS → 로컬 vector_db 동기화 스크립트
gsutil -m rsync 대체 (google-cloud-cli 설치 없이 동작)
"""

import os
import sys
from pathlib import Path

BUCKET_NAME = "test-icore-vector-db"
GCS_PREFIX = "vector_db/"
LOCAL_DIR = Path("data/vector_db")


def sync():
    from google.cloud import storage

    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blobs = list(bucket.list_blobs(prefix=GCS_PREFIX))

    if not blobs:
        print("vector_db 없음, 건너뜀")
        return

    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    synced = 0
    for blob in blobs:
        if blob.name.endswith("/"):
            continue
        relative = blob.name[len(GCS_PREFIX):]
        local_path = LOCAL_DIR / relative
        local_path.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(local_path))
        synced += 1

    print(f"vector_db 동기화 완료: {synced}개 파일")


if __name__ == "__main__":
    try:
        sync()
    except Exception as e:
        print(f"vector_db 동기화 실패 (건너뜀): {e}", file=sys.stderr)
