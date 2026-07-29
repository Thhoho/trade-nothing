# Trade Nothing — Autonomous Investment Agent & Maintenance Automation
# Dynamically extract version from centralized version.py
ROOT_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
VERSION := $(shell python3 -c "import sys; sys.path.insert(0, '$(ROOT_DIR)/scripts'); from version import __version__; print(__version__)")

DEV_DIR ?= $(if $(wildcard $(HOME)/Documents/trade-nothing/SKILL.md),$(HOME)/Documents/trade-nothing,$(ROOT_DIR))
GEMINI_SKILL_DIR ?= $(HOME)/.gemini/skills/trade-nothing
CODEX_SKILL_DIR ?= $(HOME)/.codex/skills/trade-nothing
SKILL_DIRS := $(GEMINI_SKILL_DIR) $(CODEX_SKILL_DIR)
ROOT_FILES := SKILL.md README.md README_zh.md CONTRIBUTING.md LICENSE requirements.txt Makefile

.PHONY: help install pull status test test-legacy test-live clean server portfolio verify-version

help:
	@echo "=================================================================="
	@echo "Trade Nothing v$(VERSION) Autonomous Agent Maintenance Suite"
	@echo "=================================================================="
	@echo "make install       : Sync controlled source files to Gemini and Codex skills"
	@echo "make status        : Check Git status and verify directory alignment"
	@echo "make server        : Start the Autonomous REST Daemon Server (Port 8000)"
	@echo "make portfolio     : Print current multi-currency transaction ledger"
	@echo "make verify-version: Check version consistency across documentation"
	@echo "make test          : Run current deterministic safety and regression gates"
	@echo "make test-legacy   : Run legacy LFI/Kelly compatibility tests"
	@echo "make test-live     : Run non-gating live provider diagnostics"
	@echo "make clean         : Clean Python cache files and temp state files"
	@echo "=================================================================="

install:
	@echo "🚀 Syncing controlled source files to Gemini and Codex..."
	@for dst in $(SKILL_DIRS); do \
		mkdir -p $$dst/scripts $$dst/agents $$dst/references $$dst/docs $$dst/benchmarks $$dst/assets; \
		rsync -a --include='*.py' --exclude='*' $(DEV_DIR)/scripts/ $$dst/scripts/; \
		rsync -a $(DEV_DIR)/agents/ $$dst/agents/; \
		rsync -a $(DEV_DIR)/references/ $$dst/references/; \
		rsync -a --include='*.md' --exclude='*' $(DEV_DIR)/docs/ $$dst/docs/; \
		rsync -a --delete $(DEV_DIR)/benchmarks/ $$dst/benchmarks/; \
		rsync -a --delete --exclude='.DS_Store' $(DEV_DIR)/assets/ $$dst/assets/; \
		for f in $(ROOT_FILES); do cp $(DEV_DIR)/$$f $$dst/$$f; done; \
	done
	@python3 $(DEV_DIR)/scripts/check_source_sync.py --source $(DEV_DIR) --targets $(SKILL_DIRS)
	@echo "✅ Install complete. Runtime JSON/state/scratch files were not touched."

pull:
	@echo "Pull is intentionally disabled: $(DEV_DIR) is the single source of truth."
	@echo "Copy an intentional runtime change into DEV_DIR manually, review it, then run make install."

status:
	@python3 $(DEV_DIR)/scripts/check_source_sync.py --source $(DEV_DIR) --targets $(SKILL_DIRS)

verify-version:
	@echo "🔍 Running version consistency audit..."
	python3 $(DEV_DIR)/scripts/version.py

