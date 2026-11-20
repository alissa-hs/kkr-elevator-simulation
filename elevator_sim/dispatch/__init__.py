"""Dispatcher registry.

Adding a strategy = one new module in this package + one line in DISPATCHERS.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from elevator_sim.config import ConfigError
from elevator_sim.dispatch.base import Dispatcher
from elevator_sim.dispatch.nearest import NearestCarDispatcher

if TYPE_CHECKING:
    from elevator_sim.config import SimConfig

DISPATCHERS: dict[str, type[Dispatcher]] = {
    NearestCarDispatcher.name: NearestCarDispatcher,
}


def unknown_scheduler_message(name: str) -> str:
    return f"unknown scheduler '{name}'; choose from: {', '.join(DISPATCHERS)}"


def get_dispatcher(name: str, config: SimConfig) -> Dispatcher:
    """Instantiate the dispatcher registered under ``name``."""
    try:
        cls = DISPATCHERS[name]
    except KeyError:
        raise ConfigError(unknown_scheduler_message(name)) from None
    return cls(config)


__all__ = ["DISPATCHERS", "Dispatcher", "get_dispatcher", "unknown_scheduler_message"]
