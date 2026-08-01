.PHONY: install build-agent generate doctor smoke pilot full evaluate assets test lint

install:
	python -m pip install -e .[dev]

build-agent:
	docker build -f containers/agent/Dockerfile -t purposebound-finance-agent:local .

generate:
	python -m purposebench.cli generate --cases-per-workflow 30

doctor:
	python scripts/doctor.py

smoke:
	python -m purposebench.cli run --config configs/experiment.yaml --limit 4

pilot:
	python -m purposebench.cli run --config configs/experiment.yaml --limit 40

full:
	python -m purposebench.cli run --config configs/experiment.yaml

evaluate:
	python -m purposebench.cli evaluate

assets:
	python -m purposebench.cli report

test:
	pytest -q

lint:
	ruff check .
