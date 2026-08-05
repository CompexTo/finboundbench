/* Invoke OpenRouter through the platform's governed adapter for protocol v3. */
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { executeBridgeInput } = require('./governed_openrouter_bridge.cjs');

function requireObject(value, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`${label} is required`);
  }
  return value;
}

async function main() {
  const input = requireObject(JSON.parse(fs.readFileSync(0, 'utf8')), 'bridge input');
  const platformRoot = path.resolve(process.env.COMPEX_PLATFORM_ROOT || '');
  const researchRoot = path.resolve(process.env.FINBOUNDBENCH_ROOT || '');
  if (!fs.existsSync(path.join(platformRoot, 'services', 'runner'))) {
    throw new Error('COMPEX_PLATFORM_ROOT must name the local Compex repository');
  }
  if (!fs.existsSync(path.join(researchRoot, 'configs', 'v3'))) {
    throw new Error('FINBOUNDBENCH_ROOT must name the research repository');
  }
  const manifestRoot = path.resolve(researchRoot, 'docs', 'v3', 'model-manifests');
  const manifestPath = path.resolve(researchRoot, String(input.manifestRelativePath || ''));
  if (manifestPath !== manifestRoot && !manifestPath.startsWith(`${manifestRoot}${path.sep}`)) {
    throw new Error('model manifest escaped its allowed root');
  }
  const modelManifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const result = await executeBridgeInput(platformRoot, {
    contractHash: input.contractHash,
    modelManifest,
    workloadImageDigest: input.workloadImageDigest,
    seed: input.seed,
    outputTokenLimit: input.outputTokenLimit,
    timeoutMs: input.timeoutMs,
    selectedFields: input.selectedFields,
    records: input.records,
    prompts: input.prompts,
    responseSchema: input.responseSchema,
    nativeReleasePolicy: input.nativeReleasePolicy,
    maximumAuthorizedCostEur: input.maximumAuthorizedCostEur,
  });
  process.stdout.write(JSON.stringify(result));
}

function reportFailure(error) {
  if (error && typeof error === 'object' && error.diagnostic) {
    process.stderr.write(`PROVIDER_SAFE_ERROR:${JSON.stringify(error.diagnostic)}`);
    process.exitCode = 1;
    return;
  }
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(message.includes('OPENROUTER_API_KEY') ? 'OPENROUTER_API_KEY_NOT_CONFIGURED' : message);
  process.exitCode = 1;
}

main().catch(reportFailure);
