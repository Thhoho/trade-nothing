# Trade Nothing v7.0 — Autonomous Investment Agent & Maintenance Automation

SKILL_DIR = $(HOME)/.gemini/skills/trade-nothing
DEV_DIR = $(HOME)/Documents/trade-nothing

.PHONY: help install pull status test clean server portfolio

help:
	@echo "=================================================================="
	@echo "Trade Nothing v7.0 Autonomous Agent Maintenance Suite"
	@echo "=================================================================="
	@echo "make install  : Sync dev files from Documents to Gemini Active Skill"
	@echo "make pull     : Pull updates from Active Skill back to Documents repo"
	@echo "make status   : Check Git status and verify directory alignment"
	@echo "make server   : Start the Autonomous REST Daemon Server (Port 8000)"
	@echo "make portfolio: Print current multi-currency transaction ledger"
	@echo "make test     : Run automated LFI, Bayesian, and Concurrency test suites"
	@echo "make clean    : Clean Python cache files and temp state files"
	@echo "=================================================================="

install:
	@echo "🚀 Syncing dev workspace to active Gemini Skill folder..."
	@mkdir -p $(SKILL_DIR)/scripts
	@mkdir -p $(SKILL_DIR)/agents
	cp -r $(DEV_DIR)/scripts/* $(SKILL_DIR)/scripts/
	cp -r $(DEV_DIR)/agents/* $(SKILL_DIR)/agents/
	cp $(DEV_DIR)/SKILL.md $(SKILL_DIR)/SKILL.md
	@echo "✅ Install complete. Active Gemini Skill is now up to date with dev workspace."


pull:
	@echo "📥 Pulling runtime updates from active Gemini Skill to dev workspace..."
	cp -r $(SKILL_DIR)/scripts/* $(DEV_DIR)/scripts/
	cp -r $(SKILL_DIR)/agents/* $(DEV_DIR)/agents/
	cp $(SKILL_DIR)/SKILL.md $(DEV_DIR)/SKILL.md
	@echo "✅ Pull complete. Local Documents workspace has been synchronized."

status:
	@echo "🔍 Checking Git Workspace..."
	@git status
	@echo "\n🔍 Active Skill path details:"
	@ls -la $(SKILL_DIR)/scripts/dungs_argumentation.py || echo "⚠️ Active Skill files not installed yet."

test:
	@echo "🧪 Running full mathematical and engineering verification suites..."
	python3 $(DEV_DIR)/scripts/dungs_argumentation.py
	python3 $(HOME)/.gemini/antigravity-cli/brain/f67491f6-a96d-474b-864f-9668f63ce8a6/scratch/test_lfi_bayes.py
	python3 $(HOME)/.gemini/antigravity-cli/brain/f67491f6-a96d-474b-864f-9668f63ce8a6/scratch/test_decoupling_concurrency.py
	python3 $(HOME)/.gemini/antigravity-cli/brain/f67491f6-a96d-474b-864f-9668f63ce8a6/scratch/test_data_resilience.py
	python3 $(HOME)/.gemini/antigravity-cli/brain/f67491f6-a96d-474b-864f-9668f63ce8a6/scratch/test_global_data.py
	python3 $(HOME)/.gemini/antigravity-cli/brain/f67491f6-a96d-474b-864f-9668f63ce8a6/scratch/test_pluggable_ext.py
	python3 $(HOME)/.gemini/antigravity-cli/brain/f67491f6-a96d-474b-864f-9668f63ce8a6/scratch/test_portfolio_execution.py
	@echo "🎉 All 7 verification test suites run successfully!"

clean:
	@echo "🧹 Cleaning pycache and temp states..."
	rm -rf $(DEV_DIR)/scripts/__pycache__
	rm -rf $(SKILL_DIR)/scripts/__pycache__
	rm -rf /tmp/concurrency_test_state.json
	rm -rf /tmp/test_trade_nothing_state.json
	@echo "✨ Clean complete."

server:
	@echo "⚡ Starting Autonomous REST Daemon Server..."
	python3 $(DEV_DIR)/scripts/trade_nothing_server.py

portfolio:
	@echo "📊 Reading Multi-Currency Transaction Ledger..."
	python3 $(DEV_DIR)/scripts/portfolio_manager.py

