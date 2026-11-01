"""Legacy adapter must not mistake a truncated/error stream for completion."""
from __future__ import annotations
import json
import sys
import unittest

if sys.platform=='linux':
    from eegfm.agent.driver import Adapter


@unittest.skipUnless(sys.platform=='linux','Legacy driver uses Linux fcntl')
class LegacyAdapterCompletionTests(unittest.TestCase):
    def test_empty_malformed_and_truncated_zero_exit_are_failures(self) -> None:
        adapter=Adapter('codex')
        for stdout in ('','not-json\n',json.dumps({'type':'thread.started','thread_id':'fixture'})):
            with self.subTest(stdout=stdout):
                self.assertFalse(adapter.classify(0,stdout,'',False)[0])

    def test_spaced_error_event_is_not_success(self) -> None:
        adapter=Adapter('codex')
        stdout=json.dumps({'type':'error','message':'connection reset by peer'})+'\n'+json.dumps({'type':'turn.completed','usage':{}})
        ok,kind,_=adapter.classify(0,stdout,'',False)
        self.assertFalse(ok); self.assertEqual(kind,'transient')

    def test_success_text_does_not_trigger_auth_classifier(self) -> None:
        stdout=json.dumps({'type':'item.completed','item':{'text':'Documented an unauthorized example.'}})+'\n'+json.dumps({'type':'turn.completed','usage':{}})
        self.assertTrue(Adapter('codex').classify(0,stdout,'',False)[0])
        self.assertFalse(Adapter('codex').classify(0,stdout,'',True)[0])
        self.assertTrue(Adapter('script').classify(0,'ordinary output','',False)[0])

    def test_auth_error_is_fatal_even_with_zero_exit(self) -> None:
        stdout=json.dumps({'type':'turn.failed','error':{'message':'authentication failed'}})
        ok,kind,_=Adapter('codex').classify(0,stdout,'',False)
        self.assertFalse(ok); self.assertEqual(kind,'fatal')


if __name__=='__main__': unittest.main()
