/* Reproducible live gate for the local Compex hardened Docker backend. */
'use strict';

const path = require('node:path');
const { createRequire } = require('node:module');

const platformRoot = path.resolve(
  process.env.COMPEX_PLATFORM_ROOT || path.join(__dirname, '..', '..', '..'),
);
const runnerRequire = createRequire(
  path.join(platformRoot, 'services', 'runner', 'package.json'),
);
const { Client } = runnerRequire('minio');
const {
  approvePurposeBoundExecutionContract,
  canonicalJson,
  createPurposeBoundExecutionContract,
  hashCanonicalJson,
  sha256Hex,
} = require(path.join(platformRoot, 'packages', 'types', 'dist', 'index.js'));

const requiredEnvironment = [
  'GATE_IMAGE_DIGEST',
  'MINIO_ACCESS_KEY',
  'MINIO_SECRET_KEY',
  'RUNNER_INTERNAL_TOKEN',
];
for (const name of requiredEnvironment) {
  if (!process.env[name]) throw new Error(`${name} is required`);
}

const executionId = process.env.GATE_EXECUTION_ID || 'execution-live-local-v2-002';
const imageDigest = process.env.GATE_IMAGE_DIGEST;
const toolPermissions = { defaultDeny: true, permissions: [] };
const responseSchemaHash = sha256Hex('governed-gate-response-schema');
const contractInput = {
  contractId: `contract-${executionId}`,
  organization: { id: 'org-research' },
  workspace: { id: 'workspace-research' },
  dataOwner: { id: 'owner-research' },
  processor: { id: 'processor-compex' },
  purpose: { id: 'purpose-governed-gate' },
  purposeVersion: 'purpose-v2',
  dataset: { id: 'dataset-synthetic-gate' },
  datasetVersion: { id: 'dataset-version-live-001' },
  datasetHash: sha256Hex('synthetic-gate-dataset-v1'),
  policy: { id: 'policy-live-fields' },
  policyVersion: 'policy-v2',
  policyHash: sha256Hex('policy-live-json'),
  allowedFields: ['case_id', 'loan_amount', 'debt_to_income_ratio'],
  deniedFields: ['internal_fraud_note'],
  approvedRowSelector: {
    kind: 'ALL_ROWS',
    selectorId: 'selector-all-rows',
    selectorVersion: 'selector-v2',
    canonicalPredicateHash: sha256Hex('all-rows'),
  },
  workloadType: 'ANALYZE',
  workloadImage: 'purposebound-finance-v2-gate:local',
  workloadImageDigest: imageDigest,
  modelExecution: {
    provider: 'OLLAMA',
    exactRequestedModelId:
      'qwen3:4b@sha256:359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7',
    effectiveModelId:
      'qwen3:4b@sha256:359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7',
    modelVersion:
      'sha256:359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7',
    modelIdImmutability: 'PINNED',
    endpoint: 'http://127.0.0.1:11434/api/generate',
    executionMode: 'LOCAL',
    workloadImageDigest: imageDigest,
    temperature: 0,
    seed: 20260802,
    topP: 1,
    reasoningSetting: 'DISABLED',
    outputTokenLimit: 32,
    promptHashes: { system: sha256Hex('governed-gate-system') },
    responseSchemaHash,
    toolSchemaHash: hashCanonicalJson(toolPermissions),
    timeoutMs: 60000,
    retryPolicy: {
      maxAttempts: 1,
      initialBackoffMs: 0,
      maximumBackoffMs: 0,
      retryableStatusCodes: [],
    },
    providerMetadataTimestamp: '2026-08-02T15:55:00.000Z',
  },
  privacy: null,
  outputRelease: {
    responseSchemaHash,
    requiredFields: ['status'],
    permittedDecisionVocabulary: ['APPROVED_DATA_AVAILABLE'],
    numericBounds: [],
    maximumOutputBytes: 16384,
    prohibitedExactValueHashes: [],
    prohibitedFieldNames: ['internal_fraud_note'],
    piiPatternDetectionRequired: true,
    minimumCohortSize: 1,
    permittedArtifactTypes: ['application/json'],
    modelReleaseAllowed: false,
    humanApprovalRequired: false,
    privacyBudgetRequired: false,
    requiredValidatorIds: ['json-schema-v1'],
  },
  toolPermissions,
  networkPolicy: { defaultDeny: true, mode: 'DISABLED', destinations: [] },
  secretReferences: [],
  retentionPolicy: {
    inputRetentionDays: 0,
    outputRetentionDays: 7,
    evidenceRetentionDays: 365,
    cleanupDeadlineHours: 1,
    cleanupMode: 'IMMEDIATE',
    deleteInputsAfterExecution: true,
    preserveAccountabilityEvidence: true,
  },
  approvalExpiresAt: '2026-09-01T00:00:00.000Z',
  executionBackend: 'LOCAL_HARDENED_DOCKER',
  createdAt: '2026-08-02T15:56:00.000Z',
};

