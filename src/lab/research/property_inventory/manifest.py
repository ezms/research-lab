from pydantic import BaseModel

from lab.platform.research.manifest import OutputType, ResearchManifest
from lab.platform.research.registry import register_research
from lab.research.property_inventory.params import PropertyInventoryParams


@register_research
class PropertyInventoryResearch(ResearchManifest):
    id = "property_inventory"
    name = "Inventário de Imóveis"
    description = (
        "Levanta padrões de configuração física de imóveis brasileiros — tipos de cômodo, "
        "áreas externas, infraestrutura e variações regionais. Fonte: MercadoLivre Imóveis. "
        "Documenta também casos de divergência entre função arquitetônica e uso real."
    )
    params_model = PropertyInventoryParams
    output_types = [OutputType.TABLE, OutputType.CHART]

    @classmethod
    def local_results(cls, params: BaseModel) -> dict | None:
        from lab.research.property_inventory.pipeline.runner import find_local_results

        return find_local_results(PropertyInventoryParams.model_validate(params.model_dump()))

    def run(self, params: BaseModel) -> dict:
        from lab.research.property_inventory.pipeline import runner

        return runner.run(PropertyInventoryParams.model_validate(params.model_dump()))
