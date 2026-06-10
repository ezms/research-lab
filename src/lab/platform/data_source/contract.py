from abc import ABC, abstractmethod


class Identifiable(ABC):
    @abstractmethod
    def identify(self) -> dict:
        pass


class Downloadable(ABC):
    @abstractmethod
    def download(self):
        pass


class Parseable(ABC):
    @abstractmethod
    def parse(self):
        pass


class VariableMappable(ABC):
    @abstractmethod
    def map_variables(self):
        pass


class DataSource(Identifiable, Downloadable, Parseable, VariableMappable):
    """Full data source contract: identifies, downloads, parses and maps."""