const contract = approvePurposeBoundExecutionContract(
  createPurposeBoundExecutionContract(contractInput),
  {
    approvalId: `approval-${executionId}`,
    approvedBy: 'reviewer-dpo-001',
    approvedAt: '2026-08-02T15:57:00.000Z',
  },
);
const projection = {
  contractHash: contract.contractHash,
  selectedFields: [...contract.allowedFields],
  deniedFields: [...contract.deniedFields],
  records: [
    {
      case_id: 'pseudo-001',
      loan_amount: 125000,
      debt_to_income_ratio: 0.31,
    },
  ],
};
const body = Buffer.from(canonicalJson(projection));
const projectionHash = sha256Hex(body);
const bucket = 'compex-projections';
const key = `protocol-v2-local/${executionId}/projection.json`;
const minio = new Client({
  endPoint: process.env.MINIO_ENDPOINT || '127.0.0.1',
  port: Number(process.env.MINIO_PORT || 9000),
  useSSL: process.env.MINIO_USE_SSL === 'true',
  accessKey: process.env.MINIO_ACCESS_KEY,
  secretKey: process.env.MINIO_SECRET_KEY,
});

async function runnerRequest(requestPath, options = {}) {
  const response = await fetch(
    `${process.env.RUNNER_URL || 'http://127.0.0.1:4003'}${requestPath}`,
    {
      ...options,
      headers: {
        'content-type': 'application/json',
        'x-compex-runner-token': process.env.RUNNER_INTERNAL_TOKEN,
        ...(options.headers || {}),
      },
    },
  );
  const data = await response.json();
  if (!response.ok) throw new Error(`runner HTTP ${response.status}: ${JSON.stringify(data)}`);
  return data;
}

async function main() {
  if (!(await minio.bucketExists(bucket))) await minio.makeBucket(bucket);
  await minio.putObject(bucket, key, body, body.length, {
    'Content-Type': 'application/json',
    'x-amz-meta-sha256': projectionHash,
  });
  const context = {
    executionId,
    projection: {
      contractHash: contract.contractHash,
      datasetId: contract.dataset.id,
      datasetVersionId: contract.datasetVersion.id,
      datasetHash: contract.datasetHash,
      policyId: contract.policy.id,
      policyVersion: contract.policyVersion,
      policyHash: contract.policyHash,
      approvalId: contract.approval.approvalId,
      projectionArtifactHash: projectionHash,
      input: {
        bucket,
        key,
        mountPath: '/input/projection.json',
        expectedSha256: projectionHash,
      },
    },
    resourceLimits: {
      timeoutSec: 60,
      cpuLimit: 0.5,
      memoryLimitMb: 256,
      pidsLimit: 32,
    },
  };
  const accepted = await runnerRequest('/governed-executions', {
    method: 'POST',
    body: JSON.stringify({ contract, context }),
  });
  let evidence;
  for (let attempt = 0; attempt < 120; attempt += 1) {
    evidence = await runnerRequest(`/governed-executions/${executionId}/evidence`);
    if (
      ['completed', 'failed', 'cancelled', 'timeout'].includes(evidence.status) &&
      evidence.cleanupStatus !== 'PENDING'
    ) {
      break;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  process.stdout.write(
    JSON.stringify(
      {
        schemaVersion: 'purposebound-finance.local-hardened-docker-gate.v2',
        status: evidence.status === 'completed' ? 'passed' : 'failed',
        accepted,
        contractHash: contract.contractHash,
        projectionHash,
        evidence,
      },
      null,
      2,
    ),
  );
  if (evidence.status !== 'completed') process.exitCode = 1;
}

main().catch((error) => {
  process.stderr.write(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
