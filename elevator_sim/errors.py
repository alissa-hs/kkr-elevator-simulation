"""Custom exceptions for the elevator simulation.

Kept in one module with no imports, so any other module can raise them
without creating an import cycle.
"""


class ConfigError(ValueError):
    """Invalid simulation configuration (bad or missing settings, unknown scheduler)."""


class InputError(ValueError):
    """Invalid requests. The message lists every bad row, one per line."""


class SimulationError(RuntimeError):
    """The simulation reached a state that should be impossible.

    Raised by guards (starvation, max_ticks), invariant checks, an invalid
    dispatcher answer, or a car moving outside the building.
    """
