from __future__ import annotations
from pathlib import PurePosixPath as Path
import unittest
from eegfm.research_bench.actor import actor_argv, build_profile


class ActorConfigTests(unittest.TestCase):
    def profile(self, control: Path = Path('/trusted/control')) -> str:
        return build_profile(case=Path('/isolated/case'),public=Path('/isolated/case/public'),
                             control_home=control,runtime=Path('/trusted/runtime'),
                             native_binary=Path('/runtime/codex'),bwrap_dir=Path('/runtime/bwrap'))

    def test_no_legacy_sandbox_or_network_permission_composition(self) -> None:
        profile=self.profile()
        self.assertNotIn('sandbox_mode',profile)
        self.assertIn('default_permissions = "actor"',profile)
        self.assertIn('web_search = "disabled"',profile)
        self.assertIn('inherit = "none"',profile)
        self.assertNotIn('proxy',profile.lower())
        self.assertIn('"/trusted/control" = "deny"',profile)

    def test_control_home_cannot_live_in_case(self) -> None:
        with self.assertRaisesRegex(ValueError,'outside'):
            self.profile(Path('/isolated/case/secrets'))

    def test_argv_does_not_resume_or_mix_legacy_permissions(self) -> None:
        argv=actor_argv({'native_binary':'/runtime/codex','case':'/isolated/case'},'ONLY THIS PROMPT',Path('/trusted/final.txt'))
        self.assertIn('--ignore-rules',argv)
        self.assertNotIn('--ignore-user-config',argv)  # 0.165.0 would discard the restrictive profile
        self.assertNotIn('--ephemeral',argv)  # fresh protected rollout needed for nested tool provenance
        self.assertNotIn('resume',argv)
        self.assertNotIn('--sandbox',argv)
        self.assertEqual(argv[-1],'ONLY THIS PROMPT')


if __name__ == '__main__': unittest.main()
