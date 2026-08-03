/* Invoke the platform's native governed Ollama adapter for one benchmark batch. */
'use strict';

const fs = require('node:fs');
const path = require('node:path');

function requireInput(value, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`${label} is required`);
  }
  return value;
}

async function main() {
  const platformRoot = path.resolve(process.env.COMPEX_PLATFORM_ROOT || '');
  if (!platformRoot || !fs.existsSync(path.join(platformRoot, 'services', 'runner'))) {
    throw new Error('COMPEX_PLATFORM_ROOT must name the local Compex repository');
  }
  const input = requireInput(JSON.parse(fs.readFileSync(0, 'utf8')), 'bridge input');
  const types = require(path.join(platformRoot, 'packages', 'types', 'dist', 'index.js'));
  const { OllamaModelAdapter } = require(path.join(
    platformRoot,
    'services',
    'runner',
    'dist',
    'local-models',
    'ollama-model.adapter.js',
  ));
  const manifestPath = path.resolve(platformRoot, String(input.manifestRelativePath || ''));
  const modelManifestRoot = path.resolve(platformRoot, 'docs', 'v2', 'model-manifests');
  if (manifestPath !== modelManifestRoot && !manifestPath.startsWith(`${modelManifestRoot}${path.sep}`)) {
    throw new Error('Model manifest escaped docs/v2/model-manifests');
  }
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const prompts = requireInput(input.prompts, 'prompts');
  const responseSchema = requireInput(input.responseSchema, 'responseSchema');
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
    keepAliveSeconds: 300,
    contextWindowTokens: input.contextWindowTokens,
  });

  let nativeRelease = null;
  if (input.nativeReleasePolicy) {
    const { evaluateNativeOutputRelease } = require(path.join(
      platformRoot,
      'services',
      'api',
      'dist',
      'confidential-execution',
      'release',
      'native-output-release.js',
    ));
    nativeRelease = evaluateNativeOutputRelease({
      contractHash: input.contractHash,
      evaluatedAt: new Date().toISOString(),
      artifact: {
        bytes: Buffer.from(result.quarantinedOutput, 'utf8'),
        artifactType: 'application/json',
        isModel: false,
      },
      policy: input.nativeReleasePolicy,
    });
  }
  process.stdout.write(JSON.stringify({ ...result, nativeRelease }));
}

main().catch((error) => {
  process.stderr.write(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
