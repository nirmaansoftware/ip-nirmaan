"""IP Nirmaan: the company definition.

Everything here is data. ``nirmaan_definition()`` returns the declarative
company, and ``build_organization()`` derives staffing, applies registered
extensions, validates, and freezes it.
"""

from __future__ import annotations

from nirmaan.company.capabilities import CAPABILITIES
from nirmaan.company.governance import AUTHORITY, CONSTITUTION, ESCALATION, GATES
from nirmaan.company.org_chart import COMPANY_NAME, EXECUTIVES, LEVEL_PROFILES, units
from nirmaan.company.skills import SKILLS
from nirmaan.company.tools import TOOLS
from nirmaan.company.vocabulary import ASSUMPTIONS, FEATURES, INTENTS, PARAMETERS
from nirmaan.company.workflows import WORKFLOWS
from nirmaan.org.organization import CompanyDefinition, Organization, OrganizationBuilder


def nirmaan_definition() -> CompanyDefinition:
    return CompanyDefinition(
        name=COMPANY_NAME,
        units=units(),
        roles=list(EXECUTIVES),
        level_profiles=list(LEVEL_PROFILES),
        skills=list(SKILLS),
        capabilities=list(CAPABILITIES),
        tools=list(TOOLS),
        workflows=list(WORKFLOWS),
        gates=list(GATES),
        principles=list(CONSTITUTION),
        authority=list(AUTHORITY),
        escalation=list(ESCALATION),
        intents=list(INTENTS),
        features=list(FEATURES),
        parameters=list(PARAMETERS),
        assumptions=list(ASSUMPTIONS),
    )


def builder() -> OrganizationBuilder:
    """A builder over the IP Nirmaan definition, ready for overlays."""
    return OrganizationBuilder(nirmaan_definition())


def build_organization(extensions: bool = True) -> Organization:
    return builder().build(extensions=extensions)


__all__ = ["COMPANY_NAME", "build_organization", "builder", "nirmaan_definition"]
