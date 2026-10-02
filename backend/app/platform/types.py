from dataclasses import dataclass


@dataclass(frozen=True)
class Capability:
    code: str
    domain: str
    sensitive: bool = False
    tenant_role: bool = False
    tenant_enabled: bool = False
    mutates_business_state: bool = True
    read_only_safe: bool = False
    module_code: str | None = None
