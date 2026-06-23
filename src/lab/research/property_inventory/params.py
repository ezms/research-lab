from typing import Literal

from pydantic import BaseModel

from lab.enums.uf import UF


class PropertyInventoryParams(BaseModel):
    source: Literal["ml_imoveis"] = "ml_imoveis"
    ufs: list[UF] | None = None
    negocio: Literal["aluguel", "venda"] | None = None  # None = ambos
