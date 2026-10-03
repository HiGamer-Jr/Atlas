"""Closed server registration; production contains no executable actions."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from types import MappingProxyType

from app.core.errors import ApiError


@dataclass(frozen=True)
class MaintenanceAction:
    action_code: str
    label: str
    entity_type: str
    capability: str
    module_code: str
    resolve_entity: Callable
    authorize_domain: Callable
    handler: Callable | None = None


class MaintenanceActionRegistry:
    def __init__(self, actions: Iterable[MaintenanceAction] = ()):
        values = list(actions)
        if len({action.action_code for action in values}) != len(values):
            raise ValueError("Duplicate registered action")
        self._actions = MappingProxyType(
            {action.action_code: action for action in values}
        )

    def get(self, code):
        action = self._actions.get(code)
        if action is None:
            raise ApiError(
                403,
                "MAINTENANCE_ACTION_UNAVAILABLE",
                "Operação de manutenção indisponível.",
            )
        return action

    def list(self):
        return tuple(self._actions.values())