test:
	@echo "🧪 Running current deterministic safety and regression gates..."
	PYTHONDONTWRITEBYTECODE=1 python3 $(ROOT_DIR)/scripts/test_v2_engine.py
	PYTHONDONTWRITEBYTECODE=1 python3 $(ROOT_DIR)/scripts/test_landscape_engine.py
	PYTHONDONTWRITEBYTECODE=1 python3 $(ROOT_DIR)/scripts/test_framing_feasibility.py
	PYTHONDONTWRITEBYTECODE=1 python3 $(ROOT_DIR)/scripts/test_hypothesis_engine.py
	PYTHONDONTWRITEBYTECODE=1 python3 $(ROOT_DIR)/scripts/test_hypothesis_integration.py
	PYTHONDONTWRITEBYTECODE=1 python3 $(ROOT_DIR)/scripts/test_evidence_exhaustion_convergence.py
	PYTHONDONTWRITEBYTECODE=1 python3 $(ROOT_DIR)/scripts/test_opportunity_engine.py
	PYTHONDONTWRITEBYTECODE=1 python3 $(ROOT_DIR)/scripts/test_candidate_gap_engine.py
	PYTHONDONTWRITEBYTECODE=1 python3 $(ROOT_DIR)/scripts/test_research_output.py
	PYTHONDONTWRITEBYTECODE=1 python3 $(ROOT_DIR)/scripts/test_candidate_screen_engine.py
	PYTHONDONTWRITEBYTECODE=1 python3 $(ROOT_DIR)/scripts/test_claim_verification_engine.py
	PYTHONDONTWRITEBYTECODE=1 python3 $(ROOT_DIR)/scripts/test_benchmark_current.py
	PYTHONDONTWRITEBYTECODE=1 python3 $(ROOT_DIR)/scripts/test_benchmark_harness.py
	PYTHONDONTWRITEBYTECODE=1 python3 $(ROOT_DIR)/scripts/test_discovery_benchmark_harness.py
	PYTHONDONTWRITEBYTECODE=1 python3 $(ROOT_DIR)/scripts/test_project_handoff.py
	PYTHONDONTWRITEBYTECODE=1 python3 $(ROOT_DIR)/scripts/test_research_start_packet.py
	python3 -c "import ast,pathlib; [ast.parse(pathlib.Path(p).read_text(encoding='utf-8')) for p in ['$(ROOT_DIR)/scripts/crux_engine.py','$(ROOT_DIR)/scripts/hypothesis_engine.py','$(ROOT_DIR)/scripts/landscape_engine.py','$(ROOT_DIR)/scripts/framing_feasibility.py','$(ROOT_DIR)/scripts/opportunity_engine.py','$(ROOT_DIR)/scripts/candidate_gap_engine.py','$(ROOT_DIR)/scripts/candidate_screen_engine.py','$(ROOT_DIR)/scripts/codex_candidate_screen_receipt.py','$(ROOT_DIR)/scripts/evidence_snapshot.py','$(ROOT_DIR)/scripts/claim_verification_engine.py','$(ROOT_DIR)/scripts/research_output.py','$(ROOT_DIR)/scripts/deepthink_orchestrator_v2.py','$(ROOT_DIR)/scripts/report_v2.py','$(ROOT_DIR)/scripts/validate_report_v2.py','$(ROOT_DIR)/scripts/benchmark_harness.py','$(ROOT_DIR)/scripts/discovery_benchmark_harness.py','$(ROOT_DIR)/scripts/project_handoff.py','$(ROOT_DIR)/scripts/research_start_packet.py']]"
	TRADE_NOTHING_SCRATCH_DIR=$${TMPDIR:-/tmp}/trade-nothing-v2-selftest PYTHONDONTWRITEBYTECODE=1 python3 $(ROOT_DIR)/scripts/deepthink_orchestrator_v2.py --selftest
	@echo "🎉 Current deterministic gates passed."

test-legacy:
	@echo "🧪 Running legacy compatibility suites (not v2 calibration evidence)..."
	python3 $(DEV_DIR)/scripts/dungs_argumentation.py
	python3 $(DEV_DIR)/scripts/test_kelly_sizing.py
	python3 $(DEV_DIR)/scripts/test_v9_engine.py

test-live:
	@echo "🌐 Running live provider diagnostics. These scripts may report unavailable data without failing."
	python3 $(DEV_DIR)/scripts/test_integrated_providers.py
	python3 $(DEV_DIR)/scripts/test_data_acquisition.py

clean:
	@echo "🧹 Cleaning pycache and temp states..."
	rm -rf $(DEV_DIR)/scripts/__pycache__
	@for dst in $(SKILL_DIRS); do rm -rf $$dst/scripts/__pycache__; done
	rm -rf $(DEV_DIR)/scripts/.state/*
	@echo "✨ Clean complete."

server:
	@echo "⚡ Starting Autonomous REST Daemon Server..."
	python3 $(DEV_DIR)/scripts/trade_nothing_server.py

portfolio:
	@echo "📊 Reading Multi-Currency Transaction Ledger..."
	python3 $(DEV_DIR)/scripts/portfolio_manager.py

verify-report:
	@if [ -z "$(REPORT)" ] || [ -z "$(STATE)" ]; then \
		echo "Usage: make verify-report REPORT=path/to/report.md STATE=path/to/state.json"; \
		exit 1; \
	fi
	python3 $(DEV_DIR)/scripts/verify_report_math.py $(REPORT) $(STATE)
