from pydantic import BaseModel

from lab.enums.uf import UF


class HousingRealityParams(BaseModel):
    ufs: list[UF] | None = None
