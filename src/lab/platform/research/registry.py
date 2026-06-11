from lab.platform.research.manifest import ResearchManifest

_REGISTRY: dict[str, type[ResearchManifest]] = {}


def register_research(cls: type[ResearchManifest]) -> type[ResearchManifest]:
    _REGISTRY[cls.id] = cls
    return cls


def get_registry() -> dict[str, type[ResearchManifest]]:
    return dict(_REGISTRY)
