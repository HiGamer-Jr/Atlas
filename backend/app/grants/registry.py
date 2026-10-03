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
    module_code: str | None
    resolve_entity: Callable
    authorize_domain: Callable
    handler: Callable | None = None
    enabled: bool = True


class MaintenanceActionRegistry:
    def __init__(self, actions: Iterable[MaintenanceAction] = ()):
        values = list(actions)
        from app.maintenance.registry import MaintenanceHandler

        for action in values:
            if (
                action.handler is not None
                and not callable(action.handler)
                and not isinstance(action.handler, MaintenanceHandler)
            ):
                raise ValueError("Executable handler must be typed")
            if isinstance(action.handler, MaintenanceHandler):
                action.handler.validate_contract()
                if action.module_code is None and not action.handler.foundation_action:
                    raise ValueError("Operational handler requires its module")
        if len({action.action_code for action in values}) != len(values):
            raise ValueError("Duplicate registered action")
        self._actions = MappingProxyType(
            {action.action_code: action for action in values}
        )

    def get(self, code):
        action = self._actions.get(code)
        if action is None or not action.enabled:
            raise ApiError(
                403,
                "MAINTENANCE_ACTION_UNAVAILABLE",
                "Operação de manutenção indisponível.",
            )
        return action

    def list(self):
        return tuple(action for action in self._actions.values() if action.enabled)
