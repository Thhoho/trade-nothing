# Trade Nothing — Evidence-Gated Research Skill Maintenance
# Dynamically extract version from centralized version.py
ROOT_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
VERSION := $(shell python3 -c "import sys; sys.path.insert(0, '$(ROOT_DIR)/scripts'); from version import __version__; print(__version__)")

DEV_DIR ?= $(if $(wildcard $(HOME)/Documents/trade-nothing/SKILL.md),$(HOME)/Documents/trade-nothing,$(ROOT_DIR))
GEMINI_SKILL_DIR ?= $(HOME)/.gemini/skills/trade-nothing
CODEX_SKILL_DIR ?= $(HOME)/.codex/skills/trade-nothing
CLAUDE_SKILL_DIR ?= $(HOME)/.claude/skills/trade-nothing
.PHONY: help install pull status test clean clean-state verify-version verify-report

help:
	@echo "=================================================================="
	@echo "Trade Nothing v$(VERSION) Research Skill Maintenance Suite"
	@echo "=================================================================="
	@echo "make install       : Sync controlled source files to Gemini, Codex and Claude skills"
	@echo "make status        : Verify managed source alignment and report inert legacy extras"
	@echo "make verify-version: Check version consistency across documentation"
	@echo "make test          : Run current deterministic safety and regression gates"
	@echo "make clean         : Clean Python cache only (never deletes research state)"
	@echo "make clean-state   : Remove legacy v1 state files; v2 research state preserved"
	@echo "=================================================================="

install:
	@echo "🚀 Installing controlled source files to Gemini, Codex and Claude..."
	@python3 "$(DEV_DIR)/scripts/install_skill.py" --source "$(DEV_DIR)" --targets \
		"$(GEMINI_SKILL_DIR)" "$(CODEX_SKILL_DIR)" "$(CLAUDE_SKILL_DIR)"
	@python3 "$(DEV_DIR)/scripts/check_source_sync.py" --source "$(DEV_DIR)" --targets \
		"$(GEMINI_SKILL_DIR)" "$(CODEX_SKILL_DIR)" "$(CLAUDE_SKILL_DIR)"
	@echo "✅ Install complete. Runtime JSON/state/scratch files were not touched; stale managed code was recoverably quarantined."

pull:
	@echo "Pull is intentionally disabled: $(DEV_DIR) is the single source of truth."
	@echo "Copy an intentional runtime change into DEV_DIR manually, review it, then run make install."

status:
	@python3 "$(DEV_DIR)/scripts/check_source_sync.py" --source "$(DEV_DIR)" --targets \
		"$(GEMINI_SKILL_DIR)" "$(CODEX_SKILL_DIR)" "$(CLAUDE_SKILL_DIR)"

verify-version:
	@echo "🔍 Running version consistency audit..."
	python3 "$(DEV_DIR)/scripts/version.py"

test:
	@echo "🧪 Running current deterministic safety and regression gates..."
	PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_v2_engine.py"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_landscape_engine.py"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_framing_feasibility.py"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_hypothesis_engine.py"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_hypothesis_integration.py"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_evidence_exhaustion_convergence.py"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_deepthink_host_runner.py"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_agy_candidate_screen_runner.py"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_claim_verifier_runner.py"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_run_registry.py"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_artifact_envelope.py"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_opportunity_engine.py"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_path_analysis.py"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_tracking_engine.py"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_logic_radar_v2.py"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_data_safety.py"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_candidate_gap_engine.py"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_research_output.py"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_candidate_screen_engine.py"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_claim_verification_engine.py"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_version.py"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_benchmark_current.py"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_benchmark_harness.py"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_discovery_benchmark_harness.py"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_project_handoff.py"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_research_start_packet.py"
	PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/test_install_skill.py"
	python3 -c "import ast,pathlib; [ast.parse(pathlib.Path(p).read_text(encoding='utf-8')) for p in ['$(ROOT_DIR)/scripts/crux_engine.py','$(ROOT_DIR)/scripts/hypothesis_engine.py','$(ROOT_DIR)/scripts/landscape_engine.py','$(ROOT_DIR)/scripts/framing_feasibility.py','$(ROOT_DIR)/scripts/opportunity_engine.py','$(ROOT_DIR)/scripts/candidate_gap_engine.py','$(ROOT_DIR)/scripts/candidate_screen_engine.py','$(ROOT_DIR)/scripts/codex_candidate_screen_receipt.py','$(ROOT_DIR)/scripts/codex_claim_verifier_receipt.py','$(ROOT_DIR)/scripts/evidence_snapshot.py','$(ROOT_DIR)/scripts/claim_verification_engine.py','$(ROOT_DIR)/scripts/claim_verifier_runner.py','$(ROOT_DIR)/scripts/process_control.py','$(ROOT_DIR)/scripts/install_skill.py','$(ROOT_DIR)/scripts/research_output.py','$(ROOT_DIR)/scripts/deepthink_orchestrator_v2.py','$(ROOT_DIR)/scripts/report_v2.py','$(ROOT_DIR)/scripts/validate_report_v2.py','$(ROOT_DIR)/scripts/benchmark_harness.py','$(ROOT_DIR)/scripts/discovery_benchmark_harness.py','$(ROOT_DIR)/scripts/project_handoff.py','$(ROOT_DIR)/scripts/research_start_packet.py']]"
	env "TRADE_NOTHING_SCRATCH_DIR=$${TMPDIR:-/tmp}/trade-nothing-v2-selftest" PYTHONDONTWRITEBYTECODE=1 python3 "$(ROOT_DIR)/scripts/deepthink_orchestrator_v2.py" --selftest
	@echo "🎉 Current deterministic gates passed."

clean:
	@echo "🧹 Cleaning pycache only. Research state is never deleted here."
	rm -rf "$(DEV_DIR)/scripts/__pycache__"
	rm -rf "$(GEMINI_SKILL_DIR)/scripts/__pycache__"
	rm -rf "$(CODEX_SKILL_DIR)/scripts/__pycache__"
	rm -rf "$(CLAUDE_SKILL_DIR)/scripts/__pycache__"
	@echo "✨ Clean complete. Run 'make clean-state' to remove legacy v1 state."

# scripts/.state/ holds BOTH legacy v1 state and migrated v2 research state, so a
# blanket delete destroys real research. Only v1 files are removable, and only on
# an explicit target.
clean-state:
	@echo "⚠️  Removing legacy v1 state files from scripts/.state/ (v2 state preserved)..."
	@find "$(DEV_DIR)/scripts/.state" -maxdepth 1 -name '*_state.json' \
		! -name '*_v2_state.json' -print -delete 2>/dev/null || true
	@echo "✨ Legacy v1 state removed. v2 state and $(TRADE_NOTHING_SCRATCH_DIR) untouched."

verify-report:
	@if [ -z "$(REPORT)" ] || [ -z "$(STATE)" ]; then \
		echo "Usage: make verify-report REPORT=path/to/report.md STATE=path/to/state.json"; \
		exit 1; \
	fi
	python3 "$(DEV_DIR)/scripts/verify_report_math.py" "$(REPORT)" "$(STATE)"
