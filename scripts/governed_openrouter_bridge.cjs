/* Invoke OpenRouter only through the platform's governed commercial adapter. */
'use strict';

const fs = require('node:fs');
const path = require('node:path');

const KEY_NAME = 'OPENROUTER_API_KEY';
const REFERENCE_ID = 'openrouter-benchmark-key';

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

async function main() {
  const platformRoot = path.resolve(process.env.COMPEX_PLATFORM_ROOT || '');
  if (!platformRoot || !fs.existsSync(path.join(platformRoot, 'services', 'runner'))) {
    throw new Error('COMPEX_PLATFORM_ROOT must name the local Compex repository');
  }
  const input = requireInput(JSON.parse(fs.readFileSync(0, 'utf8')), 'bridge input');
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
    if (
      manifest.provider !== 'OPENROUTER'
      || manifest.endpoint !== 'https://openrouter.ai/api/v1/chat/completions'
      || manifest.modelVersion !== manifest.modelId
      || /(?:^|[-_.:/@])(latest|current|default|stable|preview|auto)(?:$|[-_.:/@])/i
        .test(String(manifest.modelId || ''))
      || types.hashCanonicalJson(manifestMaterial) !== manifest.manifestHash
    ) {
      throw new Error('OpenRouter model manifest identity or integrity changed');
    }
    const supportedParameters = Array.isArray(manifest.supportedParameters)
      ? manifest.supportedParameters.map(String)
      : [];
    const providerOnly = Array.isArray(manifest.providerRouting?.only)
      ? manifest.providerRouting.only.map(String)
      : [];
    const reasoningDisableStrategy = manifest.reasoningDisableStrategy || 'ENABLED_FALSE';
    const reasoningSetting = manifest.reasoningSetting || 'DISABLED';
    if (
      providerOnly.length !== 1
      || manifest.providerRouting?.allowFallbacks !== false
      || manifest.providerRouting?.zeroDataRetention !== true
    ) {
      throw new Error('OpenRouter model manifest must pin one ZDR provider route');
    }
    if (!['ENABLED_FALSE', 'EFFORT_NONE', 'OMIT'].includes(reasoningDisableStrategy)) {
      throw new Error('OpenRouter reasoning disable strategy is invalid');
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
      !supportedParameters.includes('max_tokens')
      && !supportedParameters.includes('max_completion_tokens')
    ) {
      throw new Error('OpenRouter model does not support an output-token parameter');
    }
    const promptRate = Number(manifest.budgetCeilingUsdPerToken?.prompt);
    const completionRate = Number(manifest.budgetCeilingUsdPerToken?.completion);
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
      modelVersion: manifest.modelVersion,
      modelIdImmutability: 'PINNED',
      endpoint: manifest.endpoint,
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
      providerMetadataTimestamp: manifest.capturedAt,
    };
    const costCalculator = {
      calculate: ({ modelId, tokens }) => {
        if (modelId !== manifest.modelId) {
          return {
            amount: null,
            currency: 'USD',
            amountEur: null,
            pricingSource: 'MODEL_SUBSTITUTION',
            pricingTimestamp: manifest.capturedAt,
          };
        }
        const amount = tokens.inputTokens * promptRate
          + tokens.outputTokens * completionRate;
        return {
          amount,
          currency: 'USD',
          amountEur: amount,
          pricingSource: 'RESEARCH_MANIFEST_CONSERVATIVE_USD_EUR_PARITY_CEILING',
          pricingTimestamp: manifest.capturedAt,
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
      reasoningDisableStrategy,
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
    process.stdout.write(JSON.stringify({ ...result, nativeRelease }));
  } finally {
    if (keyState.loadedFromFile) {
      if (keyState.previousValue === undefined) delete process.env[KEY_NAME];
      else process.env[KEY_NAME] = keyState.previousValue;
    }
  }
}

main().catch((error) => {
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(message.includes(KEY_NAME) ? 'OPENROUTER_API_KEY_NOT_CONFIGURED' : message);
  process.exitCode = 1;
});
