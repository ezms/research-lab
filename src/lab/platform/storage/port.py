from abc import ABC, abstractmethod
from pathlib import Path


class StoragePort(ABC):
    @abstractmethod
    def upload(self, local_path: Path, remote_key: str) -> None:
        """Upload a local file to remote storage."""
        ...

    @abstractmethod
    def download(self, remote_key: str, local_path: Path) -> None:
        """Download a file from remote storage to local disk."""
        ...

    @abstractmethod
    def delete(self, remote_key: str) -> None:
        """Delete a file from remote storage."""
        ...
