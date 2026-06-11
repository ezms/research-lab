from abc import ABC, abstractmethod

import pandas as pd


class DatabasePort(ABC):
    @abstractmethod
    def query(self, sql: str) -> pd.DataFrame:
        """Execute a SELECT statement and return the result as a DataFrame."""

    @abstractmethod
    def execute(self, sql: str) -> None:
        """Execute a non-SELECT statement (CREATE, INSERT, COPY TO, etc.)."""
