from dataclasses import dataclass


@dataclass(frozen=True)
class Capability:
    code: str
    domain: str
    sensitive: bool = False
    tenant_role: bool = False
    tenant_enabled: bool = False
