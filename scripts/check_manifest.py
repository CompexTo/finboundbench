import json
from pathlib import Path
from purposebench.utils import sha256_json

m = json.loads(Path('docs/v3/model-manifests/openrouter-moonshotai-kimi-k3.json').read_text(encoding='utf-8'))
material = {k: v for k, v in m.items() if k != 'manifestHash'}
stored = m['manifestHash']
computed = sha256_json(material)
print(f'Stored: {stored}')
print(f'Computed: {computed}')
print(f'Match: {stored == computed}')
