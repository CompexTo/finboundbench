PY ?= python
TEX ?= pdflatex
BIBTEX ?= bibtex

.PHONY: install build-agent generate doctor smoke pilot full evaluate assets test lint starter-kit reproduce paper proposal

install:
	$(PY) -m pip install -e .[dev]

build-agent:
	docker build -f containers/agent/Dockerfile -t purposebound-finance-agent:local .

generate:
	$(PY) -m purposebench.cli generate --cases-per-workflow 30

doctor:
	$(PY) scripts/doctor.py

smoke:
	$(PY) -m purposebench.cli run --config configs/experiment.yaml --limit 4

pilot:
	$(PY) -m purposebench.cli run --config configs/experiment.yaml --limit 40

full:
	$(PY) -m purposebench.cli run --config configs/experiment.yaml

evaluate:
	$(PY) -m purposebench.cli evaluate

assets:
	$(PY) -m purposebench.cli report

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check .

starter-kit:
	$(PY) -m competition.evaluator.run_baselines --out competition/results/leaderboard_dev.json

# No API key required: rebuild every statistic and check from the frozen raw
# events and manifests, regenerate figures, and compile paper + proposal PDFs.
reproduce:
	$(PY) scripts/run_v4_confirmatory_statistics.py --study primary
	$(PY) scripts/run_v4_confirmatory_statistics.py --study replication
	$(PY) scripts/run_v4_confirmatory_statistics.py --combine
	$(PY) scripts/run_v4_confirmatory_integrity.py
	$(PY) scripts/run_v4_verification_bundle.py
	$(PY) scripts/run_v4_independent_stats.py
	$(PY) scripts/run_v4_headline_figure.py
	$(PY) scripts/make_paper_figure_schematic.py
	$(MAKE) starter-kit
	$(MAKE) paper
	$(MAKE) proposal

paper:
	cd paper && $(TEX) -interaction=nonstopmode -halt-on-error main.tex
	cd paper && $(BIBTEX) main
	cd paper && $(TEX) -interaction=nonstopmode -halt-on-error main.tex
	cd paper && $(TEX) -interaction=nonstopmode -halt-on-error main.tex

proposal:
	cd competition && $(TEX) -interaction=nonstopmode -halt-on-error icaif26_finboundbench_proposal.tex
	cd competition && $(BIBTEX) icaif26_finboundbench_proposal
	cd competition && $(TEX) -interaction=nonstopmode -halt-on-error icaif26_finboundbench_proposal.tex
	cd competition && $(TEX) -interaction=nonstopmode -halt-on-error icaif26_finboundbench_proposal.tex
