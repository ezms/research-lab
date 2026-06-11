from dotenv import load_dotenv

load_dotenv()

import lab.research.housing_reality.manifest  # noqa: F401 — populates research registry

from lab.ui.app import run

if __name__ == "__main__":
    run()
