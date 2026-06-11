from abc import ABC, abstractmethod
from enum import Enum
from typing import ClassVar

from pydantic import BaseModel


class OutputType(Enum):
    TABLE = "table"
    CHART = "chart"
    REPORT = "report"
    NOTEBOOK = "notebook"


class ResearchManifest(ABC):
    id: ClassVar[str]
    name: ClassVar[str]
    description: ClassVar[str]
    params_model: ClassVar[type[BaseModel]]
    output_types: ClassVar[list[OutputType]]

    @classmethod
    def local_results(cls, params: BaseModel) -> "dict | None":
        return None

    @abstractmethod
    def run(self, params: BaseModel) -> dict:
        pass
