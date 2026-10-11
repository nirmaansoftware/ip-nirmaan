"""The organization layer: build, validate, and query the company."""

from nirmaan.org.authority import AuthorityService, route_escalation
from nirmaan.org.organization import (
    CompanyDefinition,
    Organization,
    OrganizationBuilder,
    OrganizationError,
    available_extensions,
    register_extension,
    unregister_extension,
)
from nirmaan.org.validate import validate_organization

__all__ = [
    "AuthorityService",
    "CompanyDefinition",
    "Organization",
    "OrganizationBuilder",
    "OrganizationError",
    "available_extensions",
    "register_extension",
    "route_escalation",
    "unregister_extension",
    "validate_organization",
]
