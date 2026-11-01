"""Explicit host boundaries for offline verification."""
from __future__ import annotations
import sys
import pytest


LINUX_TESTS = {
    "test_actor_cannot_redirect_output_root_to_host_directory",
    "test_crashed_launch_consumes_durable_session_budget",
    "test_driver_lifetime_lease_prevents_second_controller_launch",
    "test_driver_session_budget_block_is_controller_owned",
    "test_invalid_actor_request_has_immutable_safe_feedback",
    "test_real_driver_loop_waits_and_honors_blocked_without_legacy_argv",
    "test_symlink_and_hardlink_candidates_rejected",
    "test_parser_rejects_duplicate_keys_cross_episode_links_and_big_batch",
    "test_scripted_native_boundary_completes_actual_driver_loop_five_sessions",
}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if sys.platform != "linux":
        marker = pytest.mark.skip(reason="Linux lifecycle and process isolation required")
        for item in items:
            if item.path.name == "test_program.py" or item.name in LINUX_TESTS:
                item.add_marker(marker)
