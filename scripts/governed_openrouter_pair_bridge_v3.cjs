/* Invoke OpenRouter through the platform's governed commercial adapter for the
 * v3 one-pair B0/P3 validation gate.
 *
 * This bridge is a copy of the frozen `governed_openrouter_bridge.cjs`
 * (commit 514323d) plus one additive capability: it forwards
 * `projectionClassification` into the adapter invocation so the platform
 * evidence records the approved/prohibited partition and per-partition
 * payload hashes. The frozen bridge is intentionally left unchanged so the R0
 * admission freeze keeps verifying; this file pins its own digest.
 */
'use strict';

const fs = require('node:fs');
const path = require('node:path');

const KEY_NAME = 'OPENROUTER_API_KEY';
const REFERENCE_ID = 'openrouter-benchmark-key';
const OPENROUTER_ENDPOINT = 'https://openrouter.ai/api/v1/chat/completions';

function requireInput(value, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`${label} is required`);
  }
  return value;
}

function loadResearchKey(platformRoot) {
  const environmentPath = path.join(platformRoot, '.env.research.local');
  if (!fs.existsSync(environmentPath)) {
    if (process.env[KEY_NAME]) return { loadedFromFile: false, previousValue: undefined };
    throw new Error('OPENROUTER_API_KEY_NOT_CONFIGURED');
  }
  const matches = fs.readFileSync(environmentPath, 'utf8')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith('#'))
    .filter((line) => line.startsWith(`${KEY_NAME}=`));
  if (matches.length !== 1) throw new Error('OPENROUTER_API_KEY_NOT_CONFIGURED');
  let value = matches[0].slice(KEY_NAME.length + 1).trim();
  if (
    value.length >= 2
    && ((value.startsWith('"') && value.endsWith('"'))
      || (value.startsWith("'") && value.endsWith("'")))
  ) {
    value = value.slice(1, -1);
  }
  if (!value || /[\r\n\0]/.test(value)) {
    throw new Error('OPENROUTER_API_KEY_NOT_CONFIGURED');
  }
  const previousValue = process.env[KEY_NAME];
  process.env[KEY_NAME] = value;
  return { loadedFromFile: true, previousValue };
}

