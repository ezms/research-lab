from pydantic import BaseModel
from PySide6.QtCore import QThread, Signal

from lab.platform.research.manifest import ResearchManifest


class ResearchWorker(QThread):
    finished: Signal = Signal(dict)
    errored: Signal = Signal(str)

    def __init__(self, manifest_cls: type[ResearchManifest], params: BaseModel) -> None:
        super().__init__()
        self._manifest_cls = manifest_cls
        self._params = params

    def run(self) -> None:
        try:
            result = self._manifest_cls().run(self._params)
            self.finished.emit(result)
        except Exception as exc:
            self.errored.emit(str(exc))
