"""Validate model extraction, ground exact quotes, and retain every correction."""
from __future__ import annotations
import json
from typing import Any
from .schema import AtomicClaim,ValidationError


def validate_extraction(value: Any,documents: list[dict[str,Any]]) -> dict[str,Any]:
    if not isinstance(value,dict) or set(value)!={'protocol_version','documents'} or value['protocol_version']!='atomic_extract_v1':
        raise ValidationError('Unsupported extraction envelope')
    sources={d['document_id']:d for d in documents}
    if len(sources)!=len(documents): raise ValidationError('Duplicate source document IDs')
    if not isinstance(value['documents'],list): raise ValidationError('documents must be an array')
    seen=set(); result=[]; alignments=[]
    for item in value['documents']:
        if not isinstance(item,dict) or set(item)!={'document_id','claims','extraction_notes'}:
            raise ValidationError('Extraction document fields mismatch')
        identifier=item['document_id']
        if identifier not in sources or identifier in seen: raise ValidationError('Unknown or duplicate extracted document ID')
        seen.add(identifier); source=sources[identifier]; report=source['text']
        if not isinstance(item['claims'],list) or len(item['claims'])>30: raise ValidationError('Claim count exceeds extraction cap')
        claims=[]; ids=set()
        for original in item['claims']:
            claim=json.loads(json.dumps(original))
            text=claim.get('text')
            if not isinstance(text,str) or not text or text not in report: raise ValidationError('Extracted claim is not an exact source quote')
            span=claim.get('source_span',{})
            start,end=span.get('start'),span.get('end')
            accurate=type(start) is int and type(end) is int and 0<=start<end<=len(report) and report[start:end]==text
            if not accurate:
                if report.count(text)!=1: raise ValidationError('Ambiguous repeated quote with invalid offsets')
                corrected={'source':source['source'],'start':report.index(text),'end':report.index(text)+len(text)}
                alignments.append({'claim_id':claim.get('claim_id'),'proposed':span,'aligned':corrected,'method':'unique_exact_quote'})
                claim['source_span']=corrected
            else:
                if span.get('source')!=source['source']: raise ValidationError('Wrong source filename')
            validated=AtomicClaim.from_dict(claim)
            if validated.claim_id in ids: raise ValidationError('Duplicate extracted claim ID')
            ids.add(validated.claim_id); claims.append(validated.to_dict())
        result.append({'document_id':identifier,'claims':claims,'extraction_notes':item['extraction_notes']})
    if seen!=set(sources): raise ValidationError('Extraction omitted a source document')
    return {'protocol_version':'atomic_extract_v1','documents':result,'deterministic_span_alignments':alignments}
