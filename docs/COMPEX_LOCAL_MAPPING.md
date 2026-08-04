# Compex local interface mapping

Mapping date: 2026-08-01 (Europe/Rome)

This document records a read-only inspection of the local Compex checkout at
`C:\Users\FRHMMH01\Compex-platform`. The inspected platform commit is
`ebf8e27fe782d6d883fbf6de7f5916d0b4debbe6`. The platform worktree already had
unrelated local changes before this study began, so the commit identifier alone
does not completely describe the inspected source. No tracked platform file was
changed by the mapping or benchmark setup.

## Runtime and startup

The local stack is defined by `infra/docker/docker-compose.local.yml` and is
normally started from the Compex repository with:

```text
pnpm local:up
pnpm db:seed
```

`pnpm local:up` builds shared packages and the three local job images, starts
Docker Compose, and initializes MinIO buckets. The Compose services are
`postgres`, `redis`, `minio`, `api`, `worker`, `runner`, `serve-gateway`, and
`platform`.

At mapping time, `docker ps` and `docker compose ... ps` returned no running
containers. HTTP probes to ports 4000, 4002, and 4003 therefore failed. This is
a runtime-state observation, not a schema failure.

| Service | Host URL | Health route | Role |
|---|---|---|---|
| Platform UI | `http://localhost:3000` | n/a | Next.js UI |
| API | `http://localhost:4000` | `GET /health` | REST API and OpenAPI |
| Serve gateway | `http://localhost:4001` | `GET /health` | Token-checked deployed endpoints |
| Worker | `http://localhost:4002` | `GET /health` | BullMQ execution consumer |
| Runner | `http://localhost:4003` | `GET /health` | Docker lifecycle service |
| MinIO | `http://localhost:9000` | `/minio/health/live` | Dataset, artifact, and evidence objects |

The API exposes Swagger UI at `/docs`; NestJS normally exposes the generated
OpenAPI document at `/docs-json`. Source of truth: `services/api/src/main.ts`.

## Authentication and tenancy

Public API routes use `Authorization: Bearer <credential>`. The guard accepts:

- a JWT access token issued by `POST /auth/login`; or
- a Compex API key beginning with `ck_`.

API keys are scoped by organization, optionally by workspace, and by named URL
scopes. The relevant scopes are `datasets:read`, `analyze:write`,
`executions:read`, and `evidence:read`; an API key with `*` also satisfies them.
Role checks still apply. Research credentials must be supplied through the
uncommitted `.env` file and must never be written into reports, Git, raw request
records, container environment evidence, or logs.

Workspace routes use this prefix:

```text
/organizations/{orgId}/workspaces/{workspaceId}
```

## Dataset registration and ingestion

There is no single protected-object JSON endpoint. Compex registers a dataset,
then accepts CSV/JSON as a version:

1. `POST .../datasets`
2. `POST .../datasets/{datasetId}/versions` as `multipart/form-data`, file field
   `file`, maximum 25 MiB
3. optionally `PATCH .../datasets/{datasetId}/fields/{fieldId}` with a
   `FieldClassification`
4. optionally `POST .../datasets/{datasetId}/activate`

Dataset creation accepts `name`, optional `description`, and optional
`classification`. Upload creates an immutable version record, inferred schema,
per-field records, row count, SHA-256, and a MinIO object under
`compex-datasets`. Version responses include schema fields and their IDs.

For this study, one synthetic one-row CSV per benchmark execution is the safe
mapping. The description can carry non-secret purpose/case metadata, while the
policy carries the authoritative allowed/denied field lists. Dataset deletion is
logical archival, not physical object erasure.

## Policy and purpose-contract mapping

Policies are managed at `.../policies`:

- `POST .../policies` creates a policy with `name`, optional `description`,
  `status`, and an optional `rules` array.
- Each rule has `ruleType`, JSON `expression`, and optional `order`.
- `PATCH .../policies/{policyId}` changes description/status.

The runtime schema has `FIELD_ACCESS`, `OUTPUT_CONTROL`, `EXECUTION_LIMIT`,
`RETENTION`, `AUDIT_REQUIRED`, and `ENDPOINT_ACCESS` rule types. A purpose-bound
benchmark policy maps to an active policy with at least:

```json
{
  "ruleType": "FIELD_ACCESS",
  "expression": {
    "allowFields": ["..."],
    "denyFields": ["..."]
  }
}
```

and an `AUDIT_REQUIRED` rule. `FIELD_ACCESS` is actually enforced before
Train/Analyze/Serve work is queued: `checkFieldAccess` rejects a requested
field outside the allow-list or in the deny-list. The general `PolicyEvaluator`
is advisory for other rule types and currently never emits an explicit deny.

Important limitation: `OUTPUT_CONTROL` is represented in the policy schema but
has no content-filtering or output-validation implementation in the inspected
runtime. It must not be reported as enforced evidence.

## Execution submission and response

The generic execution endpoint is:

```text
POST .../executions
```

Request shape (`CreateExecutionRunDto`):

```json
{
  "workflowType": "ANALYZE",
  "image": "container-image:tag",
  "command": [],
  "env": {},
  "queueName": "analyze",
  "approvalRequestId": "optional",
  "timeoutSec": 60,
  "memoryLimitMb": 512,
  "networkMode": "none"
}
```

