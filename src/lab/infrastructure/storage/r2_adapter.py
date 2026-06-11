import os
from pathlib import Path

import boto3

from lab.platform.storage.port import StoragePort


class R2Adapter(StoragePort):
    def __init__(self) -> None:
        self._bucket = os.environ["R2_BUCKET_NAME"]
        self._client = boto3.client(
            "s3",
            endpoint_url=os.environ["R2_ENDPOINT_URL"],
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        )

    def upload(self, local_path: Path, remote_key: str) -> None:
        self._client.upload_file(str(local_path), self._bucket, remote_key)

    def download(self, remote_key: str, local_path: Path) -> None:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        self._client.download_file(self._bucket, remote_key, str(local_path))

    def delete(self, remote_key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=remote_key)
