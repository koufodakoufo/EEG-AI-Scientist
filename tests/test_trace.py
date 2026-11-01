from __future__ import annotations
import json
from pathlib import Path
import tempfile
import unittest
from eegfm.improvement.trace import collect_visible_trace
from eegfm.improvement.trace import visible_payload
from eegfm.agent.actor import validate_isolation_gate


class TraceTests(unittest.TestCase):
    def test_reasoning_and_developer_context_excluded(self) -> None:
        for payload in [{'type':'reasoning','encrypted_content':'secret'},{'type':'message','role':'assistant','channel':'analysis','content':'private'},
                        {'type':'message','role':'developer','content':'builder private'}]:
            self.assertIsNone(visible_payload(payload))
        kept=visible_payload({'type':'custom_tool_call','name':'exec','input':'text(1)','encrypted_content':'secret'})
        self.assertNotIn('encrypted_content',kept)

    def test_collect_preserves_tools_and_sanitizes_native(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); sessions=root/'home/sessions'; sessions.mkdir(parents=True)
            path=sessions/'rollout.jsonl'
            rows=[{'type':'response_item','payload':{'type':'reasoning','encrypted_content':'SECRET'}},
                  {'type':'response_item','payload':{'type':'custom_tool_call','name':'exec','input':'text(1)','call_id':'c1'}},
                  {'type':'turn_context','payload':{'model':'gpt-6.1-sol','account_id':'PRIVATE'}},
                  {'type':'response_item','payload':{'type':'additional_tools','tools':[{'type':'namespace','name':'functions','tools':[{'type':'custom','name':'exec'}]}]}}]
            path.write_text('\n'.join(json.dumps(r) for r in rows))
            result=collect_visible_trace(root/'home',root/'trace')
            self.assertEqual(result['declared_tools'],['functions.exec'])
            self.assertEqual(result['visible_events'],1)
            self.assertNotIn('SECRET',path.read_text()); self.assertNotIn('PRIVATE',path.read_text())

    def test_fabricated_or_partial_isolation_status_is_insufficient(self) -> None:
        with self.assertRaises(RuntimeError): validate_isolation_gate({}, {'status':'passed'})
        with self.assertRaises(RuntimeError): validate_isolation_gate({'native_binary_sha256':'x'},{'status':'passed','schema_version':'isolation_report_v2'})


if __name__=='__main__': unittest.main()
