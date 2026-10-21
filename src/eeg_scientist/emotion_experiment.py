"""Deprecated compatibility shim.

The implementation is in `eeg_scientist.legacy.emotion_experiment`. New code must use
the unified `study`/`review` entry points. This file exists only so old
commands and tests can still import the historical path.
"""

from .legacy.emotion_experiment import *  # noqa: F401,F403
from .legacy.emotion_experiment import _assert_lock
