# PREFLIGHT

- checked_at_utc: 2026-10-18T17:37:44Z
- local_time: 2026-10-19T01:37:44+08:00
- timezone: 中国标准时间
- deadline: 2026-10-19T09:14:21+08:00
- deadline_utc: 2026-10-19T01:14:21+00:00
- report_reserve_minutes: 60
- cwd: X:\projects\EEG-AI-Scientist
- python: 3.12.4
- platform: Windows-11-10.0.26200-SP0
- cpu_count: 20
- disk_free_gb: 465.0

## Model route

- provider_kind: ollama_native
- provider_name: ollama_local
- model: qwen3.5:9b
- backend: real_llm
- health: {"ok": true, "models": [{"name": "qwen3.5:27b", "model": "qwen3.5:27b", "modified_at": "2026-07-24T02:44:21.3872876+08:00", "size": 17420432728, "digest": "7653528ba5cba4dd8e19da24aaddc7f4d0b5ecd93571c0825dfd4137958ec06e", "details": {"parent_model": "", "format": "gguf", "family": "qwen35", "families": ["qwen35"], "parameter_size": "27.8B", "quantization_level": "Q4_K_M", "context_length": 262144, "embedding_length": 5120}, "capabilities": ["vision", "completion", "tools", "thinking"]}, {"name": "qwen3.5:9b", "model": "qwen3.5:9b", "modified_at": "2026-07-24T02:32:33.1911612+08:00", "size": 6594474711, "digest": "6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7", "details": {"parent_model": "", "format": "gguf", "family": "qwen35", "families": ["qwen35"], "parameter_size": "9.7B", "quantization_level": "Q4_K_M", "context_length": 262144, "embedding_length": 4096}, "capabilities": ["vision", "completion", "tools", "thinking"]}, {"name": "deepseek-r1:8b", "model": "deeps
- describe: {"license": "                                Apache License\n                           Version 2.0, January 2004\n                        http://www.apache.org/licenses/\n\n   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION\n\n   1. Definitions.\n\n      \"License\" shall mean the terms and conditions for use, reproduction,\n      and distribution as defined by Sections 1 through 9 of this document.\n\n      \"Licensor\" shall mean the copyright owner or entity authorized by\n      the copyright owner that is granting the License.\n\n      \"Legal Entity\" shall mean the union of the acting entity and all\n      other entities that control, are controlled by, or are under common\n      control with that entity. For the purposes of this definition,\n      \"control\" means (i) the power, direct or indirect, to cause the\n      direction or management of such entity, whether by contract or\n      otherwise, or (ii) ownership of fifty percent (50%) or more of the\n      outstanding shares, or (iii) beneficial ownership of such entity.\n\n      \"You\" (or \"Your\") shall mean an individual or Legal Entity\n      exercising permissions granted by this License.\n\n      \"Source\" form shall mean the preferred form for making modifications,\n      including but not limited to software source code, documentation\n      source, and configuration files.\n\n      \"Object\" form shall mean any form resulting from mechanical\n      transformation or translation of a Sourc
- probe_status: ok
- probe_ok: True
- probe_latency_ms: 13059.8
- probe_usage: {"prompt_tokens": 32, "completion_tokens": 12, "total_tokens": 44}
- probe_error: 

## Cloud/API environment (boolean only; no values)

- SCIENTIST_API_KEY: False
- SCIENTIST_BASE_URL: False
- SCIENTIST_MODEL: False
- DEEPSEEK_API_KEY: False
- OPENAI_API_KEY: False
- OPENAI_BASE_URL: False

## Repository and power

```text
## main...github/main
 M .gitignore
 M pyproject.toml
 M uv.lock
?? EEG_AI_Scientist_Overnight_Plan.md
?? configs/
?? prompts/
?? reports/
?? src/
```

```text
电源方案 GUID: 64a64f24-65b9-4b56-befd-5ec1eaced9b3  (Silent)
  子组 GUID: 238c9fa8-0aad-41ed-83f4-97be242c8f20  (睡眠)
    GUID 别名: SUB_SLEEP
    电源设置 GUID: 29f6c1db-86da-48c5-9fdb-f2b67b1f44da  (在此时间后睡眠)
      GUID 别名: STANDBYIDLE
      最小可能的设置: 0x00000000
      最大可能的设置: 0xffffffff
      可能的设置增量: 0x00000001
      可能的设置单位: 秒
    当前交流电源设置索引: 0x00000000
    当前直流电源设置索引: 0x00000384
```

## Interpretation

Desktop login and Python model access are separate. The local Ollama route is the primary route when the provider kind is ollama_native. A probe failure is a blocker; it must not be reported as a successful AI run.
