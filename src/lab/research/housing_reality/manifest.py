from pydantic import BaseModel

from lab.platform.research.manifest import OutputType, ResearchManifest
from lab.platform.research.registry import register_research
from lab.research.housing_reality.params import HousingRealityParams


@register_research
class HousingRealityResearch(ResearchManifest):
    id = "housing_reality"
    name = "Realidade Habitacional"
    description = (
        "Analisa condições habitacionais brasileiras a partir dos microdados "
        "do Censo Demográfico 2010, cruzando configuração física dos domicílios "
        "com composição dos moradores."
    )
    params_model = HousingRealityParams
    output_types = [OutputType.TABLE, OutputType.CHART, OutputType.NOTEBOOK]

    @classmethod
    def local_results(cls, params: BaseModel) -> dict | None:
        from lab.research.housing_reality.pipeline.runner import find_local_results

        return find_local_results(HousingRealityParams.model_validate(params.model_dump()))

    def run(self, params: BaseModel) -> dict:
        from lab.research.housing_reality.pipeline import runner

        return runner.run(HousingRealityParams.model_validate(params.model_dump()))
