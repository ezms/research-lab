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


class Parseable(ABC):
    @abstractmethod
    def parse(self, file_path: Path) -> dict[str, Path]:
        pass


class VariableMappable(ABC):
    @abstractmethod
    def map_variables(self, parsed_data: dict[str, Path]) -> dict[str, Path]:
        pass


class DataSource(Identifiable, Downloadable, Parseable, VariableMappable):
    """Full data source contract: identifies, downloads, parses and maps."""
