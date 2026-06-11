import pytest
from pydantic import BaseModel

from lab.platform.research.manifest import OutputType, ResearchManifest
from lab.platform.research.registry import get_registry, register_research


class _DummyParams(BaseModel):
    value: int = 0


@register_research
class _DummyResearch(ResearchManifest):
    id = "dummy_registry_test"
    name = "Dummy"
    description = "Test research"
    params_model = _DummyParams
    output_types = [OutputType.TABLE]

    def run(self, params: BaseModel) -> dict:
        return {}


def test_register_research_adds_to_registry():
    assert "dummy_registry_test" in get_registry()


def test_registered_class_is_correct():
    assert get_registry()["dummy_registry_test"] is _DummyResearch


def test_get_registry_returns_copy():
    registry = get_registry()
    registry["should_not_persist"] = None  # type: ignore[assignment]
    assert "should_not_persist" not in get_registry()


def test_housing_reality_is_registered():
    import lab.research.housing_reality.manifest  # noqa: F401 — trigger registration

    assert "housing_reality" in get_registry()
