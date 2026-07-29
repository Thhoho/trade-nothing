#!/usr/bin/env python3
"""Separate evidence cutoff, relative horizon, and explicit forecast target."""
from __future__ import annotations

import re
from datetime import date


SCHEMA = "trade-nothing.temporal-contract.v1"
_DATE_IN_TEXT = re.compile(
    r"(?<!\d)(20\d{2})(?:-|/|\.|年)(\d{1,2})(?:-|/|\.|月)(\d{1,2})日?(?!\d)"
)


class TemporalContractError(ValueError):
    pass


def iso_date(raw, field, optional=False):
    value = str(raw or "").strip()
    if optional and not value:
        return ""
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise TemporalContractError(f"{field} must use YYYY-MM-DD") from exc


def dates_in_text(raw):
    result = []
    for match in _DATE_IN_TEXT.finditer(str(raw or "")):
        try:
            value = date(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
            ).isoformat()
        except ValueError:
            continue
        if value not in result:
            result.append(value)
    return result


def validate_question(question, prefix="question"):
    if not isinstance(question, dict):
        raise TemporalContractError(f"{prefix} must be an object")
    evidence_as_of = iso_date(
        question.get("as_of_date"),
        f"{prefix}.as_of_date",
    )
    forecast_target = iso_date(
        question.get("forecast_target_date"),
        f"{prefix}.forecast_target_date",
        optional=True,
    )
    if forecast_target and forecast_target <= evidence_as_of:
        raise TemporalContractError(
            f"{prefix}.forecast_target_date must be later than "
            f"{prefix}.as_of_date"
        )
    future_dates = [
        value
        for value in dates_in_text(question.get("decision_question"))
        if value > evidence_as_of
    ]
    if future_dates and not forecast_target:
        raise TemporalContractError(
            f"{prefix}.forecast_target_date is required when "
            f"{prefix}.decision_question mentions a later date"
        )
    return {
        "evidence_as_of_date": evidence_as_of,
        "forecast_target_date": forecast_target,
        "decision_horizon": str(question.get("horizon") or "").strip(),
        "future_dates_mentioned_in_question": future_dates,
    }


def from_state(state):
    state = state if isinstance(state, dict) else {}
    frame = (
        state.get("frame_contract")
        if isinstance(state.get("frame_contract"), dict)
        else {}
    )
    question = {
        "decision_question": state.get("decision_question"),
        "horizon": state.get("horizon"),
        "as_of_date": frame.get("as_of_date") or state.get("as_of_date"),
        "forecast_target_date": (
            frame.get("forecast_target_date")
            or state.get("forecast_target_date")
            or ""
        ),
    }
    try:
        normalized = validate_question(question, prefix="state.frame_contract")
    except TemporalContractError as exc:
        evidence_as_of = _safe_date(question["as_of_date"])
        future_dates = [
            value
            for value in dates_in_text(question["decision_question"])
            if evidence_as_of and value > evidence_as_of
        ]
        return {
            "schema_version": SCHEMA,
            "status": "AMBIGUOUS_OR_INVALID",
            "evidence_as_of_date": evidence_as_of,
            "forecast_target_date": _safe_date(
                question["forecast_target_date"]
            ),
            "decision_horizon": question["horizon"],
            "future_dates_mentioned_in_question": future_dates,
            "requires_human_resolution": True,
            "message": str(exc),
        }
    return {
        "schema_version": SCHEMA,
        "status": (
            "EXPLICIT_FORWARD_TARGET"
            if normalized["forecast_target_date"]
            else "EVIDENCE_CUTOFF_WITH_HORIZON"
        ),
        **normalized,
        "requires_human_resolution": False,
        "message": (
            f"Evidence stops at {normalized['evidence_as_of_date']}; "
            f"forecast target is {normalized['forecast_target_date']}."
            if normalized["forecast_target_date"]
            else
            f"Evidence stops at {normalized['evidence_as_of_date']}; "
            f"decision horizon is {normalized['decision_horizon']}."
        ),
    }


def _safe_date(raw):
    try:
        return date.fromisoformat(str(raw or "").strip()).isoformat()
    except ValueError:
        return ""
