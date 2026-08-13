# Trade Nothing — active v0.18 Skill maintenance
ROOT_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
VERSION := $(shell python3 -c "import sys; sys.path.insert(0, '$(ROOT_DIR)/scripts'); from version import __version__; print(__version__)")

DEV_DIR ?= $(if $(wildcard $(HOME)/Documents/trade-nothing/SKILL.md),$(HOME)/Documents/trade-nothing,$(ROOT_DIR))
GEMINI_SKILL_DIR ?= $(HOME)/.gemini/skills/trade-nothing
CODEX_SKILL_DIR ?= $(HOME)/.codex/skills/trade-nothing
CLAUDE_SKILL_DIR ?= $(HOME)/.claude/skills/trade-nothing
.PHONY: help install pull status test daily daily-finalize daily-topic clean verify-version

help:
	@echo "Trade Nothing v$(VERSION)"
	@echo "make install        Sync the active allowlisted Skill to Gemini, Codex and Claude"
	@echo "make status         Verify source alignment"
	@echo "make daily          Produce one observation and one 0-10 round topic proposal"
	@echo "make test           Run active deterministic product and safety gates"
	@echo "make verify-version Audit current version surfaces"

install:
	@python3 "$(DEV_DIR)/scripts/install_skill.py" --source "$(DEV_DIR)" --targets \
		"$(GEMINI_SKILL_DIR)" "$(CODEX_SKILL_DIR)" "$(CLAUDE_SKILL_DIR)"
	@python3 "$(DEV_DIR)/scripts/check_source_sync.py" --source "$(DEV_DIR)" --targets \
		"$(GEMINI_SKILL_DIR)" "$(CODEX_SKILL_DIR)" "$(CLAUDE_SKILL_DIR)"

pull:
	@echo "Pull is disabled: DEV_DIR is the reviewed source of truth."

status:
	@python3 "$(DEV_DIR)/scripts/check_source_sync.py" --source "$(DEV_DIR)" --targets \
		"$(GEMINI_SKILL_DIR)" "$(CODEX_SKILL_DIR)" "$(CLAUDE_SKILL_DIR)"

verify-version:
	@PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/version.py"

test:
	@echo "Running active v$(VERSION) deterministic gates..."
	@PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_research_core.py"
	@PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_research_loop.py"
	@PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_current_reality_regression.py"
	@PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_research_host_runner.py"
	@PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_model_process_runtime.py"
	@PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_free_market_observations.py"
	@PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_market_snapshot_adapter.py"
	@PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_research_market_input.py"
	@PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_research_report.py"
	@PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_product_reset_contract.py"
	@PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_research_registry.py"
	@PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_daily_topic.py"
	@PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_install_skill.py"
	@PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_version.py"
	@PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_benchmark_current.py"
	@PYTHONDONTWRITEBYTECODE=1 python3 -c "import ast,pathlib,sys; sys.path.insert(0,'$(ROOT_DIR)/scripts'); import method_identity; [ast.parse((pathlib.Path('$(ROOT_DIR)')/p).read_text(encoding='utf-8')) for p in method_identity.ACTIVE_METHOD_PATHS if p.endswith('.py')]"
	@echo "Active deterministic gates passed. Effectiveness remains a forward-test question."

daily:
	@PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/tools/daily_topic.py" $(ARGS)

daily-finalize:
	@if [ -z "$(INPUT)" ]; then echo "Usage: make daily-finalize INPUT=/path/to/daily.json ARGS='--as-of ...'"; exit 1; fi
	@PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/tools/daily_topic.py" --input-json "$(INPUT)" $(ARGS)

daily-topic: daily

clean:
	@echo "Remove Python cache directories manually if needed; research state is never deleted by Make."
