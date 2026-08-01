# Raw event data dictionary

Each execution produces one JSON object in `results/raw/runs.jsonl`.

Required fields:

- `run_id`: UUID
- `experiment_name`
- `git_commit`
- `case_id`
- `pair_id`
- `workflow`
- `purpose`
- `variant`
- `attack_class`
- `condition`
- `model_provider`
- `model_name`
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
- `request_payload`
- `raw_response`
- `parsed_output`
- `tool_calls`
- `accessed_fields`
- `policy_events`
- `evidence`
- `token_usage`
- `estimated_cost`
- `error`

Never overwrite raw events. Corrections must be represented as new derived data or an explicit exclusion manifest.
