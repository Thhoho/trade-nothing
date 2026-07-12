# Design Spec: Trade Nothing Core Bug Fixes & Hardening

*   **Date**: 2026-05-27
*   **Status**: Draft
*   **Author**: Antigravity (GitHub Technical Expert Persona)
*   **Objective**: Fix 4 Critical/High bugs identified in the independent review, clean up data providers, secure notification channels against injection, and introduce real test assertions.

---

## 1. Proposed Changes

### Component A: Core Engine (`deepthink_engine.py`)

#### Problem 1: Dung Inversion Logic
*   **File**: `scripts/deepthink_engine.py` L418
*   **Fix**: Change `if attacker not in ge:` to `if attacker in ge:`. In Dung's framework, an attack is unrefuted/active if the attacker itself is accepted (`in ge`).

#### Problem 2: Thread-Safety of `STATE_FILE`
*   **File**: `scripts/deepthink_engine.py` L25-61
*   **Fix**: Replace the module-level mutable string `STATE_FILE` with a thread-local variable via `threading.local()`.
*   **Implementation**:
    ```python
    import threading
    _state_local = threading.local()

    def get_state_file() -> str:
        if not hasattr(_state_local, "state_file"):
            _state_local.state_file = os.path.join(SCRIPT_DIR, ".deepthink_state.json")
        return _state_local.state_file

    def set_state_file(path: str):
        _state_local.state_file = path
    ```
    And adjust all read/write references from `STATE_FILE` to `get_state_file()`.

---

### Component B: Data Gateway (`data_providers.py`)

#### Problem 3: AkShare Field and Divisor Mismatch
*   **File**: `scripts/data_providers.py` L334-335
*   **Fix**:
    *   Change `"turnover_rate": safe_float(r.get("涨跌幅"))` to `"turnover_rate": safe_float(r.get("换手率"))`.
    *   Change `"market_cap_billions": market_cap_raw / 1e9` to `"market_cap_billions": market_cap_raw / 1e8` to align units ("亿" CNY) with Tencent and NetEase.

---

### Component C: Utilities (`utils.py`)

#### Problem 4: OS Command Injection in Notifications
*   **File**: `scripts/utils.py` L115-135
*   **Fix**: Define a rigorous regex sanitiser to strip dangerous shell delimiters (`"`, `` ` ``, `$`, `;`, `\`) from `title` and `message` strings before execution.
*   **Implementation**:
    ```python
    import re
    def sanitize_notification_text(text: str) -> str:
        if not text:
            return ""
        # Strip characters that can break double-quoted string contexts or chain execution
        clean = re.sub(r'["`$;\\]', '', text)
        return clean.replace('\n', ' ').replace('\r', '')
    ```

---

### Component D: Verification & Testing (`test_v9_engine.py` & new tests)

#### Problem 5: Zero assertions in tests
*   **File**: `scripts/test_v9_engine.py` and `scripts/test_kelly_sizing.py`
*   **Fix**: Convert print-only checks into actual `assert` statements so the test runner (pytest/unittest) can fail on correctness errors.
*   **Example**:
    ```python
    assert result.converged is True, "Engine did not converge"
    assert len(unrefuted_attacks) == 0, "Should have zero unrefuted attacks under base case"
    ```

---

## 2. Verification Plan

### Automated Tests
1. Run `python -m unittest scripts/test_v9_engine.py` to ensure core engine runs with thread-local variables and correct Dung logic.
2. Run `python -m unittest scripts/test_kelly_sizing.py` to verify quantitative outputs.

### Manual Verification
1. Verify no syntax or runtime errors occur during dynamic plugin discovery.
2. Check that the global state file is correctly resolved per-thread under simulated concurrent API calls.
