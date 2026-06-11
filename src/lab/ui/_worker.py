import json
import subprocess
import sys
from pathlib import Path

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
        self._proc: subprocess.Popen | None = None

    def run(self) -> None:
        payload = json.dumps({
            "manifest": f"{self._manifest_cls.__module__}:{self._manifest_cls.__qualname__}",
            "params": self._params.model_dump(mode="json"),
        }).encode()

        self._proc = subprocess.Popen(
            [sys.executable, "-m", "lab.ui._pipeline_runner"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = self._proc.communicate(input=payload)

        if self._proc.returncode == 0:
            data = json.loads(stdout)
            result = {
                uf: {ft: Path(p) for ft, p in files.items()}
                for uf, files in data.items()
            }
            self.finished.emit(result)
        elif self._proc.returncode in (-15, -9):  # SIGTERM/SIGKILL — user cancelled
            pass
        else:
            self.errored.emit(stderr.decode() or f"Processo encerrou com código {self._proc.returncode}")

    def terminate(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
        super().terminate()
