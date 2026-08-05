import yaml
from pathlib import Path
config = yaml.safe_load(Path('configs/v3/openrouter-model-admission-v3.yaml').read_text(encoding='utf-8'))
print('R0 Admission Config:')
print(f'  admission_id: {config["admission_id"]}')
print(f'  models: {len(config["models"])}')
for m in config['models']:
    print(f'    {m["lane_id"]}: model={m["expected_model_id"]}, route={m["expected_upstream_route"]}')
    print(f'      manifest_hash: {m["expected_manifest_hash"][:16]}...')
