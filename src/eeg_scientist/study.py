"""Deprecated compatibility shim.

The implementation is in `eeg_scientist.legacy.study`. New code must use
the unified `study`/`review` entry points. This file exists only so old
commands and tests can still import the historical path.
"""

from .legacy.study import *  # noqa: F401,F403
from .legacy.study import _build_development_facts, _pair_order
