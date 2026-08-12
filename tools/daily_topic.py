#!/usr/bin/env python3
"""Produce one daily observation and one minimum-sufficient research topic.

This is deliberately a thin host entrypoint. It asks one ephemeral Codex run to
inspect current public information and return two linked artifacts from the same
evidence set. It never creates a Trade Nothing research run, spends research
rounds, or publishes.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, time
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlparse
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "var" / "daily"
LEGACY_OUTPUT_DIR = ROOT / "var" / "daily-topics"
SHANGHAI = ZoneInfo("Asia/Shanghai")
SCHEMA_VERSION = "trade-nothing.daily-content-bundle.v1"
MARKET_CLOSE = time(15, 0)
MARKET_OPEN = time(9, 30)
DAILY_FINALIZATION = time(18, 0)

CHANGE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "change_id",
        "title",
        "detail",
        "source_url",
        "source_date",
        "evidence_label",
    ],
    "properties": {
        "change_id": {"type": "string", "enum": ["C1", "C2", "C3"]},
        "title": {"type": "string"},
        "detail": {"type": "string"},
        "source_url": {"type": "string"},
        "source_date": {"type": "string"},
        "evidence_label": {
            "type": "string",
            "enum": ["FACT", "SINGLE_SOURCE", "INFERENCE"],
        },
    },
}

OBSERVATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "status",
        "market_state",
        "headline",
        "changes",
        "industry_market_bridge",
        "decision_boundary",
        "next_validation",
        "degradation_reason",
    ],
    "properties": {
        "status": {"type": "string", "enum": ["READY", "DEGRADED"]},
        "market_state": {"type": "string"},
        "headline": {"type": "string"},
        "changes": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": CHANGE_SCHEMA,
        },
        "industry_market_bridge": {"type": "string"},
        "decision_boundary": {"type": "string"},
        "next_validation": {"type": "string"},
        "degradation_reason": {"type": "string"},
    },
}

SELECTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "status",
        "topic",
        "decision_question",
        "why_now",
        "decision_change",
        "supporting_change_ids",
        "round_budget",
        "budget_reason",
        "why_not_less",
        "why_not_more",
        "round_plan",
        "stop_condition",
        "continuation_condition",
        "evidence_risks",
        "execution_instruction",
    ],
    "properties": {
        "status": {"type": "string", "enum": ["TOPIC_READY", "NO_TOPIC"]},
        "topic": {"type": "string"},
        "decision_question": {"type": "string"},
        "why_now": {"type": "string"},
        "decision_change": {"type": "string"},
        "supporting_change_ids": {
            "type": "array",
            "maxItems": 3,
            "items": {"type": "string", "enum": ["C1", "C2", "C3"]},
        },
        "round_budget": {"type": "integer", "minimum": 0, "maximum": 10},
        "budget_reason": {"type": "string"},
        "why_not_less": {"type": "string"},
        "why_not_more": {"type": "string"},
        "round_plan": {
            "type": "array",
            "maxItems": 10,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["round", "objective", "enter_if", "stop_if"],
                "properties": {
                    "round": {"type": "integer", "minimum": 1, "maximum": 10},
                    "objective": {"type": "string"},
                    "enter_if": {"type": "string"},
                    "stop_if": {"type": "string"},
                },
            },
        },
        "stop_condition": {"type": "string"},
        "continuation_condition": {"type": "string"},
        "evidence_risks": {
            "type": "array",
            "maxItems": 5,
            "items": {"type": "string"},
        },
        "execution_instruction": {"type": "string"},
    },
}

DAILY_OUTPUT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["observation", "selection"],
    "properties": {
        "observation": OBSERVATION_SCHEMA,
        "selection": SELECTION_SCHEMA,
    },
}


class DailyTopicError(RuntimeError):
    """Fail-closed error for a daily topic selection run."""


def _text(value):
    return " ".join(str(value or "").split())


def _parse_as_of(raw):
    if not raw:
        return datetime.now(SHANGHAI)
    value = str(raw).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            parsed_date = date.fromisoformat(value)
        except ValueError as exc:
            raise DailyTopicError("as_of_must_be_iso_date_or_datetime") from exc
        return datetime.combine(parsed_date, time(18, 30), tzinfo=SHANGHAI)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise DailyTopicError("as_of_must_be_iso_date_or_datetime")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SHANGHAI)
    return parsed.astimezone(SHANGHAI)


def _trade_day_status(as_of):
    session = as_of.date()
    if session.weekday() >= 5:
        return {
            "status": "CLOSED",
            "source": "WEEKEND_CALENDAR",
            "session": session.isoformat(),
            "reason": "weekend",
        }

    token = _text(os.environ.get("TUSHARE_TOKEN"))
    if not token:
        return {
            "status": "UNKNOWN",
            "source": "TUSHARE",
            "session": session.isoformat(),
            "reason": "tushare_token_missing",
        }
    try:
        import tushare as ts  # type: ignore

        pro = ts.pro_api(token, timeout=15)
        compact = session.strftime("%Y%m%d")
        frame = pro.query(
            "trade_cal",
            exchange="SSE",
            start_date=compact,
            end_date=compact,
            fields="exchange,cal_date,is_open,pretrade_date",
        )
        rows = frame.to_dict(orient="records") if hasattr(frame, "to_dict") else []
        if len(rows) != 1:
            raise ValueError("trade_calendar_row_missing")
        is_open = str(rows[0].get("is_open", "")).strip()
        if is_open not in {"0", "1"}:
            raise ValueError("trade_calendar_is_open_invalid")
        return {
            "status": "OPEN" if is_open == "1" else "CLOSED",
            "source": "TUSHARE_TRADE_CAL",
            "session": session.isoformat(),
            "previous_session": str(rows[0].get("pretrade_date") or ""),
            "reason": "verified_open" if is_open == "1" else "verified_closed",
        }
    except Exception as exc:  # provider availability is contextual, not fatal
        return {
            "status": "UNKNOWN",
            "source": "TUSHARE",
            "session": session.isoformat(),
            "reason": f"calendar_unavailable:{type(exc).__name__}",
        }


def _market_session_context(as_of, calendar):
    """Project wall-clock time into one explicit daily-content boundary.

    A calendar date is not a completed market session.  The previous implementation
    allowed a 01:23 run to become the canonical "daily" artifact and then block the
    actual close.  This projection is deliberately small and deterministic: only a
    post-settlement run may write the canonical daily slot.
    """
    calendar_status = _text((calendar or {}).get("status")).upper() or "UNKNOWN"
    local_time = as_of.timetz().replace(tzinfo=None)
    if calendar_status == "CLOSED":
        phase = "CLOSED"
        canonical_output_allowed = True
    elif local_time < MARKET_OPEN:
        phase = "PRE_OPEN"
        canonical_output_allowed = False
    elif local_time < MARKET_CLOSE:
        phase = "IN_SESSION"
        canonical_output_allowed = False
    elif local_time < DAILY_FINALIZATION:
        phase = "POST_CLOSE_SETTLING"
        canonical_output_allowed = False
    else:
        phase = "POST_CLOSE_FINAL"
        canonical_output_allowed = True
    return {
        "phase": phase,
        "session": as_of.date().isoformat(),
        "calendar_status": calendar_status,
        "canonical_output_allowed": canonical_output_allowed,
        "ready_allowed": canonical_output_allowed and calendar_status == "OPEN",
        "finalization_time": DAILY_FINALIZATION.isoformat(timespec="minutes"),
        "previous_complete_session": _text(
            (calendar or {}).get("previous_session")
        ),
    }


def _recent_topics(output_dir, before_date, limit=7, legacy_output_dir=LEGACY_OUTPUT_DIR):
    topics = []
    paths = list(Path(output_dir).glob("????-??-??/topic-card.json"))
    if legacy_output_dir:
        paths.extend(Path(legacy_output_dir).glob("????-??-??.json"))
    dated_paths = []
    for path in paths:
        slug = path.parent.name if path.name == "topic-card.json" else path.stem
        if slug < before_date.isoformat():
            dated_paths.append((slug, path))
    for slug, path in sorted(dated_paths, reverse=True):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        selection = record.get("selection") or {}
        topic = _text(selection.get("topic"))
        if topic:
            topics.append(
                {
                    "date": slug,
                    "topic": topic,
                    "question": _text(selection.get("decision_question")),
                }
            )
        if len(topics) >= limit:
            break
    return topics


def _method_identity():
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import method_identity

        return method_identity.build_method_identity(ROOT)
    finally:
        try:
            sys.path.remove(str(ROOT / "scripts"))
        except ValueError:
            pass


def build_prompt(
    as_of, calendar, recent_topics, method_identity, market_session=None
):
    history = json.dumps(recent_topics, ensure_ascii=False, indent=2)
    identity = json.dumps(method_identity, ensure_ascii=False, sort_keys=True)
    calendar_json = json.dumps(calendar, ensure_ascii=False, sort_keys=True)
    session_json = json.dumps(
        market_session or _market_session_context(as_of, calendar),
        ensure_ascii=False,
        sort_keys=True,
    )
    return f"""You are Trade Nothing's daily market observer and topic editor. Observe and select; do not perform research.

