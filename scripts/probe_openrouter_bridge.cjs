/* Exercise the exact OpenRouter bridge contract with a local fake transport. */
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { executeBridgeInput } = require('./governed_openrouter_bridge.cjs');

async function main() {
  const platformRoot = path.resolve(process.env.COMPEX_PLATFORM_ROOT || '');
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  const results = Array.from({ length: input.expectedRecordCount }, (_, index) => ({
    index,
    normalized_risk_score: index % 2 === 0 ? 0.25 : 0.75,
    recommendation: 'NO_RECOMMENDATION',
    factors: [],
  }));
  const transport = {
    requests: [],
    async send(request) {
      this.requests.push(request);
      return {
        status: 200,
        headers: { 'x-openrouter-request-id': 'fake-local-probe' },
        latencyMs: 1,
        body: JSON.stringify({
          model: input.modelManifest.modelId,
          choices: [{ message: { content: JSON.stringify({ results }) } }],
          usage: { prompt_tokens: 10, completion_tokens: 10, cost: 0.0001 },
        }),
      };
    },
  };
  const result = await executeBridgeInput(platformRoot, input, { transport });
  if (
    transport.requests.length !== 1
    || result.nativeRelease?.allowed !== true
    || result.governedActionBatch?.recordCount !== input.expectedRecordCount
  ) {
    throw new Error('LOCAL_FAKE_OPENROUTER_CONTRACT_PROBE_FAILED');
  }
  process.stdout.write(JSON.stringify({
    status: 'PASSED',
    fakeTransportCalls: transport.requests.length,
    nativeReleaseAllowed: result.nativeRelease.allowed,
    governedRecordCount: result.governedActionBatch.recordCount,
    externalProviderCalls: 0,
  }));
}

main().catch((error) => {
  process.stderr.write(error instanceof Error ? error.message : 'LOCAL_FAKE_PROBE_FAILED');
  process.exitCode = 1;
});
