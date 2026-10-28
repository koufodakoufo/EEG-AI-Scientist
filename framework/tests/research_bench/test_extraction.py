from __future__ import annotations
import unittest
from eegfm.research_bench.extraction import validate_extraction
from eegfm.research_bench.schema import ValidationError


class ExtractionTests(unittest.TestCase):
    def example(self,text: str='Measured accuracy is 0.7.') -> tuple:
        document={'document_id':'d','source':'report.md','text':'Result: '+text}
        claim={'claim_id':'d_C1','text':text,'scope':{},'polarity':'positive','source_span':{'source':'report.md','start':0,'end':1},'evidence_ids':[]}
        value={'protocol_version':'atomic_extract_v1','documents':[{'document_id':'d','claims':[claim],'extraction_notes':[]}]}
        return value,[document]
    def test_exact_quote_alignment_is_recorded(self) -> None:
        value,documents=self.example(); result=validate_extraction(value,documents)
        self.assertEqual(result['documents'][0]['claims'][0]['source_span']['start'],8)
        self.assertEqual(len(result['deterministic_span_alignments']),1)
    def test_invented_text_or_ambiguous_span_rejected(self) -> None:
        value,documents=self.example(); value['documents'][0]['claims'][0]['text']='Accuracy is perfect.'
        with self.assertRaises(ValidationError): validate_extraction(value,documents)
        value,documents=self.example(); documents[0]['text']*=2
        with self.assertRaises(ValidationError): validate_extraction(value,documents)
    def test_missing_document_rejected(self) -> None:
        value,documents=self.example(); value['documents']=[]
        with self.assertRaises(ValidationError): validate_extraction(value,documents)


if __name__=='__main__': unittest.main()