WORK WINDOW
- Repository: {ROOT}
- Fact cutoff: {as_of.isoformat(timespec='minutes')}
- Trading calendar observation: {calendar_json}
- Market-session boundary: {session_json}
- Current method identity: {identity}
- Recent selected topics, only for repetition control: {history}

Read SKILL.md completely before deciding. Use its evidence, market-mechanics, economic-exposure,
candidate-comparison, and bounded-round principles only as an observation and selection rubric.
Do not create or resume any run, do not invoke -deepthink2, do not edit files, and do not publish.

ONE SCAN, TWO LINKED OUTPUTS
1. Browse current public information up to the cutoff. Establish what actually changed today and
   over the previous week. Prefer primary official sources for event facts and use market data only
   as market evidence. The observation is a 600-1000 Chinese-character decision brief, not a news
   digest and not a research report.
2. The host has already supplied the trading-calendar observation. No provider token or API secret
   is available to you. Use public sources for any further market checks.
3. Produce one observation first. READY is legal only when market-session ready_allowed=true and
   requires exactly three genuinely decision-relevant changes;
   each needs a unique C1/C2/C3 ID, concrete URL, source date, and evidence label. If current evidence
   supports only one or two changes, use DEGRADED and explain the missing coverage. Never fill a slot
   with generic market commentary.