The endpoint returns an `ExecutionRun`, whose ID is the Compex run identifier.
`GET .../executions/{runId}` returns status, image and runtime settings plus
artifacts and result rows. `GET .../executions/{runId}/logs` returns persisted
stdout/stderr lines. Runs move through `DRAFT`, `SUBMITTED`, `APPROVED`,
`QUEUED`, `RUNNING`, and a terminal state. The API also supports
`POST .../executions/{runId}/cancel`.

Generic execution does not itself evaluate a field-access policy. The safe
research route is therefore two stages:

1. submit an Analyze `custom-sql` job over the full uploaded object, selecting
   only the purpose-allowed columns; Compex validates the SQL's detected fields
   against the attached `FIELD_ACCESS` rule before starting the container;
2. attach the resulting projection artifact, and only that artifact, to a
   second Compex execution that invokes the research model agent under the same
   approved request.

Passing a Python-filtered object directly to the model would bypass Compex and
is forbidden for the `compex_purpose_bound` condition.

## Analyze projection contract

Analyze routes are:

- `POST .../analyze` with `name`, `templateKey`, `datasetId`, optional
  `datasetVersionId`, `policyId`, and `parameters`;
- `POST .../analyze/{jobId}/run`;
- `GET .../analyze/{jobId}`;
- `POST .../analyze/{jobId}/evidence`.

`templateKey: custom-sql` takes `parameters.sql`. The server derives
`requestedFields` by matching dataset column names in that SQL and invokes the
field-access check before creating any execution. The projection query must use
an explicit quoted column list; wildcard selection is not acceptable evidence
because the best-effort detector cannot prove the expanded fields.

A policy-backed Analyze job creates a pending approval request. It cannot run
until `POST .../approvals/{requestId}/decisions` records an `APPROVED` decision.

## Network isolation and resource controls

Batch runs default to Docker `networkMode: none`; the runner also sets memory
and CPU limits, `Privileged: false`, and `no-new-privileges:true`. The worker
currently forwards only `none` or Docker `bridge` for one-shot executions.
A model endpoint requires `bridge`; offline projection stays at `none`.

The original local model-agent image must receive no commercial secret in its
recorded environment. That v1 adapter therefore rejects a non-placeholder model
API key instead of persisting it in `ExecutionRun.env`. Protocol v2 does not
weaken that rule: its governed OpenRouter condition runs through the platform's
separate secret-reference model adapter. The execution contract contains only
the reference identity and hash; the trusted runner resolves the value for the
single allowlisted provider call and disposes the lease afterward.

The v2 remote condition is not represented as local Docker isolation. It is
classified as `REMOTE_PROVIDER_PROCESSING`, pseudonymizes direct identifiers,
transmits only the approved projection, and requires native output release
validation before a result is marked releasable.

No model identifier, temperature, seed, prompt, or token schema exists natively
in Compex. The research container must pass these to the OpenAI-compatible model
endpoint and emit them in its machine-readable result. The adapter must compare
the echoed values with the requested configuration and fail on mismatch.

## Evidence and audit response

Evidence is generated from a non-pending approval:

```text
POST .../evidence
GET  .../evidence/{bundleId}
GET  .../evidence/{bundleId}/download?format=json|pdf|csv
POST .../evidence/{bundleId}/verify
```

Generation returns an `EvidenceBundle`. Its ID is the evidence identifier. The
JSON payload (schema version 1.1) includes tenant/workflow identifiers, dataset
version hashes and field metadata, the primary policy and rules, policy
evaluation, approval history, associated executions, artifact references,
result summaries, log summaries, audit-chain verification, and audit-event IDs.
JSON/PDF/CSV exports have stored SHA-256 checksums; the verify endpoint re-hashes
them.

The evidence payload does not contain per-value read telemetry. For the proposed
adapter, `accessed_fields` means the explicit columns in the policy-checked
projection artifact, supported by the Analyze job's `requestedFields`, policy
rule, projection SQL, artifact hash, and the research agent's echoed input-field
list. It must not be described as lower-level database read tracing.

`denied_fields` can be derived from the contract and any `ANALYZE_FIELD_BLOCKED`
audit event, but successful projections do not emit one deny event per omitted
column. `tool_calls` and output-validation events are not native execution
fields; the research agent can return model tool calls, while missing output
validation evidence must remain explicitly missing rather than fabricated.

## CLI and SDK surface

The local CLI supports dataset listing, Analyze/Train job creation and running,
execution log/get operations, and evidence get/verify operations. It uses the
same API and environment variables `COMPEX_API_URL`, `COMPEX_API_KEY`,
`COMPEX_ORG_ID`, and `COMPEX_WORKSPACE_ID`. The Python and TypeScript SDKs expose
the same principal routes, but neither currently exposes dataset upload, policy
creation, approval decisions, generic execution creation, or artifact download;
the benchmark adapter therefore needs direct HTTP calls for those operations.

## Fail-closed integration conditions

The Compex adapter must return an error and preserve that error in raw JSONL if
any of the following occurs:

- health, authentication, organization, or workspace configuration is missing;
- the uploaded dataset/version hash or inferred fields do not match the case;
- policy creation or approval does not echo the intended contract;
- Analyze `requestedFields` differ from the exact allowed-field list;
- the projection or model run is not completed successfully;
- the model run receives any field outside the allowed list;
- the model identifier/seed/settings are changed or silently substituted;
- the model result, Compex run ID, artifact hash, evidence bundle, or evidence
  checksum is missing;
- evidence verification fails; or
- a secret-bearing model credential would need to be stored in execution
  environment metadata.

This mapping measures technical behavior only and makes no legal-compliance
claim.
