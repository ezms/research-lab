from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceIdentity:
    name: str
    version: str
    provider: str
    description: str


class Identifiable(ABC):
    @abstractmethod
    def identify(self) -> SourceIdentity:
        pass


class Downloadable(ABC):
    @abstractmethod
    def download(self) -> Path:
        pass
