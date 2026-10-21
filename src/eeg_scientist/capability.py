"""Deprecated compatibility shim.

The implementation is in `eeg_scientist.legacy.capability`. New code must use
the unified `study`/`review` entry points. This file exists only so old
commands and tests can still import the historical path.
"""

from .legacy.capability import *  # noqa: F401,F403