4. Explain the bridge from industrial change to value transfer, economic exposure, market carrier,
   price/crowding, and the next falsifiable checkpoint. Keep technical facts, economic exposure,
   market behavior, and recommendation boundaries distinct.
5. Then internally compare 3-5 candidate questions across sectors. Return exactly one only when it has
   both a real new change and plausible decision value. Do not expose the discarded list.
6. A price move, concept label, media volume, or launch/technical success alone is insufficient.
   Prefer questions that can connect a real change to a value-transfer path, economic exposure,
   actual market carriers, alternatives, price/crowding, and a future validation point.
7. The selection must cite observation changes only through supporting_change_ids; it may not invent
   a second fact set. TOPIC_READY needs at least two supporting IDs. If no question clears that bar,
   return NO_TOPIC with budget 0 and an empty ID list. The observation still exists.
8. If calendar or source coverage is uncertain, mark the observation DEGRADED and preserve the
   uncertainty. Do not manufacture freshness, verification, a recommendation, or a tradable setup.
9. "Today" means the supplied completed market session, never merely the same calendar date.
   PRE_OPEN, IN_SESSION and POST_CLOSE_SETTLING are not canonical daily-close windows.

MINIMUM-SUFFICIENT BUDGET
- 0 rounds: no new decision-relevant question.
- 1 round: a narrow event/fact question with one main causal chain and bounded carrier check.
- 2-3 rounds: an ordinary deep question that needs industry-to-market mapping, economic-versus-
  trading carrier comparison, or one meaningful adversarial pass.
- 4-6 rounds: a broad value-transfer problem with multiple causal chains, candidate groups, or
  time horizons that cannot be settled in one comparison cycle.
- 7-10 rounds: exceptional only. Each additional round must have a distinct decision-changing
  evidence target; breadth, popularity, or uncertainty alone cannot justify a large budget.

Never recommend more than 10 rounds. Choose the smallest budget that can answer the decision
question, not the largest budget the topic could consume. A high budget must describe why the work
cannot be parallelized or collapsed into fewer rounds.

For every non-zero budget, explain why one fewer round is inadequate, why one more is unnecessary,
and give one objective per round. Later rounds must have explicit entry and stop conditions. Budget
means a recommendation for later user authorization; it is not authorization to run research now.

