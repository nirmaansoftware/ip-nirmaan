"""Project providers: the only source-aware code in the platform.

Importing this package registers every built-in provider (the decorators run on
import), the same side-effect-import pattern as ``knowledge.packs`` and
``engineering.providers``.
"""

from veritriage.project.providers import manifest, rtl  # noqa: F401  (register on import)
from veritriage.project.providers.base import (
    ProjectCapability,
    ProjectProvider,
    ProjectProviderError,
)
from veritriage.project.providers.registry import (
    available_project_providers,
    collect_project,
    register_project_provider,
    unregister_project_provider,
)

__all__ = [
    "ProjectCapability",
    "ProjectProvider",
    "ProjectProviderError",
    "available_project_providers",
    "collect_project",
    "register_project_provider",
    "unregister_project_provider",
]
