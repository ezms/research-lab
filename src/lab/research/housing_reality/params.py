from typing import Literal

from pydantic import BaseModel

from lab.enums.uf import UF


class HousingRealityParams(BaseModel):
    source: Literal["census_2010", "pnadc_visita1"] | None = None
    ufs: list[UF] | None = None
    pnadc_year: int = 2025