Return one JSON object containing observation and selection, matching the supplied schema. Write
all prose in concise Chinese. For
TOPIC_READY, execution_instruction must be directly usable and have this form:
“使用最新 $trade-nothing，研究：<decision question>，-deepthink2 <N>轮。”
"""


def _redact(text):
    output = str(text or "")
    for name, value in os.environ.items():
        upper = name.upper()
        if value and any(marker in upper for marker in ("TOKEN", "API_KEY", "SECRET")):
            output = output.replace(value, f"<{upper}_REDACTED>")
    return output


def _sanitized_child_env(environment=None):
    source = dict(os.environ if environment is None else environment)
    secret_markers = ("TOKEN", "API_KEY", "SECRET")
    return {
        name: value
        for name, value in source.items()
        if not any(marker in name.upper() for marker in secret_markers)
    }


def _resolve_codex(codex_bin=""):
    if codex_bin:
        candidate = shutil.which(codex_bin) if os.sep not in codex_bin else codex_bin
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
        raise DailyTopicError(f"codex_cli_not_found:{codex_bin}")
    candidates = [
        Path("/Applications/ChatGPT.app/Contents/Resources/codex"),
        Path(shutil.which("codex")) if shutil.which("codex") else None,
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return str(candidate.resolve())
    raise DailyTopicError("codex_cli_not_found:auto")


def _run_codex(prompt, *, codex_bin, model, timeout_seconds):
    executable = _resolve_codex(codex_bin)
    if not executable or not Path(executable).is_file():
        raise DailyTopicError(f"codex_cli_not_found:{codex_bin}")

    with tempfile.TemporaryDirectory(prefix="trade-nothing-daily-") as tmp:
        tmp_path = Path(tmp)
        schema_path = tmp_path / "daily-output.schema.json"
        result_path = tmp_path / "daily-output.json"
        schema_path.write_text(
            json.dumps(DAILY_OUTPUT_SCHEMA, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        command = [
            str(executable),
            "exec",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--color",
            "never",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(result_path),
            "-C",
            str(ROOT),
        ]
        if model:
            command.extend(["--model", model])
        command.append("-")
        try:
            completed = subprocess.run(
                command,
                input=prompt,
                text=True,
                env=_sanitized_child_env(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=ROOT,
                check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise DailyTopicError("codex_cli_timeout") from exc
        if completed.returncode != 0:
            detail = _redact(completed.stderr or completed.stdout)[-2000:]
            raise DailyTopicError(f"codex_cli_failed:{completed.returncode}:{detail}")
        if not result_path.is_file():
            raise DailyTopicError("codex_cli_result_missing")
        try:
            return json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise DailyTopicError("codex_cli_result_invalid_json") from exc


def _valid_url(value):
    parsed = urlparse(_text(value))
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_observation(observation, *, allow_closed=False, cutoff_date=None):
    if not isinstance(observation, dict):
        raise DailyTopicError("observation_must_be_object")
    required = OBSERVATION_SCHEMA["required"]
    missing = [key for key in required if key not in observation]
    if missing:
        raise DailyTopicError("observation_missing:" + ",".join(missing))

    status = observation.get("status")
    changes = observation.get("changes")
    if allow_closed and status == "SKIPPED_CLOSED":
        if changes:
            raise DailyTopicError("closed_observation_must_not_have_changes")
        return observation
    if status not in {"READY", "DEGRADED"}:
        raise DailyTopicError("observation_status_invalid")
    for field in (
        "market_state",
        "headline",
        "industry_market_bridge",
        "decision_boundary",
        "next_validation",
    ):
        if not _text(observation.get(field)):
            raise DailyTopicError(f"observation_missing:{field}")
    if not isinstance(changes, list) or not 1 <= len(changes) <= 3:
        raise DailyTopicError("observation_changes_invalid")
    if status == "READY" and len(changes) != 3:
        raise DailyTopicError("ready_observation_requires_three_changes")
    if status == "DEGRADED" and not _text(observation.get("degradation_reason")):
        raise DailyTopicError("degraded_observation_requires_reason")
    if status == "READY" and _text(observation.get("degradation_reason")):
        raise DailyTopicError("ready_observation_must_not_have_degradation_reason")

    expected_ids = [f"C{index}" for index in range(1, len(changes) + 1)]
    actual_ids = []
    for item in changes:
        if not isinstance(item, dict):
            raise DailyTopicError("observation_change_invalid")
        actual_ids.append(item.get("change_id"))
        if not _text(item.get("title")) or not _text(item.get("detail")):
            raise DailyTopicError("observation_change_text_invalid")
        if item.get("evidence_label") not in {"FACT", "SINGLE_SOURCE", "INFERENCE"}:
            raise DailyTopicError("observation_change_label_invalid")
        if not _valid_url(item.get("source_url")):
            raise DailyTopicError("observation_change_url_invalid")
        try:
            source_date = date.fromisoformat(_text(item.get("source_date"))[:10])
        except ValueError as exc:
            raise DailyTopicError("observation_change_date_invalid") from exc
        if cutoff_date and source_date > cutoff_date:
            raise DailyTopicError("observation_change_after_cutoff")
    if actual_ids != expected_ids:
        raise DailyTopicError("observation_change_ids_must_be_sequential")
    return observation


def validate_selection(selection):
    if not isinstance(selection, dict):
        raise DailyTopicError("selection_must_be_object")
    missing = [key for key in SELECTION_SCHEMA["required"] if key not in selection]
    if missing:
        raise DailyTopicError("selection_missing:" + ",".join(missing))

    status = selection.get("status")
    budget = selection.get("round_budget")
    rounds = selection.get("round_plan")
    change_ids = selection.get("supporting_change_ids")
    if status not in {"TOPIC_READY", "NO_TOPIC"}:
        raise DailyTopicError("selection_status_invalid")
    if isinstance(budget, bool) or not isinstance(budget, int) or not 0 <= budget <= 10:
        raise DailyTopicError("selection_round_budget_invalid")
    if not isinstance(rounds, list) or not isinstance(change_ids, list):
        raise DailyTopicError("selection_lists_invalid")

    if status == "NO_TOPIC":
        if budget != 0 or rounds or change_ids:
            raise DailyTopicError("no_topic_must_have_zero_budget")
        if _text(selection.get("topic")) or _text(selection.get("decision_question")):
            raise DailyTopicError("no_topic_must_not_name_topic")
        return selection

    if budget not in range(1, 11):
        raise DailyTopicError("topic_ready_requires_positive_budget")
    for field in (
        "topic",
        "decision_question",
        "why_now",
        "decision_change",
        "budget_reason",
        "why_not_less",
        "why_not_more",
        "stop_condition",
        "continuation_condition",
        "execution_instruction",
    ):
        if not _text(selection.get(field)):
            raise DailyTopicError(f"topic_ready_missing:{field}")
    if len(rounds) != budget:
        raise DailyTopicError("round_plan_must_match_budget")
    if [item.get("round") for item in rounds if isinstance(item, dict)] != list(
        range(1, budget + 1)
    ):
        raise DailyTopicError("round_plan_sequence_invalid")
    if len(change_ids) < 2 or len(set(change_ids)) != len(change_ids):
        raise DailyTopicError("topic_ready_requires_two_unique_change_refs")
    if any(item not in {"C1", "C2", "C3"} for item in change_ids):
        raise DailyTopicError("selection_change_ref_invalid")
    instruction = _text(selection.get("execution_instruction"))
    if "$trade-nothing" not in instruction or "-deepthink2" not in instruction:
        raise DailyTopicError("execution_instruction_missing_mode")
    if not re.search(rf"(?:^|\D){budget}\s*轮", instruction):
        raise DailyTopicError("execution_instruction_budget_mismatch")
    return selection


def validate_daily_output(output, *, as_of=None, market_session=None):
    if not isinstance(output, dict) or set(output) != {"observation", "selection"}:
        raise DailyTopicError("daily_output_shape_invalid")
    cutoff_date = as_of.date() if isinstance(as_of, datetime) else as_of
    observation = validate_observation(
        output["observation"], cutoff_date=cutoff_date
    )
    if market_session and observation.get("status") == "READY" and not market_session.get(
        "ready_allowed"
    ):
        raise DailyTopicError("ready_observation_requires_completed_open_session")
    selection = validate_selection(output["selection"])
    available = {item["change_id"] for item in observation["changes"]}
    missing = [
        item for item in selection["supporting_change_ids"] if item not in available
    ]
    if missing:
        raise DailyTopicError("selection_change_ref_missing:" + ",".join(missing))
    return output


def _closed_selection(calendar):
    return {
        "status": "NO_TOPIC",
        "topic": "",
        "decision_question": "",
        "why_now": f"交易日历显示 {calendar['session']} 非交易日，本次未启动选题。",
        "decision_change": "",
        "supporting_change_ids": [],
        "round_budget": 0,
        "budget_reason": "非交易日默认不消耗研究预算。",
        "why_not_less": "预算已经为0轮。",
        "why_not_more": "没有需要由新增轮次回答的当日市场问题。",
        "round_plan": [],
        "stop_condition": "保持0轮，等待下一个交易日或用户显式要求评估重大事件。",
        "continuation_condition": "出现具有一手事实来源的重大产业事件时由用户显式强制运行。",
        "evidence_risks": [],
        "execution_instruction": "",
    }


def _closed_observation(calendar):
    return {
        "status": "SKIPPED_CLOSED",
        "market_state": "非交易日",
        "headline": f"{calendar['session']} 非交易日，不生成伪造的当日市场变化。",
        "changes": [],
        "industry_market_bridge": "没有当日交易形成的价格与筹码反馈，不做产业到市场的新增映射。",
        "decision_boundary": "本条仅记录日历边界，不构成市场判断、研究结论或推荐。",
        "next_validation": "下一个交易日重新核对一手事件、行业价值转移与市场载体表现。",
        "degradation_reason": "",
    }


def build_record(
    as_of, calendar, identity, observation, selection, market_session=None
):
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(SHANGHAI).isoformat(timespec="seconds"),
        "as_of": as_of.isoformat(timespec="minutes"),
        "calendar": calendar,
        "market_session": market_session or _market_session_context(as_of, calendar),
        "method_identity": identity,
        "boundary": (
            "Observation and topic-budget proposal only; no research run, research-round "
            "spend, recommendation, publication, or deployment."
        ),
        "observation": observation,
        "selection": selection,
    }


def _changes_by_id(record):
    return {item["change_id"]: item for item in record["observation"]["changes"]}


def render_observation_markdown(record):
    observation = record["observation"]
    selection = record["selection"]
    lines = [
        "# Trade Nothing 每日观察",
        "",
        f"> 事实截止：{record['as_of']}  ",
        f"> 观察状态：{observation['status']}  ",
        f"> 市场状态：{observation['market_state']}",
        "",
        "## 一句话市场判断",
        "",
        observation["headline"],
        "",
        "## 今天真正改变的三件事",
        "",
    ]
    if observation["changes"]:
        for item in observation["changes"]:
            lines.append(
                f"- **{item['change_id']} · {item['title']}** — `{item['evidence_label']}` "
                f"{item['detail']} ([来源]({item['source_url']})，{item['source_date']})"
            )
    else:
        lines.append("- 无：非交易日不构造当日变化。")
    lines.extend(
        [
            "",
            "## 产业到市场的连接",
            "",
            observation["industry_market_bridge"],
            "",
            "## 今日研究焦点",
            "",
        ]
    )
    if selection["status"] == "TOPIC_READY":
        lines.extend(
            [
                f"**{selection['topic']} · 建议 {selection['round_budget']}轮**",
                "",
                selection["decision_question"],
            ]
        )
    else:
        lines.append("**NO_TOPIC · 0轮。** 今天没有达到新增深研门槛的问题。")
    lines.extend(
        [
            "",
            "## 今日边界",
            "",
            observation["decision_boundary"],
            "",
            "## 下一验证",
            "",
            observation["next_validation"],
        ]
    )
    if observation.get("degradation_reason"):
        lines.extend(
            [
                "",
                "## 降级说明",
                "",
                observation["degradation_reason"],
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_topic_markdown(record):
    selection = record["selection"]
    lines = [
        "# Trade Nothing 每日选题卡",
        "",
        f"> 事实截止：{record['as_of']}  ",
        f"> 状态：{selection['status']}  ",
        f"> 建议预算：{selection['round_budget']}轮",
        "",
    ]
    if selection["status"] != "TOPIC_READY":
        lines.extend(
            [
                "## 今日判断",
                "",
                selection["why_now"],
                "",
                f"**预算理由：** {selection['budget_reason']}",
                "",
                f"**继续条件：** {selection['continuation_condition']}",
            ]
        )
        return "\n".join(lines).rstrip() + "\n"

    lines.extend(
        [
            "## 今日唯一主题",
            "",
            f"**{selection['topic']}**",
            "",
            selection["decision_question"],
            "",
            f"**为什么是今天：** {selection['why_now']}",
            "",
            f"**可能改变的判断：** {selection['decision_change']}",
            "",
            "## 当日变化",
            "",
        ]
    )
    changes = _changes_by_id(record)
    for change_id in selection["supporting_change_ids"]:
        item = changes[change_id]
        lines.append(
            f"- **{change_id} · {item['title']}** — `{item['evidence_label']}` {item['detail']} "
            f"([来源]({item['source_url']})，{item['source_date']})"
        )
    lines.extend(
        [
            "",
            "## 预算",
            "",
            f"**建议：{selection['round_budget']}轮。** {selection['budget_reason']}",
            "",
            f"- 为什么不能更少：{selection['why_not_less']}",
            f"- 为什么不需要更多：{selection['why_not_more']}",
            "",
            "## 轮次计划",
            "",
        ]
    )
    for item in selection["round_plan"]:
        lines.extend(
            [
                f"### 第{item['round']}轮",
                "",
                item["objective"],
                "",
                f"- 进入条件：{item['enter_if']}",
                f"- 停止条件：{item['stop_if']}",
                "",
            ]
        )
    lines.extend(
        [
            "## 总停止边界",
            "",
            f"- 提前停止：{selection['stop_condition']}",
            f"- 继续条件：{selection['continuation_condition']}",
        ]
    )
    if selection["evidence_risks"]:
        lines.extend(["", "## 主要证据风险", ""])
        lines.extend(f"- {item}" for item in selection["evidence_risks"])
    lines.extend(
        [
            "",
            "## 执行指令",
            "",
            f"> {selection['execution_instruction']}",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


# Backward-compatible renderer name for callers that only need the topic card.
render_markdown = render_topic_markdown


def _atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def _artifact_records(record):
    common = {
        key: record[key]
        for key in (
            "schema_version",
            "generated_at",
            "as_of",
            "calendar",
            "market_session",
            "method_identity",
            "boundary",
        )
    }
    observation_record = {
        **common,
        "observation": record["observation"],
        "selection_summary": {
            "status": record["selection"]["status"],
            "topic": record["selection"]["topic"],
            "decision_question": record["selection"]["decision_question"],
            "round_budget": record["selection"]["round_budget"],
        },
    }
    changes = _changes_by_id(record)
    topic_record = {
        **common,
        "selection": record["selection"],
        "supporting_changes": [
            changes[item]
            for item in record["selection"]["supporting_change_ids"]
        ],
    }
    return observation_record, topic_record


def _record_phase(day_dir):
    path = Path(day_dir) / "observation.json"
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "UNKNOWN"
    phase = _text((existing.get("market_session") or {}).get("phase")).upper()
    if phase:
        return phase
    try:
        as_of = _parse_as_of(existing.get("as_of"))
    except DailyTopicError:
        return "UNKNOWN"
    return _market_session_context(as_of, existing.get("calendar") or {})["phase"]


def _archive_nonfinal_day(day_dir, output_dir, slug):
    """Move a poisoned early slot aside before writing the completed close.

    The move is recoverable and keeps the old artifacts byte-for-byte intact.
    """
    observation_path = Path(day_dir) / "observation.json"
    try:
        existing = json.loads(observation_path.read_text(encoding="utf-8"))
        stamp = re.sub(r"[^0-9]", "", _text(existing.get("as_of"))[11:16]) or "unknown"
    except (OSError, json.JSONDecodeError):
        stamp = "unknown"
    archive_root = Path(output_dir).parent / "daily-drafts" / slug
    archive_root.mkdir(parents=True, exist_ok=True)
    target = archive_root / stamp
    suffix = 1
    while target.exists():
        target = archive_root / f"{stamp}-{suffix}"
        suffix += 1
    os.replace(day_dir, target)
    return target


def persist_record(record, output_dir, *, replace=False):
    output_dir = Path(output_dir)
    slug = str(record["as_of"])[:10]
    day_dir = output_dir / slug
    paths = {
        "observation_json": day_dir / "observation.json",
        "observation_markdown": day_dir / "observation.md",
        "topic_json": day_dir / "topic-card.json",
        "topic_markdown": day_dir / "topic-card.md",
    }
    archived_nonfinal = None
    if day_dir.exists() and not replace:
        existing_phase = _record_phase(day_dir)
        incoming_phase = _text(
            (record.get("market_session") or {}).get("phase")
        ).upper()
        nonfinal_phases = {"PRE_OPEN", "IN_SESSION", "POST_CLOSE_SETTLING"}
        if existing_phase in nonfinal_phases and incoming_phase == "POST_CLOSE_FINAL":
            archived_nonfinal = _archive_nonfinal_day(day_dir, output_dir, slug)
        else:
            raise DailyTopicError(
                f"daily_content_exists:{slug}; use --replace explicitly"
            )

    observation_record, topic_record = _artifact_records(record)
    payloads = {
        "observation_json": json.dumps(
            observation_record, ensure_ascii=False, indent=2
        )
        + "\n",
        "observation_markdown": render_observation_markdown(record),
        "topic_json": json.dumps(topic_record, ensure_ascii=False, indent=2) + "\n",
        "topic_markdown": render_topic_markdown(record),
    }
    if day_dir.exists():
        for key, path in paths.items():
            _atomic_write(path, payloads[key])
        return paths

    output_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{slug}.", dir=output_dir))
    try:
        for key, path in paths.items():
            (staging / path.name).write_text(payloads[key], encoding="utf-8")
        os.replace(staging, day_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    if archived_nonfinal:
        paths["archived_nonfinal"] = archived_nonfinal
    return paths


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Produce one daily observation and one 0-10 round topic budget."
    )
    parser.add_argument("--as-of", default="", help="ISO date/datetime; default now in Shanghai")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument(
        "--codex-bin",
        default=os.environ.get("CODEX_BIN", ""),
        help="Codex CLI override; default prefers the current ChatGPT app bundle, then PATH",
    )
    parser.add_argument("--model", default="", help="Optional Codex model override")
    parser.add_argument("--timeout", type=int, default=600, help="Codex timeout in seconds")
    parser.add_argument("--replace", action="store_true", help="Replace today's generated artifacts")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run observation and topic selection even when the verified calendar is closed",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the fully assembled prompt without invoking Codex or writing files",
    )
    parser.add_argument(
        "--input-json",
        default="",
        help=(
            "Validate and persist an already-produced daily JSON object instead of "
            "starting a nested Codex process"
        ),
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        as_of = _parse_as_of(args.as_of)
        output_dir = Path(args.output_dir).expanduser().resolve()
        calendar = _trade_day_status(as_of)
        market_session = _market_session_context(as_of, calendar)
        identity = _method_identity()
        recent = _recent_topics(output_dir, as_of.date())
        prompt = build_prompt(
            as_of, calendar, recent, identity, market_session=market_session
        )
        if args.dry_run:
            print(prompt)
            return 0
        if not market_session["canonical_output_allowed"]:
            raise DailyTopicError(
                "daily_close_not_ready:"
                f"{market_session['phase']}; canonical output opens at "
                f"{market_session['finalization_time']} Asia/Shanghai"
            )
        if calendar["status"] == "CLOSED" and not args.force:
            observation = _closed_observation(calendar)
            selection = _closed_selection(calendar)
        else:
            if args.input_json:
                try:
                    raw_output = json.loads(
                        Path(args.input_json).expanduser().read_text(encoding="utf-8")
                    )
                except (OSError, json.JSONDecodeError) as exc:
                    raise DailyTopicError("daily_input_json_invalid") from exc
            else:
                raw_output = _run_codex(
                    prompt,
                    codex_bin=args.codex_bin,
                    model=args.model,
                    timeout_seconds=args.timeout,
                )
            output = validate_daily_output(
                raw_output,
                as_of=as_of,
                market_session=market_session,
            )
            observation = output["observation"]
            selection = output["selection"]
        validate_observation(observation, allow_closed=True)
        validate_selection(selection)
        record = build_record(
            as_of,
            calendar,
            identity,
            observation,
            selection,
            market_session=market_session,
        )
        paths = persist_record(record, output_dir, replace=args.replace)
        print(render_observation_markdown(record), end="")
        print("\n---\n")
        print(render_topic_markdown(record), end="")
        for label, path in paths.items():
            print(f"{label}: {path}")
        return 0
    except DailyTopicError as exc:
        print(f"daily failed: {_redact(exc)}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
