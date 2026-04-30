"""Public API for PyGreenSense."""

from importlib.metadata import PackageNotFoundError, version

from .core import analyze_file, analyze_project
from .rules import (
    DeadCodeRule,
    DuplicatedCodeRule,
    GodClassRule,
    LongMethodRule,
    MutableDefaultArgumentsRule,
)

try:
    __version__ = version("pygreensense")
except PackageNotFoundError:
    __version__ = "0.0.3"

__all__ = [
    "__version__",
    "analyze_file",
    "analyze_project",
    "DeadCodeRule",
    "DuplicatedCodeRule",
    "GodClassRule",
    "LongMethodRule",
    "MutableDefaultArgumentsRule",
]
