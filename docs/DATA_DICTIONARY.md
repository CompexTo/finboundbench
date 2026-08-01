# Raw event data dictionary

Each execution produces one JSON object in `results/raw/runs.jsonl`.

Required fields:

- `run_id`: UUID
- `experiment_name`
- `protocol_version`
- `git_sha` and compatibility alias `git_commit`
- `configuration_hash`
- `dataset_hash`
- `case_id`
- `pair_id`
- `workflow`
- `purpose`
- `variant`
- `attack_class`
- `condition`
- `model_provider`
- `model_name`
- `model_identifier`
- `model_version`
- `seed`
- `repetition`
- `policy_hash`
- `prompt_hash`
- `input_hash`
- `authorized_projection_hash`
- `started_at`
- `ended_at`
- `latency_ms`
- `status`
- `request`: exact intended OpenAI-compatible request
- `request_payload`
- `raw_response`
- `parsed_output`
- `tool_calls`
- `accessed_fields`
- `denied_fields`
- `policy_events`
- `output_validation_events`
- `compex_run_id`
- `evidence_id`
- `evidence`
- `token_usage`
- `estimated_cost`
- `attempts`
- `retry_policy`
- `output_hash`
- `previous_event_hash`
- `event_hash`
- `error`

Never overwrite raw events. Corrections must be represented as new derived data or an explicit exclusion manifest.

For Compex executions, `accessed_fields` means the explicit columns in the
policy-checked projection consumed by the research agent. It is supported by
the Analyze requested-field echo, projection SQL, artifact checksum, and agent
input-field echo; it is not lower-level per-value database telemetry.

Synthetic-resource cleanup is recorded separately in
`results/raw/cleanup.jsonl` after the execution event and full evidence have
been durably appended.
