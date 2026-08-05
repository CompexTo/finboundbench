/* Invoke Compex's native governed Ollama and output-release paths for v3. */
'use strict';

const fs = require('node:fs');
const path = require('node:path');

function requireObject(value, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`${label} is required`);
  }
  return value;
}

function confinedPath(root, relativePath, label) {
  const resolved = path.resolve(root, String(relativePath || ''));
  if (resolved !== root && !resolved.startsWith(`${root}${path.sep}`)) {
    throw new Error(`${label} escaped its allowed root`);
  }
  return resolved;
}

async function main() {
  const platformRoot = path.resolve(process.env.COMPEX_PLATFORM_ROOT || '');
  const researchRoot = path.resolve(process.env.FINBOUNDBENCH_ROOT || '');
  if (!fs.existsSync(path.join(platformRoot, 'services', 'runner'))) {
    throw new Error('COMPEX_PLATFORM_ROOT must name the local Compex repository');
  }
  if (!fs.existsSync(path.join(researchRoot, 'configs', 'v3'))) {
    throw new Error('FINBOUNDBENCH_ROOT must name the research repository');
  }

  const input = requireObject(JSON.parse(fs.readFileSync(0, 'utf8')), 'bridge input');
  const types = require(path.join(platformRoot, 'packages', 'types', 'dist', 'index.js'));
  const { OllamaModelAdapter } = require(path.join(
    platformRoot,
    'services',
    'runner',
    'dist',
    'local-models',
    'ollama-model.adapter.js',
  ));
  const manifestRoot = path.resolve(researchRoot, 'docs', 'v3', 'model-manifests');
  const manifestPath = confinedPath(
    manifestRoot,
    path.relative(manifestRoot, path.resolve(researchRoot, String(input.manifestRelativePath || ''))),
    'model manifest',
  );
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const prompts = requireObject(input.prompts, 'prompts');
  const responseSchema = requireObject(input.responseSchema, 'responseSchema');
  const releasePolicy = requireObject(input.nativeReleasePolicy, 'native release policy');
  const toolSchema = { defaultDeny: true, permissions: [] };
  const promptHashes = Object.fromEntries(
    Object.entries(prompts).map(([name, prompt]) => [name, types.sha256Hex(String(prompt))]),
  );
  const model = {
    provider: 'OLLAMA',
    exactRequestedModelId: manifest.pinnedModelId,
    effectiveModelId: manifest.pinnedModelId,
    modelVersion: manifest.modelRevision,
    modelIdImmutability: 'PINNED',
    endpoint: 'http://127.0.0.1:11434/api/generate',
    executionMode: 'LOCAL',
    workloadImageDigest: input.workloadImageDigest,
    temperature: 0,
    seed: input.seed,
    topP: 1,
    reasoningSetting: 'DISABLED',
    outputTokenLimit: input.outputTokenLimit,
    promptHashes,
    responseSchemaHash: types.hashCanonicalJson(responseSchema),
    toolSchemaHash: types.hashCanonicalJson(toolSchema),
    timeoutMs: input.timeoutMs,
    retryPolicy: {
      maxAttempts: 1,
      initialBackoffMs: 0,
      maximumBackoffMs: 0,
      retryableStatusCodes: [],
    },
    providerMetadataTimestamp: manifest.capturedAt,
  };
  const result = await new OllamaModelAdapter().invoke({
    contractHash: input.contractHash,
    model,
    manifest,
    selectedFields: input.selectedFields,
    records: input.records,
    prompts,
    responseSchema,
    toolSchema,
    keepAliveSeconds: input.keepAliveSeconds,
    contextWindowTokens: input.contextWindowTokens,
  });

  const { evaluateNativeOutputRelease } = require(path.join(
    platformRoot,
    'services',
    'api',
    'dist',
    'confidential-execution',
    'release',
    'native-output-release.js',
  ));
  const nativeRelease = evaluateNativeOutputRelease({
    contractHash: input.contractHash,
    evaluatedAt: new Date().toISOString(),
    artifact: {
      bytes: Buffer.from(result.quarantinedOutput, 'utf8'),
      artifactType: 'application/json',
      isModel: false,
    },
    policy: releasePolicy,
  });
  process.stdout.write(JSON.stringify({ ...result, nativeRelease }));
}

main().catch((error) => {
  process.stderr.write(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