async function executeBridgeInput(platformRootInput, inputValue, adapterOverrides = {}) {
  const platformRoot = path.resolve(platformRootInput || '');
  if (!platformRoot || !fs.existsSync(path.join(platformRoot, 'services', 'runner'))) {
    throw new Error('COMPEX_PLATFORM_ROOT must name the local Compex repository');
  }
  const input = requireInput(inputValue, 'bridge input');
  const keyState = loadResearchKey(platformRoot);
  try {
    const types = require(path.join(platformRoot, 'packages', 'types', 'dist', 'index.js'));
    const {
      OpenRouterModelAdapter,
    } = require(path.join(
      platformRoot,
      'services',
      'runner',
      'dist',
      'providers',
      'openrouter.adapter.js',
    ));
    const {
      createSecretReference,
      EnvironmentReferenceSecretProvider,
      SecretProviderRegistry,
    } = require(path.join(
      platformRoot,
      'services',
      'runner',
      'dist',
      'secrets',
      'secret-providers.js',
    ));
    const manifest = requireInput(input.modelManifest, 'model manifest');
    const manifestMaterial = { ...manifest };
    delete manifestMaterial.manifestHash;
    const gateway = manifest.gateway || manifest.provider;
    const endpoint = manifest.endpoint || OPENROUTER_ENDPOINT;
    const modelVersion = manifest.modelVersion || manifest.modelId;
    const canonicalSlug = manifest.canonicalCatalogSlug || manifest.canonicalSlug;
    if (
      gateway !== 'OPENROUTER'
      || endpoint !== OPENROUTER_ENDPOINT
      || modelVersion !== manifest.modelId
      || typeof canonicalSlug !== 'string'
      || /(?:^|[-_.:/@])(latest|current|default|stable|preview|auto)(?:$|[-_.:/@])/i
        .test(String(manifest.modelId || ''))
      || types.hashCanonicalJson(manifestMaterial) !== manifest.manifestHash
    ) {
      throw new Error('OpenRouter model manifest identity or integrity changed');
    }
    const supportedParameters = Array.isArray(manifest.supportedParameters)
      ? manifest.supportedParameters.map(String)
      : [];
    const providerOnly = typeof manifest.upstreamRoute === 'string'
      ? [manifest.upstreamRoute]
      : Array.isArray(manifest.providerRouting?.only)
        ? manifest.providerRouting.only.map(String)
        : [];
    const fallbackAllowed = manifest.fallbackAllowed === undefined
      ? manifest.providerRouting?.allowFallbacks
      : manifest.fallbackAllowed;
    const zeroDataRetentionRequired = manifest.zeroDataRetentionRequired === undefined
      ? manifest.providerRouting?.zeroDataRetention
      : manifest.zeroDataRetentionRequired;
    const reasoningDisableStrategy = manifest.reasoningDisableStrategy || 'ENABLED_FALSE';
    const reasoningConfiguration = manifest.reasoningConfiguration;
    const reasoningStrategy = reasoningConfiguration?.reasoningStrategy;
    const reasoningEffort = reasoningConfiguration?.reasoningEffort;
    const reasoningEnabled = reasoningConfiguration?.reasoningEnabled;
    const reasoningSetting = manifest.reasoningSetting
      || (reasoningStrategy === 'EFFORT' ? String(reasoningEffort).toUpperCase() : 'DISABLED');
    const tokenParameter = manifest.tokenParameter
      || (supportedParameters.includes('max_tokens')
        ? 'max_tokens'
        : 'max_completion_tokens');
    if (
      providerOnly.length !== 1
      || fallbackAllowed !== false
      || zeroDataRetentionRequired !== true
      || (manifest.providerDataCollectionAllowed !== undefined
        && manifest.providerDataCollectionAllowed !== false)
    ) {
      throw new Error('OpenRouter model manifest must pin one ZDR provider route');
    }
    if (
      manifest.structuredOutputMode !== undefined
      && manifest.structuredOutputMode !== 'JSON_SCHEMA_STRICT'
    ) {
      throw new Error('OpenRouter structured-output method is invalid');
    }
    if (!['ENABLED_FALSE', 'EFFORT_NONE', 'OMIT'].includes(reasoningDisableStrategy)) {
      throw new Error('OpenRouter reasoning disable strategy is invalid');
    }
    if (
      reasoningStrategy !== undefined
      && !['OMIT', 'EFFORT', 'ENABLED_FLAG'].includes(reasoningStrategy)
    ) {
      throw new Error('OpenRouter reasoning strategy is invalid');
    }
    if (!['DISABLED', 'LOW', 'MEDIUM', 'HIGH'].includes(reasoningSetting)) {
      throw new Error('OpenRouter reasoning setting is invalid');
    }
    for (const required of ['response_format', 'structured_outputs']) {
      if (!supportedParameters.includes(required)) {
        throw new Error(`OpenRouter model does not support required parameter: ${required}`);
      }
    }
    if (
      !['max_tokens', 'max_completion_tokens'].includes(tokenParameter)
      || !supportedParameters.includes(tokenParameter)
    ) {
      throw new Error('OpenRouter model does not support an output-token parameter');
    }
    if (
      manifest.maximumOutputTokens !== undefined
      && (
        !Number.isSafeInteger(manifest.maximumOutputTokens)
        || input.outputTokenLimit > manifest.maximumOutputTokens
      )
    ) {
      throw new Error('OpenRouter output-token limit exceeds the manifest');
    }
    if (
      manifest.contextWindow !== undefined
      && (!Number.isSafeInteger(manifest.contextWindow) || manifest.contextWindow < 1)
    ) {
      throw new Error('OpenRouter context window is invalid');
    }
    for (const hashField of ['catalogMetadataHash', 'routeMetadataHash']) {
      if (manifest[hashField] !== undefined && !/^[a-f0-9]{64}$/.test(manifest[hashField])) {
        throw new Error(`OpenRouter ${hashField} is invalid`);
      }
    }
    const promptRate = Number(
      manifest.inputPriceCeiling ?? manifest.budgetCeilingUsdPerToken?.prompt,
    );
    const completionRate = Number(
      manifest.outputPriceCeiling ?? manifest.budgetCeilingUsdPerToken?.completion,
    );
    if (
      !Number.isFinite(promptRate)
      || promptRate < 0
      || !Number.isFinite(completionRate)
      || completionRate < 0
    ) {
      throw new Error('OpenRouter model manifest pricing is invalid');
    }
    const prompts = requireInput(input.prompts, 'prompts');
    const responseSchema = requireInput(input.responseSchema, 'responseSchema');
    const classification = input.projectionClassification;
    if (classification !== undefined) {
      const approved = Array.isArray(classification.approvedFields)
        ? classification.approvedFields.map(String) : [];
      const prohibited = Array.isArray(classification.prohibitedFields)
        ? classification.prohibitedFields.map(String) : [];
      const combined = [...approved, ...prohibited];
      if (
        combined.length === 0
        || new Set(combined).size !== combined.length
        || JSON.stringify([...combined].sort()) !== JSON.stringify([...input.selectedFields].sort())
      ) {
        throw new Error('Projection field classification must partition the transmitted field manifest');
      }
    }
    const toolSchema = { defaultDeny: true, permissions: [] };
    const promptHashes = Object.fromEntries(
      Object.entries(prompts).map(([name, prompt]) => [name, types.sha256Hex(String(prompt))]),
    );
    const secretReference = createSecretReference({
      referenceId: REFERENCE_ID,
      provider: 'ENVIRONMENT_REFERENCE',
      version: 'openrouter-benchmark-v1',
      scopes: ['openrouter:model:invoke'],
      expiresAt: null,
    });
    const secrets = new SecretProviderRegistry([
      new EnvironmentReferenceSecretProvider({ [REFERENCE_ID]: KEY_NAME }),
    ]);
    const model = {
      provider: 'OPENROUTER',
      exactRequestedModelId: manifest.modelId,
      effectiveModelId: manifest.modelId,
      modelVersion,
      modelIdImmutability: 'PINNED',
      endpoint,
      executionMode: 'REMOTE',
      workloadImageDigest: input.workloadImageDigest,
      temperature: 0,
      ...(supportedParameters.includes('seed') ? { seed: input.seed } : {}),
      topP: 1,
      reasoningSetting,
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
      providerMetadataTimestamp: manifest.endpointMetadataCapturedAt || manifest.capturedAt,
    };
    const costCalculator = {
      calculate: ({ modelId, tokens }) => {
        if (modelId !== manifest.modelId) {
          return {
            amount: null,
            currency: 'USD',
            amountEur: null,
            pricingSource: 'MODEL_SUBSTITUTION',
            pricingTimestamp: manifest.endpointMetadataCapturedAt || manifest.capturedAt,
          };
        }
        const amount = tokens.inputTokens * promptRate
          + tokens.outputTokens * completionRate;
        return {
          amount,
          currency: 'USD',
          amountEur: amount,
          pricingSource: 'RESEARCH_MANIFEST_CONSERVATIVE_USD_EUR_PARITY_CEILING',
          pricingTimestamp: manifest.endpointMetadataCapturedAt || manifest.capturedAt,
        };
      },
    };
    const { evaluateNativeOutputRelease } = require(path.join(
      platformRoot,
      'services',
      'api',
      'dist',
      'confidential-execution',
      'release',
      'native-output-release.js',
    ));
    const result = await new OpenRouterModelAdapter({
      secrets,
      costCalculator,
      supportedParameters,
      providerOnly,
      tokenParameter,
      ...(reasoningStrategy === undefined ? {} : { reasoningStrategy }),
      ...(reasoningEffort === undefined ? {} : { reasoningEffort }),
      ...(reasoningEnabled === undefined ? {} : { reasoningEnabled }),
      reasoningDisableStrategy,
      ...(adapterOverrides.transport === undefined
        ? {}
        : { transport: adapterOverrides.transport }),
    }).invoke({
      contractHash: input.contractHash,
      model,
      selectedFields: input.selectedFields,
      records: input.records,
      prompts,
      responseSchema,
      toolSchema,
      pseudonymized: true,
      secretReference,
      ...(classification === undefined
        ? {}
        : { projectionClassification: classification }),
      networkPolicy: {
        defaultDeny: true,
        mode: 'ALLOWLIST',
        destinations: [{
          host: 'openrouter.ai',
          ports: [443],
          httpMethods: ['POST'],
          maximumCalls: 1,
          maximumBytes: 8 * 1024 * 1024,
          protectedValuesAllowed: true,
        }],
      },
      maximumAuthorizedCostEur: input.maximumAuthorizedCostEur,
    });

    const nativeRelease = evaluateNativeOutputRelease({
      contractHash: input.contractHash,
      evaluatedAt: new Date().toISOString(),
      artifact: {
        bytes: Buffer.from(result.quarantinedOutput, 'utf8'),
        artifactType: 'application/json',
        isModel: false,
      },
      policy: input.nativeReleasePolicy,
    });
    let governedActionBatch;
    if (
      input.actionPolicy !== undefined
      || input.actionPolicyHash !== undefined
      || input.expectedRecordCount !== undefined
    ) {
      if (nativeRelease.allowed !== true) {
        throw new Error('Native release denied before deterministic action mapping');
      }
      const { evaluateDeterministicActionBatch } = require(path.join(
        platformRoot,
        'services',
        'api',
        'dist',
        'confidential-execution',
        'action-policy',
        'deterministic-action-policy.js',
      ));
      governedActionBatch = evaluateDeterministicActionBatch({
        modelOutput: JSON.parse(result.quarantinedOutput),
        expectedRecordCount: input.expectedRecordCount,
        policy: input.actionPolicy,
        expectedPolicyHash: input.actionPolicyHash,
      });
    }
    return {
      ...result,
      nativeRelease,
      ...(governedActionBatch === undefined ? {} : { governedActionBatch }),
    };
  } finally {
    if (keyState.loadedFromFile) {
      if (keyState.previousValue === undefined) delete process.env[KEY_NAME];
      else process.env[KEY_NAME] = keyState.previousValue;
    }
  }
}

async function main() {
  const input = requireInput(JSON.parse(fs.readFileSync(0, 'utf8')), 'bridge input');
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
  const result = await executeBridgeInput(platformRoot, { ...input, modelManifest });
  process.stdout.write(JSON.stringify(result));
}

function reportFailure(error) {
  if (error && typeof error === 'object' && error.diagnostic) {
    process.stderr.write(`PROVIDER_SAFE_ERROR:${JSON.stringify(error.diagnostic)}`);
    process.exitCode = 1;
    return;
  }
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(message.includes(KEY_NAME) ? 'OPENROUTER_API_KEY_NOT_CONFIGURED' : message);
  process.exitCode = 1;
}

module.exports = { executeBridgeInput };

if (require.main === module) main().catch(reportFailure);
