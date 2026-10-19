# tai-unix-offset-utils
# Exports the leap-second table and conversion helpers.
from .core import (
    LEAP_SECONDS,
    atomic_to_unix,
    unix_to_atomic,
)

__all__ = [
    "LEAP_SECONDS",
    "atomic_to_unix",
    "unix_to_atomic",
    "__version__",
]

__version__ = "1.0.0"
