#!/usr/bin/env python3
"""Trade Nothing single-writer research core.

The core owns four persistent objects and nothing else:

* TaskSpec: what the research must answer;
* EvidenceStore: what was actually observed and checked;
* DecisionSnapshot: the only user-facing semantic truth;
* RunLedger: what the runtime actually executed.

It is deliberately not an investment rules engine.  Deterministic code validates
lineage, time, coverage, challenge provenance and atomic writes.  A Lead model is
the sole semantic writer of DecisionSnapshot.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import hashlib
import html
import json
import math
import re
import unicodedata
from urllib.parse import urlparse


RUN_SCHEMA = "trade-nothing.research-run.v2"
TASK_SCHEMA = "trade-nothing.task-spec.v1"
EVIDENCE_STORE_SCHEMA = "trade-nothing.evidence-store.v2"
SNAPSHOT_SCHEMA = "trade-nothing.decision-snapshot.v2"
LEDGER_SCHEMA = "trade-nothing.run-ledger.v2"
WORKING_SET_SCHEMA = "trade-nothing.working-set.v2"

HORIZONS = (
    "EVENT_DAYS",
    "TACTICAL_WEEKS",
    "EARNINGS_QUARTERS",
    "STRUCTURAL_YEARS",
)
ENTITY_TYPES = {
    "LISTED_COMPANY", "PRIVATE_COMPANY", "PROJECT", "EVENT", "INDUSTRY",
    "TECHNOLOGY", "ASSET", "OTHER",
}
EVIDENCE_BOUNDARIES = {"FACT", "SINGLE_SOURCE", "INFERENCE", "HYPOTHESIS"}
EVIDENCE_ORIGINS = {"LEAD_RESEARCH", "CHALLENGER", "USER_OR_HOST_SEED"}
SOURCE_CHECK_ORIGINS = {
    "LEAD_RESEARCH", "CHALLENGER", "HOST_INPUT", "CONTROLLED_FIXTURE",
}
DECISION_IMPACTS = {"HIGH", "MEDIUM", "LOW"}
DECISION_STATUSES = {
    "DECISION_READY",
    "MATERIAL_FACT_GAP",
    "RESEARCH_INCOMPLETE",
    "UNRESOLVED_CHALLENGE",
    "RUNTIME_DEGRADED",
}
ANSWER_STATUSES = {"OPEN", "PARTIAL", "ANSWERED", "DISPUTED"}
NEXT_TEST_AVAILABILITIES = {
    "SEARCH_NOW", "WAIT_FOR_DATE", "WAIT_FOR_EVENT", "NEEDS_USER_DATA", "UNKNOWN",
}
CHALLENGE_RESOLUTIONS = {"ACCEPTED", "PARTIAL", "REJECTED", "UNRESOLVED"}
MATERIAL_DECISION_DIMENSIONS = {
    "EARNINGS", "CASH_FLOW", "DILUTION", "CONTROL", "LIQUIDITY",
    "ECONOMIC_EXPOSURE", "LEGAL_REGULATORY", "OPERATIONS", "OTHER",
}
CANDIDATE_STANCES = {
    "CONDITIONAL_PRIORITY", "WATCH", "NO_SETUP", "EXPLORE",
}
DOCUMENT_FACT_TYPES = {
    "SUBJECT", "COUNTERPARTY", "SCOPE", "STATUS", "TERMS", "TIMING",
    "ECONOMIC_EFFECT", "CONDITION", "USE_OF_FUNDS", "AUDIT_CONCLUSION",
    "CONTROL_RELATIONSHIP", "OTHER_MATERIAL_FACT",
}
MATERIAL_EVENT_RULES = (
    ("AUDIT_OR_GOING_CONCERN", ("审计意见", "非标准审计", "持续经营", "无法表示意见", "保留意见")),
    ("FUNDS_OCCUPATION", ("资金占用", "占用资金")),
    ("SHARE_FREEZE", ("司法冻结", "轮候冻结", "冻结")),
    ("RELATED_PARTY_BORROWING", ("向控股股东借款", "关联借款", "借款", "关联交易")),
    ("IMPAIRMENT", ("资产减值", "计提减值", "减值")),
    ("LOSS_OR_PERFORMANCE", ("年度报告", "半年度报告", "季度报告", "业绩预告", "业绩快报", "亏损")),
    ("EQUITY_INCENTIVE", ("股权激励", "限制性股票")),
    ("PLEDGE", ("解质押", "质押")),
    ("UNLOCK_OR_HOLDING_CHANGE", ("限售", "解禁", "增持", "减持")),
    ("GUARANTEE", ("担保",)),
    ("FINANCING", ("定向增发", "向特定对象", "融资", "可转债")),
    ("MATERIAL_CONTRACT", ("重大合同", "合同")),
    ("LEGAL_REGULATORY", ("诉讼", "仲裁", "立案", "处罚", "风险警示", "破产", "重整")),
    ("CONTROL_CHANGE", ("控制权", "实际控制人")),
    ("OPERATIONS", ("停产", "复产", "终止", "解除", "变更")),
    ("INVESTMENT_OR_DISPOSAL", ("收购", "出售", "投资", "回购")),
)
MATERIAL_EVENT_REQUIRED_FACT_GROUPS = {
    "AUDIT_OR_GOING_CONCERN": (
        {"AUDIT_CONCLUSION"}, {"STATUS", "ECONOMIC_EFFECT", "CONDITION"},
    ),
    "FUNDS_OCCUPATION": (
        {"COUNTERPARTY", "CONTROL_RELATIONSHIP"},
        {"STATUS", "ECONOMIC_EFFECT", "TERMS"},
    ),
    "SHARE_FREEZE": (
        {"SCOPE"}, {"STATUS", "TIMING", "ECONOMIC_EFFECT"},
    ),
    "RELATED_PARTY_BORROWING": (
        {"COUNTERPARTY", "CONTROL_RELATIONSHIP"},
        {"STATUS", "TERMS", "USE_OF_FUNDS", "ECONOMIC_EFFECT"},
    ),
    "IMPAIRMENT": (
        {"SCOPE"}, {"ECONOMIC_EFFECT", "STATUS", "AUDIT_CONCLUSION"},
    ),
    "LOSS_OR_PERFORMANCE": (
        {"SCOPE", "SUBJECT"}, {"ECONOMIC_EFFECT", "STATUS", "AUDIT_CONCLUSION"},
    ),
    "EQUITY_INCENTIVE": (
        {"SCOPE", "SUBJECT"}, {"TERMS", "CONDITION", "TIMING"},
    ),
    "PLEDGE": (
        {"SCOPE", "SUBJECT"}, {"STATUS", "TERMS", "TIMING"},
    ),
    "UNLOCK_OR_HOLDING_CHANGE": (
        {"SCOPE", "SUBJECT"}, {"TIMING", "STATUS", "TERMS"},
    ),
    "GUARANTEE": (
        {"COUNTERPARTY", "SCOPE"}, {"TERMS", "STATUS", "ECONOMIC_EFFECT"},
    ),
    "FINANCING": (
        {"SCOPE", "SUBJECT"}, {"TERMS", "STATUS", "CONDITION", "USE_OF_FUNDS"},
    ),
    "MATERIAL_CONTRACT": (
        {"COUNTERPARTY", "SCOPE"}, {"TERMS", "STATUS", "CONDITION"},
    ),
    "LEGAL_REGULATORY": (
        {"SCOPE", "SUBJECT"}, {"STATUS", "ECONOMIC_EFFECT", "TIMING"},
    ),
    "CONTROL_CHANGE": (
        {"CONTROL_RELATIONSHIP", "SUBJECT"}, {"STATUS", "CONDITION", "TIMING"},
    ),
    "OPERATIONS": (
        {"SCOPE", "SUBJECT"}, {"STATUS", "TIMING", "ECONOMIC_EFFECT"},
    ),
    "INVESTMENT_OR_DISPOSAL": (
        {"SCOPE", "COUNTERPARTY"}, {"TERMS", "STATUS", "ECONOMIC_EFFECT"},
    ),
}
ACTION_TYPES = {"RESEARCH", "CHALLENGE", "RESOLUTION"}
ACTION_TARGETS = {
    "decision_snapshot",
    "core_judgment", "material_changes", "agenda_answers", "value_transfer_paths",
    "market_by_horizon", "market_carriers_by_horizon", "candidates_by_horizon",
    "challenge_resolutions", "decision_status", "lowest_cost_next_validation",
}
SOURCE_CHECK_OUTCOMES = {"FOUND", "NO_RESULT", "INSUFFICIENT"}
INDEX_ENTRY_DISPOSITIONS = {
    "OPENED_RELEVANT", "REVIEWED_NOT_MATERIAL", "DISMISSED_BY_TITLE",
}
RECEIPT_PROVENANCES = {
    "SELF_DECLARED", "HARNESS_SUBAGENT", "HOST_PROCESS", "CONTROLLED_FIXTURE",
}
EVIDENCE_ROLES = {
    "CURRENT_REALITY", "ECONOMIC_EXPOSURE", "MARKET_STATE",
    "TECHNICAL_STATE", "CATALYST", "RISK",
}
MEASURE_UNITS = {
    "CNY", "CNY_10K", "CNY_100M", "CNY_BN", "PERCENT", "RATIO",
    "POINTS", "SHARES", "COUNT", "DAYS",
}
MEASURE_DIMENSIONS = {
    "CURRENCY", "PERCENT", "RATIO", "POINTS", "SHARES", "COUNT", "DURATION",
}
MEASURE_UNIT_DIMENSIONS = {
    "CNY": "CURRENCY", "CNY_10K": "CURRENCY",
    "CNY_100M": "CURRENCY", "CNY_BN": "CURRENCY",
    "PERCENT": "PERCENT", "RATIO": "RATIO", "POINTS": "POINTS",
    "SHARES": "SHARES", "COUNT": "COUNT", "DAYS": "DURATION",
}
MEASURE_PERIODS = {
    "POINT_IN_TIME", "SESSION", "5D", "20D", "60D", "QUARTER",
    "HALF_YEAR", "YEAR", "OTHER",
}
_CURRENCY_UNITS = {"CNY", "CNY_10K", "CNY_100M", "CNY_BN"}
MEASURE_METRICS = {
    "return_5d": ("标的短窗口收益率", {"PERCENT"}),
    "return_20d": ("标的中窗口收益率", {"PERCENT"}),
    "return_60d": ("标的长窗口收益率", {"PERCENT"}),
    "excess_5d": ("相对基准短窗口超额收益", {"PERCENT"}),
    "excess_20d": ("相对基准中窗口超额收益", {"PERCENT"}),
    "excess_60d": ("相对基准长窗口超额收益", {"PERCENT"}),
    "drawdown_60d": ("长窗口最高收盘价回撤", {"PERCENT"}),
    "turnover_rate": ("最新交易日换手率", {"PERCENT"}),
    "volume_ratio_20d": ("最新成交量相对中窗口均量", {"RATIO"}),
    "provider_volume_ratio": ("数据源提供的量比", {"RATIO"}),
    "pe_ttm": ("滚动市盈率", {"RATIO"}),
    "pb": ("市净率", {"RATIO"}),
    "total_market_cap_cny": ("总市值", {"CNY"}),
    "float_market_cap_cny": ("流通市值", {"CNY"}),
    "a_share_turnover": ("A股市场成交额", _CURRENCY_UNITS),
    "financing_amount": ("融资或资本计划金额", _CURRENCY_UNITS),
    "revenue": ("营业收入", _CURRENCY_UNITS),
    "net_profit_parent": ("归母净利润", _CURRENCY_UNITS),
    "operating_cash_flow": ("经营活动现金流量净额", _CURRENCY_UNITS),
    "cash_balance": ("货币资金余额", _CURRENCY_UNITS),
    "accounts_receivable": ("应收账款余额", _CURRENCY_UNITS),
    "contract_liabilities": ("合同负债余额", _CURRENCY_UNITS),
    "capex": ("资本开支", _CURRENCY_UNITS),
    "order_amount": ("订单金额", _CURRENCY_UNITS),
    "contract_amount": ("合同金额", _CURRENCY_UNITS),
    "buyback_amount": ("回购金额", _CURRENCY_UNITS),
    "gross_margin": ("毛利率", {"PERCENT"}),
    "net_margin": ("净利率", {"PERCENT"}),
    "debt_ratio": ("资产负债率", {"PERCENT"}),
    "pledge_ratio": ("股份质押比例", {"PERCENT"}),
    "utilization_rate": ("产能利用率", {"PERCENT"}),
    "market_share": ("市场份额", {"PERCENT"}),
    "unlock_shares": ("解除限售股份数量", {"SHARES"}),
    "holdings_change_shares": ("持股变动数量", {"SHARES"}),
    "share_count": ("股份数量", {"SHARES"}),
    "capacity_count": ("产能数量", {"COUNT"}),
    "shipment_count": ("出货数量", {"COUNT"}),
    "duration_days": ("持续天数", {"DAYS"}),
}
MEASURE_METRIC_UNITS = {
    metric: set(contract[1]) for metric, contract in MEASURE_METRICS.items()
}
MEASURE_BASES = {
    "DISCLOSURE_REPORTED": "公告或定期报告原文披露",
    "PROVIDER_REPORTED": "结构化数据源原始字段",
    "CALCULATED_PRICE_RETURN": "同日起止复权收盘价计算",
    "CALCULATED_BENCHMARK_EXCESS": "标的与基准同日起止收益差",
    "CALCULATED_PRICE_DRAWDOWN": "窗口最高收盘价与最新收盘价计算",
    "CALCULATED_VOLUME_RATIO": "最新成交量与窗口均量计算",
}
MARKET_MEASURE_CONTRACTS = {
    "return_5d": ({"5D"}, {"CALCULATED_PRICE_RETURN"}),
    "return_20d": ({"20D"}, {"CALCULATED_PRICE_RETURN"}),
    "return_60d": ({"60D"}, {"CALCULATED_PRICE_RETURN"}),
    "excess_5d": ({"5D"}, {"CALCULATED_BENCHMARK_EXCESS"}),
    "excess_20d": ({"20D"}, {"CALCULATED_BENCHMARK_EXCESS"}),
    "excess_60d": ({"60D"}, {"CALCULATED_BENCHMARK_EXCESS"}),
    "drawdown_60d": ({"60D"}, {"CALCULATED_PRICE_DRAWDOWN"}),
    "turnover_rate": ({"SESSION"}, {"PROVIDER_REPORTED"}),
    "volume_ratio_20d": ({"20D"}, {"CALCULATED_VOLUME_RATIO"}),
    "provider_volume_ratio": ({"POINT_IN_TIME", "SESSION"}, {"PROVIDER_REPORTED"}),
    "pe_ttm": ({"POINT_IN_TIME", "SESSION"}, {"PROVIDER_REPORTED"}),
    "pb": ({"POINT_IN_TIME", "SESSION"}, {"PROVIDER_REPORTED"}),
    "total_market_cap_cny": ({"POINT_IN_TIME", "SESSION"}, {"PROVIDER_REPORTED"}),
    "float_market_cap_cny": ({"POINT_IN_TIME", "SESSION"}, {"PROVIDER_REPORTED"}),
    "a_share_turnover": ({"SESSION"}, {"PROVIDER_REPORTED"}),
}
DISCLOSURE_MEASURE_SURFACES = {
    "financing_amount": {"CAPITAL_ACTIONS"},
    "revenue": {"PERIODIC_FINANCIALS", "COMMERCIAL_OPERATIONS"},
    "net_profit_parent": {"PERIODIC_FINANCIALS"},
    "operating_cash_flow": {"PERIODIC_FINANCIALS"},
    "cash_balance": {"PERIODIC_FINANCIALS"},
    "accounts_receivable": {"PERIODIC_FINANCIALS"},
    "contract_liabilities": {"PERIODIC_FINANCIALS"},
    "capex": {"PERIODIC_FINANCIALS", "COMMERCIAL_OPERATIONS"},
    "order_amount": {"COMMERCIAL_OPERATIONS", "CAPITAL_ACTIONS"},
    "contract_amount": {"COMMERCIAL_OPERATIONS", "CAPITAL_ACTIONS"},
    "buyback_amount": {"CAPITAL_ACTIONS"},
    "gross_margin": {"PERIODIC_FINANCIALS"},
    "net_margin": {"PERIODIC_FINANCIALS"},
    "debt_ratio": {"PERIODIC_FINANCIALS"},
    "pledge_ratio": {"OWNERSHIP_CONTROL"},
    "utilization_rate": {"COMMERCIAL_OPERATIONS"},
    "market_share": {"COMMERCIAL_OPERATIONS"},
    "unlock_shares": {"CAPITAL_ACTIONS"},
    "holdings_change_shares": {"OWNERSHIP_CONTROL", "CAPITAL_ACTIONS"},
    "share_count": {"CAPITAL_ACTIONS", "PERIODIC_FINANCIALS"},
    "capacity_count": {"COMMERCIAL_OPERATIONS"},
    "shipment_count": {"COMMERCIAL_OPERATIONS"},
    "duration_days": {"COMMERCIAL_OPERATIONS", "LEGAL_REGULATORY", "CAPITAL_ACTIONS"},
}
MEASURE_INPUT_FIELDS = {
    "measure_id", "metric", "value", "unit", "dimension", "subject_id",
    "as_of", "period", "basis", "definition",
}
EVIDENCE_INPUT_FIELDS = {
    "evidence_id", "claim", "number", "measures", "roles", "source",
    "publisher", "url", "date", "source_tier", "boundary",
    "evidence_boundary", "decision_impact", "entity_ids", "security_ids",
    "fact_surface", "claim_ids", "origin", "document_facts",
}
DOCUMENT_FACT_FIELDS = {
    "fact_id", "fact_type", "locator", "excerpt", "document_sha256",
    "event_type", "event_anchor",
}
NUMERIC_UNIT_RE = re.compile(
    r"(?<![A-Za-z0-9.])(?:[¥￥$]\s*)?"
    r"([+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
    r"(?:[eE][+-]?\d+)?)\s*"
    r"(万亿元|万亿|亿元|亿股|亿|万元|万股|元|个百分点|百分点|"
    r"个交易日|交易日|日|个季度|季度|个月|月|年|轮|%|％|‰|"
    r"bps?|BPS?|basispoints?|倍|[xX]|点|股|天|人民币|美元|美金|港元|"
    r"CNY|RMB|USD|HKD)"
)
CHINESE_NUMERIC_UNIT_RE = re.compile(
    r"(?:(?:百分之|千分之)(?:负|正)?"
    r"(?=[零〇一二两三四五六七八九十百千万亿点壹贰叁肆伍陆柒捌玖拾佰仟萬億點]*"
    r"[零〇一二两三四五六七八九十百千点壹贰叁肆伍陆柒捌玖拾佰仟點])"
    r"[零〇一二两三四五六七八九十百千万亿点壹贰叁肆伍陆柒捌玖拾佰仟萬億點]+|"
    r"(?:负|正)?"
    r"(?=[零〇一二两三四五六七八九十百千万亿点壹贰叁肆伍陆柒捌玖拾佰仟萬億點]*"
    r"[零〇一二两三四五六七八九十百千点壹贰叁肆伍陆柒捌玖拾佰仟點])"
    r"[零〇一二两三四五六七八九十百千万亿点壹贰叁肆伍陆柒捌玖拾佰仟萬億點]+\s*"
    r"(?:万亿元|万亿|亿元|亿股|亿|万元|万股|元|个百分点|百分点|"
    r"个交易日|交易日|日|个季度|季度|个月|月|年|轮|倍|点|股|天|"
    r"人民币|美元|美金|港元))"
)
NUMERIC_FRACTION_RE = re.compile(
    r"(?<![A-Za-z0-9.])(?:\d+(?:\.\d+)?\s*/\s*\d+(?:\.\d+)?|"
    r"\d+(?:\.\d+)?[eE][+-]?\d+)(?![A-Za-z0-9.])"
)
CURRENCY_PREFIX_RE = re.compile(
    r"(?:[¥￥$]\s*[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"
)
OFFICIAL_INDEX_WINDOW_BASIS = "LATEST_PERIODIC_REPORT_OR_120D"
SNAPSHOT_FIELDS = {
    "schema_version", "version", "base_snapshot_sha256", "as_of",
    "decision_status", "core_judgment", "boundary", "material_changes",
    "open_material_gaps", "agenda_answers", "value_transfer_paths",
    "market_by_horizon", "market_carriers_by_horizon",
    "candidates_by_horizon", "self_countercases",
    "challenge_resolutions", "unresolved_questions",
    "lowest_cost_next_validation", "consumed_evidence_ids",
    "non_material_evidence_dispositions",
}
LEAD_PACKET_FIELDS = {
    "action_intent", "evidence_items", "source_checks", "decision_snapshot",
    "challenge_request", "continue_research", "stop_reason",
}
CHALLENGE_PACKET_FIELDS = {
    "challenge_id", "target_claim_ids", "evidence_items", "source_checks", "attacks",
    "strongest_countercase",
}
SNAPSHOT_ITEM_FIELDS = {
    "core_judgment": {"claim_id", "summary", "boundary", "evidence_ids"},
    "material_changes": {
        "change_id", "claim_id", "title", "summary", "decision_effect",
        "boundary", "evidence_ids",
    },
    "open_material_gaps": {"gap_id", "description", "evidence_ids"},
    "agenda_answers": {
        "question_id", "question", "status", "answer", "boundary",
        "evidence_ids", "self_countercase", "missing_information",
        "next_test_availability",
    },
    "value_transfer_paths": {
        "path_id", "claim_id", "constraint_change", "profit_pool_shift",
        "economic_exposure", "market_carrier", "boundary", "evidence_ids",
    },
    "market_by_horizon": {
        "market_view_id", "claim_id", "horizon", "current_state", "mechanism",
        "switch_condition", "boundary", "evidence_ids",
    },
    "market_carrier_group": {"horizon", "carriers"},
    "market_carrier": {
        "claim_id", "name", "ticker", "exchange", "market_role", "why_traded",
        "closest_alternative", "switch_condition", "boundary",
        "market_evidence_ids", "alternative_evidence_ids", "evidence_ids",
    },
    "candidate_group": {"horizon", "candidates"},
    "candidate": {
        "claim_id", "stance", "name", "ticker", "exchange",
        "economic_exposure", "market_role", "why_now", "closest_alternative",
        "switch_condition", "trigger", "invalidation", "price_crowding_boundary",
        "boundary", "value_path_ids", "exposure_evidence_ids",
        "market_evidence_ids", "alternative_evidence_ids", "evidence_ids",
    },
    "self_countercases": {"claim_id", "target_claim_id", "argument", "evidence_ids"},
    "challenge_resolutions": {
        "challenge_id", "challenge_packet_sha256", "target_claim_ids", "resolution",
        "summary", "lead_response", "evidence_ids",
    },
    "unresolved_questions": {
        "question_id", "gap_id", "question", "description", "evidence_ids",
    },
    "lowest_cost_next_validation": {
        "action", "availability", "expected_decision_delta", "evidence_ids",
    },
    "non_material_disposition": {
        "evidence_id", "event_family_id", "decision_dimension", "reason",
        "reversal_condition",
    },
}
SNAPSHOT_LIST_LIMITS = {
    "material_changes": 40,
    "open_material_gaps": 40,
    "agenda_answers": 12,
    "value_transfer_paths": 24,
    "market_by_horizon": 4,
    "market_carriers_by_horizon": 4,
    "candidates_by_horizon": 4,
    "self_countercases": 24,
    "challenge_resolutions": 10,
    "unresolved_questions": 24,
    "lowest_cost_next_validation": 20,
    "non_material_evidence_dispositions": 80,
}
RUN_FIELDS = {
    "schema_version", "task_spec", "evidence_store", "decision_snapshot", "run_ledger",
}
TASK_FIELDS = {
    "schema_version", "question", "as_of", "horizons", "budget",
    "primary_entities", "questions", "output_contract", "non_goals",
}
EVIDENCE_STORE_FIELDS = {"schema_version", "items", "source_checks", "aliases"}
LEDGER_FIELDS = {
    "schema_version", "method_identity", "execution_mode",
    "authorized_research_loops", "completed_research_loops", "state_revision",
    "action_intents", "calls", "rejections", "failures", "challenge_packets", "next_call",
    "stopped_reason", "task_spec_sha256", "evidence_store_sha256",
    "decision_snapshot_sha256", "pending_dispatch", "pending_challenge_request",
    "seed_input", "host_inputs", "host_invocations", "retry_call",
}
LEDGER_OPTIONAL_FIELDS = {
    "pending_dispatch", "pending_challenge_request", "seed_input", "retry_call",
}
ACTION_RECORD_FIELDS = {
    "action_id", "action_type", "target_snapshot_field", "current_uncertainty",
    "evidence_needed", "expected_decision_delta", "stop_condition", "cost_bound",
    "status", "evidence_ids", "source_check_ids", "base_snapshot_sha256",
    "snapshot_version", "snapshot_sha256", "submission_payload_sha256",
    "snapshot_frontier",
}
SNAPSHOT_FRONTIER_FIELDS = {
    "evidence_count", "source_check_count", "challenge_count",
    "evidence_prefix_sha256", "source_check_prefix_sha256",
    "challenge_prefix_sha256",
}
CALL_RECORD_FIELDS = {
    "receipt_id", "role", "status", "action_id", "challenge_id",
    "prompt_sha256", "payload_sha256", "agent_id", "isolation", "mode",
    "receipt_provenance", "process_id", "host_runtime", "external_tools_enabled",
    "parent_agent_id", "attestation_level",
}
FAILURE_RECORD_FIELDS = {
    "role", "call_mode", "reason", "receipt_id", "prompt_sha256",
    "base_snapshot_sha256",
}
REJECTION_RECORD_FIELDS = {
    "rejection_id", "role", "call_mode", "prompt_sha256", "payload_sha256",
    "agent_id", "isolation", "receipt_provenance", "process_id",
    "host_runtime", "external_tools_enabled", "base_snapshot_sha256", "errors",
    "parent_agent_id", "attestation_level",
}
CHALLENGE_RECORD_FIELDS = {
    "challenge_id", "target_claim_ids", "attacks", "evidence_ids",
    "source_check_ids", "submission_payload_sha256", "strongest_countercase",
}
CHALLENGE_ATTACK_FIELDS = {
    "target_claim_id", "argument", "evidence_ids", "severity",
}
PENDING_DISPATCH_FIELDS = {
    "call_mode", "role", "prompt_sha256", "base_snapshot_sha256",
}
PENDING_CHALLENGE_FIELDS = {
    "challenge_id", "target_claim_ids", "question", "why_load_bearing",
    "snapshot_sha256",
}
SEED_INPUT_FIELDS = {"evidence_ids", "source_check_ids", "content_sha256"}
HOST_INPUT_FIELDS = {
    "input_id", "evidence_ids", "source_check_ids", "content_sha256",
}
HOST_INVOCATION_FIELDS = {
    "invocation_id", "role", "host_runtime", "host_executable", "process_id",
    "exit_code", "timed_out", "prompt_sha256", "payload_sha256",
    "external_tools_enabled",
}
INDEX_ENTRY_FIELDS = {"title", "url", "date", "disposition", "reason"}
MAX_INDEX_ENTRIES = 1000
LEAD_CALL_MODES = {"LEAD_RESEARCH", "LEAD_SYNTHESIS", "LEAD_RESOLUTION"}
ALL_CALL_MODES = LEAD_CALL_MODES | {"CHALLENGER"}
EXECUTION_MODES = {
    "UNVERIFIED", "HARNESS_ORCHESTRATED", "EXTERNAL_PROCESS_REPORTED",
    "CONTROLLED_FIXTURE",
}

LISTED_COMPANY_FACT_SURFACES = (
    "OFFICIAL_DISCLOSURE_INDEX",
    "PERIODIC_FINANCIALS",
    "COMMERCIAL_OPERATIONS",
    "OWNERSHIP_CONTROL",
    "CAPITAL_ACTIONS",
    "LEGAL_REGULATORY",
    "MARKET_PRICE_LIQUIDITY",
)
PROJECT_FACT_SURFACES = (
    "OFFICIAL_STATUS_TIMELINE",
    "TECHNICAL_MILESTONES",
    "COMMERCIAL_OPERATIONS",
    "CAPITAL_ACTIONS",
    "LEGAL_REGULATORY",
)
THEME_FACT_SURFACES = (
    "OFFICIAL_POLICY_DATA",
    "SUPPLY_DEMAND_REALITY",
    "MARKET_CARRIER_CHANGES",
    "RISKS_ALTERNATIVES",
)

ID_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+$")
METRIC_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
TICKER_RE = re.compile(r"^[A-Z0-9.]{1,24}$")
SECURITY_ID_RE = re.compile(r"^[A-Z0-9.]{1,24}@[A-Z0-9._-]{1,16}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DOCUMENT_ACQUISITION_ID_RE = re.compile(r"^docsha256:([0-9a-f]{64})$")
MARKET_FACT_SURFACES = {"MARKET_PRICE_LIQUIDITY", "MARKET_CARRIER_CHANGES"}
EXCHANGE_ALIASES = {
    "SH": "XSHG", "SSE": "XSHG", "SHSE": "XSHG", "XSHG": "XSHG",
    "SZ": "XSHE", "SZSE": "XSHE", "XSHE": "XSHE",
    "BJ": "XBEI", "BSE": "XBEI", "BJSE": "XBEI", "XBEI": "XBEI",
}
PLACEHOLDER_HOSTS = {
    "example.com", "www.example.com", "example.org", "www.example.org",
    "example.net", "www.example.net", "localhost", "127.0.0.1",
}
MATERIAL_TITLE_MARKERS = tuple(dict.fromkeys(
    marker for _, markers in MATERIAL_EVENT_RULES for marker in markers
))


class ResearchContractError(ValueError):
    """One or more deterministic research contracts were violated."""

    def __init__(self, errors):
        self.errors = sorted(set(str(item) for item in errors if str(item)))
        super().__init__("; ".join(self.errors))


def text(value):
    return " ".join(str(value or "").split())


def _semantic_text(value):
    return re.sub(
        r"[^0-9A-Za-z\u3400-\u9fff]+", "",
        unicodedata.normalize("NFKC", text(value)).lower(),
    )


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def stable_id(prefix, *parts, length=14):
    digest = hashlib.sha256(
        "|".join(text(part).lower() for part in parts).encode("utf-8")
    ).hexdigest()[:length].upper()
    return f"{prefix}-{digest}"


def material_event_type(title):
    """Classify a potentially decision-changing disclosure title."""
    normalized = text(title)
    for event_type, markers in MATERIAL_EVENT_RULES:
        if any(marker in normalized for marker in markers):
            return event_type
    return ""


def normalize_document_fact(raw, *, index=1):
    """Normalize one host-bound body excerpt without interpreting its meaning."""
    raw = raw if isinstance(raw, dict) else {}
    errors = []
    unknown = set(raw) - DOCUMENT_FACT_FIELDS
    missing = DOCUMENT_FACT_FIELDS - set(raw)
    if unknown or missing:
        errors.append(
            "document_fact.fields_invalid:unknown=" + ",".join(sorted(unknown))
            + ":missing=" + ",".join(sorted(missing))
        )
    fact_type = _enum(raw.get("fact_type"), DOCUMENT_FACT_TYPES)
    locator = text(raw.get("locator"))
    excerpt = text(raw.get("excerpt"))
    document_sha256 = text(raw.get("document_sha256")).lower()
    event_type = text(raw.get("event_type")).upper()
    event_anchor = text(raw.get("event_anchor")).upper()
    if not fact_type:
        errors.append(f"document_fact.fact_type_invalid:{index}")
    if len(_semantic_text(locator)) < 3:
        errors.append(f"document_fact.locator_required:{index}")
    if len(_semantic_text(excerpt)) < 12:
        errors.append(f"document_fact.excerpt_too_shallow:{index}")
    if not SHA256_RE.fullmatch(document_sha256):
        errors.append(f"document_fact.document_sha256_required:{index}")
    if event_type not in {item[0] for item in MATERIAL_EVENT_RULES}:
        errors.append(f"document_fact.event_type_invalid:{index}")
    if not re.fullmatch(r"[A-Z0-9._:/@-]{3,160}", event_anchor):
        errors.append(f"document_fact.event_anchor_invalid:{index}")
    fact_id = text(raw.get("fact_id")).upper() or stable_id(
        "DF", document_sha256, locator, event_type, event_anchor
    )
    if not ID_RE.fullmatch(fact_id):
        errors.append(f"document_fact.id_invalid:{index}")
    if errors:
        raise ResearchContractError(errors)
    return {
        "fact_id": fact_id,
        "fact_type": fact_type,
        "locator": locator,
        "excerpt": excerpt,
        "document_sha256": document_sha256,
        "event_type": event_type,
        "event_anchor": event_anchor,
    }


def parse_iso_date(value):
    try:
        return date.fromisoformat(text(value))
    except (TypeError, ValueError):
        return None


def concrete_url(value):
    raw = text(value)
    try:
        parsed = urlparse(raw)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    return (
        parsed.scheme in {"http", "https"}
        and bool(host)
        and host not in PLACEHOLDER_HOSTS
        and not host.endswith(".example.com")
    )


def _unique_text(values, limit=None):
    result = []
    for value in values if isinstance(values, list) else []:
        rendered = text(value)
        if rendered and rendered not in result:
            result.append(rendered)
        if limit is not None and len(result) >= limit:
            break
    return result


def _enum(value, allowed, default=""):
    normalized = text(value).upper()
    return normalized if normalized in allowed else default


def normalize_exchange(value):
    normalized = text(value).upper()
    return EXCHANGE_ALIASES.get(normalized, normalized)


def normalize_security_id(value):
    raw = text(value).upper()
    if "@" not in raw:
        return raw
    ticker, exchange = raw.rsplit("@", 1)
    return f"{ticker}@{normalize_exchange(exchange)}"


def entity_security_id(entity):
    """Return the canonical security identity owned by a listed TaskSpec entity."""
    if not isinstance(entity, dict) or entity.get("entity_type") != "LISTED_COMPANY":
        return ""
    security_id = normalize_security_id(
        f"{text(entity.get('ticker')).upper()}@{normalize_exchange(entity.get('exchange'))}"
    )
    return security_id if SECURITY_ID_RE.fullmatch(security_id) else ""


def _reject_unknown_keys(value, allowed, errors, path):
    if not isinstance(value, dict):
        errors.append(f"snapshot.item_must_be_object:{path}")
        return
    unknown = set(value) - set(allowed)
    if unknown:
        errors.append(
            f"snapshot.unknown_item_fields:{path}:" + ",".join(sorted(unknown))
        )


def _validate_exact_record(value, fields, errors, path):
    """Reject ledger records that could hide a second, unvalidated truth."""
    if not isinstance(value, dict):
        errors.append(f"persisted.{path}_must_be_object")
        return False
    unknown = set(value) - set(fields)
    missing = set(fields) - set(value)
    if unknown or missing:
        errors.append(
            f"persisted.{path}_fields_invalid:unknown="
            + ",".join(sorted(unknown))
            + ":missing=" + ",".join(sorted(missing))
        )
        return False
    return True


def _fact_surfaces(entity_type):
    if entity_type == "LISTED_COMPANY":
        return list(LISTED_COMPANY_FACT_SURFACES)
    if entity_type in {"PRIVATE_COMPANY", "PROJECT", "EVENT", "TECHNOLOGY"}:
        return list(PROJECT_FACT_SURFACES)
    return list(THEME_FACT_SURFACES)


def task_spec_from_frame(frame, *, question="", round_budget=1):
    """Convert a v0.16 frame into the thin v0.18 TaskSpec input contract."""
    frame = frame if isinstance(frame, dict) else {}
    workplan = frame.get("research_workplan")
    workplan = workplan if isinstance(workplan, dict) else {}
    horizons = _unique_text(frame.get("horizons", []))
    if not horizons:
        old_horizon = text(frame.get("horizon")).upper()
        horizons = [item for item in HORIZONS if item in old_horizon]
    if not horizons:
        horizons = list(HORIZONS)
    return {
        "question": text(frame.get("decision_question") or question),
        "as_of": text(frame.get("as_of_date")),
        "horizons": horizons,
        "budget": int(round_budget),
        "primary_entities": deepcopy(workplan.get("primary_entities") or []),
        "questions": deepcopy(workplan.get("questions") or []),
        "output_contract": "DEEP_RESEARCH_REPORT",
        "non_goals": [
            "orders", "positions", "portfolio", "target_price", "publication", "handoff",
        ],
    }


def normalize_task_spec(raw, *, fallback_question="", round_budget=None):
    raw = raw if isinstance(raw, dict) else {}
    errors = []
    question = text(raw.get("question") or fallback_question)
    if not question:
        errors.append("task_spec.question_required")
    as_of = text(raw.get("as_of") or raw.get("as_of_date"))
    if parse_iso_date(as_of) is None:
        errors.append("task_spec.as_of_requires_iso_date")
    try:
        budget = int(raw.get("budget") if round_budget is None else round_budget)
    except (TypeError, ValueError):
        budget = -1
    if not 0 <= budget <= 10:
        errors.append("task_spec.budget_requires_0_to_10")

    horizons = []
    for value in raw.get("horizons", []) if isinstance(raw.get("horizons"), list) else []:
        horizon = text(value).upper()
        if horizon not in HORIZONS:
            errors.append(f"task_spec.invalid_horizon:{horizon or 'EMPTY'}")
        elif horizon not in horizons:
            horizons.append(horizon)
    if not horizons:
        horizons = list(HORIZONS)

    entities = []
    seen_entities = set()
    raw_entities = raw.get("primary_entities")
    raw_entities = raw_entities if isinstance(raw_entities, list) else []
    if len(raw_entities) > 8:
        errors.append("task_spec.primary_entities_limit_8")
    for index, value in enumerate(raw_entities[:8], start=1):
        if not isinstance(value, dict):
            errors.append(f"task_spec.entity_{index}_must_be_object")
            continue
        name = text(value.get("name"))
        entity_type = _enum(value.get("entity_type"), ENTITY_TYPES, "OTHER")
        entity_id = text(value.get("entity_id")) or f"E{index}"
        if not name:
            errors.append(f"task_spec.entity_{index}_name_required")
        if entity_id in seen_entities:
            errors.append(f"task_spec.duplicate_entity_id:{entity_id}")
        seen_entities.add(entity_id)
        ticker = text(value.get("ticker")).upper()
        exchange = normalize_exchange(value.get("exchange"))
        if entity_type == "LISTED_COMPANY" and (
            not TICKER_RE.fullmatch(ticker) or not exchange
        ):
            errors.append(f"task_spec.listed_entity_identity_required:{entity_id}")
        requested_surfaces = [
            item.upper() for item in _unique_text(value.get("fact_surfaces", []), limit=16)
        ]
        # A model may add a task-specific surface, but it may not delete the
        # deterministic minimum fact surface for the entity type.
        fact_surfaces = list(dict.fromkeys(
            _fact_surfaces(entity_type) + requested_surfaces
        ))
        entities.append({
            "entity_id": entity_id,
            "name": name,
            "entity_type": entity_type,
            "ticker": ticker,
            "exchange": exchange,
            "fact_surfaces": fact_surfaces,
        })
    if not entities:
        entities.append({
            "entity_id": "E1",
            "name": question[:120] or "research subject",
            "entity_type": "OTHER",
            "ticker": "",
            "exchange": "",
            "fact_surfaces": list(THEME_FACT_SURFACES),
        })

    questions = []
    seen_questions = set()
    raw_questions = raw.get("questions")
    raw_questions = raw_questions if isinstance(raw_questions, list) else []
    if len(raw_questions) > 12:
        errors.append("task_spec.questions_limit_12")
    for index, value in enumerate(raw_questions[:12], start=1):
        if isinstance(value, str):
            value = {"question": value}
        if not isinstance(value, dict) or not text(value.get("question")):
            continue
        question_id = text(value.get("question_id")) or f"RQ{index}"
        if question_id in seen_questions:
            errors.append(f"task_spec.duplicate_question_id:{question_id}")
            continue
        seen_questions.add(question_id)
        questions.append({
            "question_id": question_id,
            "question": text(value.get("question")),
            "why_it_matters": text(value.get("why_it_matters")),
            "decision_impact": _enum(
                value.get("decision_impact"), DECISION_IMPACTS, "MEDIUM"
            ),
        })
    if not questions:
        questions.append({
            "question_id": "RQ1",
            "question": question,
            "why_it_matters": "直接回答用户问题。",
            "decision_impact": "HIGH",
        })

    if errors:
        raise ResearchContractError(errors)
    return {
        "schema_version": TASK_SCHEMA,
        "question": question,
        "as_of": as_of,
        "horizons": horizons,
        "budget": budget,
        "primary_entities": entities,
        "questions": questions,
        "output_contract": text(raw.get("output_contract") or "DEEP_RESEARCH_REPORT"),
        "non_goals": _unique_text(raw.get("non_goals", []), limit=16) or [
            "orders", "positions", "portfolio", "target_price", "publication", "handoff",
        ],
    }


def new_evidence_store():
    return {
        "schema_version": EVIDENCE_STORE_SCHEMA,
        "items": [],
        "source_checks": [],
        "aliases": {},
    }


def _default_evidence_roles(fact_surface):
    surface = text(fact_surface).upper()
    roles = []
    if surface in MARKET_FACT_SURFACES or any(
        marker in surface for marker in ("MARKET", "PRICE", "LIQUIDITY", "STYLE")
    ):
        roles.append("MARKET_STATE")
    else:
        roles.append("CURRENT_REALITY")
    if any(marker in surface for marker in (
        "FINANCIAL", "COMMERCIAL", "CAPITAL", "OPERATIONS", "CUSTOMER",
        "REVENUE", "PROFIT", "CASH", "REALIZATION",
    )):
        roles.append("ECONOMIC_EXPOSURE")
    if any(marker in surface for marker in (
        "CHIP", "TREND", "MOMENTUM", "VOLATILITY",
    )):
        roles.append("TECHNICAL_STATE")
    if any(marker in surface for marker in ("EVENT", "CATALYST", "CALENDAR")):
        roles.append("CATALYST")
    if any(marker in surface for marker in ("RISK", "LEGAL", "REGULATORY")):
        roles.append("RISK")
    return list(dict.fromkeys(roles))


def normalize_measure(raw, *, as_of, index=1, allowed_subject_ids=()):
    raw = raw if isinstance(raw, dict) else {}
    metric = text(raw.get("metric")).lower()
    unit = text(raw.get("unit")).upper()
    dimension = text(raw.get("dimension")).upper()
    subject_id = text(raw.get("subject_id")).upper()
    period = text(raw.get("period") or "POINT_IN_TIME").upper()
    observed = parse_iso_date(raw.get("as_of") or as_of)
    cutoff = parse_iso_date(as_of)
    value = raw.get("value")
    errors = []
    unknown_fields = set(raw) - MEASURE_INPUT_FIELDS
    if unknown_fields:
        errors.append(
            "measure.unknown_fields:" + ",".join(sorted(unknown_fields))
        )
    if not METRIC_RE.fullmatch(metric):
        errors.append(f"measure.metric_required:{index}")
    elif metric not in MEASURE_METRICS:
        errors.append(f"measure.metric_unregistered:{metric}")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors.append(f"measure.value_must_be_number:{metric or index}")
    elif not math.isfinite(float(value)):
        errors.append(f"measure.value_must_be_finite:{metric or index}")
    if unit not in MEASURE_UNITS:
        errors.append(f"measure.unit_invalid:{metric or index}")
    if dimension not in MEASURE_DIMENSIONS:
        errors.append(f"measure.dimension_invalid:{metric or index}")
    elif MEASURE_UNIT_DIMENSIONS.get(unit) != dimension:
        errors.append(
            f"measure.dimension_unit_mismatch:{metric or index}:{dimension}:{unit}"
        )
    allowed_units = MEASURE_METRIC_UNITS.get(metric, set())
    if metric in MEASURE_METRICS and unit not in allowed_units:
        errors.append(f"measure.metric_unit_mismatch:{metric}:{unit}")
    normalized_subjects = {text(item).upper() for item in allowed_subject_ids}
    if not subject_id or subject_id not in normalized_subjects:
        errors.append(f"measure.subject_invalid:{metric or index}:{subject_id or 'EMPTY'}")
    if period not in MEASURE_PERIODS:
        errors.append(f"measure.period_invalid:{metric or index}")
    if observed is None:
        errors.append(f"measure.as_of_invalid:{metric or index}")
    elif cutoff is not None and observed > cutoff:
        errors.append(f"measure.after_as_of:{metric or index}")
    basis = text(raw.get("basis")).upper()
    if basis not in MEASURE_BASES:
        errors.append(f"measure.basis_unregistered:{metric or index}:{basis or 'EMPTY'}")
    canonical_definition = (
        MEASURE_METRICS.get(metric, ("", set()))[0]
    )
    supplied_definition = text(raw.get("definition"))
    if supplied_definition and supplied_definition != canonical_definition:
        errors.append(f"measure.definition_registry_mismatch:{metric or index}")
    measure_id = text(raw.get("measure_id")).upper() or stable_id(
        "MEASURE", subject_id, metric,
        observed.isoformat() if observed else as_of, period, basis
    )
    if not ID_RE.fullmatch(measure_id):
        errors.append(f"measure.id_invalid:{metric or index}")
    if errors:
        raise ResearchContractError(errors)
    return {
        "measure_id": measure_id,
        "metric": metric,
        "value": float(value),
        "unit": unit,
        "dimension": dimension,
        "subject_id": subject_id,
        "as_of": observed.isoformat(),
        "period": period,
        "basis": basis,
        "definition": canonical_definition,
    }


def _format_decimal(value, places=2):
    rendered = f"{float(value):.{places}f}".rstrip("0").rstrip(".")
    return rendered or "0"


def format_measure(measure):
    """Render a typed measure without asking a model to infer its scale."""
    value = float(measure.get("value"))
    unit = text(measure.get("unit")).upper()
    if unit == "CNY_BN":
        yi = value * 10.0
        if abs(yi) >= 10000:
            return f"{_format_decimal(yi / 10000.0, 3)}万亿元（{_format_decimal(yi)}亿元）"
        return f"{_format_decimal(yi)}亿元"
    if unit == "CNY_100M":
        if abs(value) >= 10000:
            return f"{_format_decimal(value / 10000.0, 3)}万亿元（{_format_decimal(value)}亿元）"
        return f"{_format_decimal(value)}亿元"
    if unit == "CNY_10K":
        if abs(value) >= 10000:
            return f"{_format_decimal(value / 10000.0)}亿元（{_format_decimal(value)}万元）"
        return f"{_format_decimal(value)}万元"
    if unit == "CNY":
        if abs(value) >= 100000000:
            return f"{_format_decimal(value / 100000000.0)}亿元"
        if abs(value) >= 10000:
            return f"{_format_decimal(value / 10000.0)}万元"
        return f"{_format_decimal(value)}元"
    suffix = {
        "PERCENT": "%", "RATIO": "倍", "POINTS": "点", "SHARES": "股",
        "COUNT": "", "DAYS": "天",
    }.get(unit, f" {unit}")
    return f"{_format_decimal(value, 6)}{suffix}"


def _numeric_scan_text(value):
    """Collapse presentation-only separators before looking for numeric prose."""
    value = str(value or "")
    # Decode named and numeric entities before stripping presentation markup.
    # Two passes cover nested escaping without turning this into an HTML parser.
    for _ in range(2):
        decoded = html.unescape(value)
        if decoded == value:
            break
        value = decoded
    value = unicodedata.normalize("NFKC", value)
    value = "".join(
        character for character in value
        if unicodedata.category(character) not in {"Cf", "Mn"}
    )
    value = re.sub(r"<!--.*?-->", "", value, flags=re.S)
    value = re.sub(r"<[^>]*>", "", value)
    value = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"\\(?=[%％¥￥$])", "", value)
    # Emphasis/code markers can visually join a value and unit.  Removing only
    # presentation punctuation preserves ordinary language and source names.
    value = re.sub(r"[`*_~]", "", value)
    return value


def validate_numeric_text(text_value, measures, *, path, errors):
    """Reject model-authored values; typed measures are the sole numeric truth."""
    value = _numeric_scan_text(text_value)
    matches = [match.group(0) for match in NUMERIC_UNIT_RE.finditer(value)]
    matches.extend(
        match.group(0) for match in CHINESE_NUMERIC_UNIT_RE.finditer(value)
    )
    matches.extend(match.group(0) for match in NUMERIC_FRACTION_RE.finditer(value))
    matches.extend(match.group(0) for match in CURRENCY_PREFIX_RE.finditer(value))
    for literal in dict.fromkeys(matches):
        errors.append(
            f"numeric_literal.must_be_rendered_from_measure:{path}:{literal}"
        )


def new_run_ledger(method_identity, budget, *, execution_mode="UNVERIFIED"):
    execution_mode = text(execution_mode).upper() or "UNVERIFIED"
    if execution_mode not in EXECUTION_MODES:
        raise ResearchContractError(["run_ledger.execution_mode_invalid"])
    if not isinstance(method_identity, dict):
        raise ResearchContractError(["run_ledger.method_identity_required"])
    return {
        "schema_version": LEDGER_SCHEMA,
        "method_identity": deepcopy(method_identity),
        "execution_mode": execution_mode,
        "authorized_research_loops": int(budget),
        "completed_research_loops": 0,
        "state_revision": 0,
        "action_intents": [],
        "calls": [],
        "rejections": [],
        "failures": [],
        "challenge_packets": [],
        "host_inputs": [],
        "host_invocations": [],
        "next_call": "LEAD_RESEARCH" if int(budget) > 0 else "LEAD_SYNTHESIS",
        "stopped_reason": "",
    }


def empty_snapshot(task_spec):
    return {
        "schema_version": SNAPSHOT_SCHEMA,
        "version": 0,
        "base_snapshot_sha256": "",
        "as_of": task_spec["as_of"],
        "decision_status": "RESEARCH_INCOMPLETE",
        "core_judgment": {
            "claim_id": "CORE-1",
            "summary": "尚未形成研究判断。",
            "boundary": "HYPOTHESIS",
            "evidence_ids": [],
        },
        "boundary": "尚未完成必要事实面。",
        "material_changes": [],
        "open_material_gaps": [],
        "agenda_answers": [],
        "value_transfer_paths": [],
        "market_by_horizon": [],
        "market_carriers_by_horizon": [],
        "candidates_by_horizon": [],
        "self_countercases": [],
        "challenge_resolutions": [],
        "unresolved_questions": [],
        "lowest_cost_next_validation": [],
        "consumed_evidence_ids": [],
        "non_material_evidence_dispositions": [],
    }


def new_research_run(task_spec, method_identity, *, execution_mode="UNVERIFIED"):
    run = {
        "schema_version": RUN_SCHEMA,
        "task_spec": deepcopy(task_spec),
        "evidence_store": new_evidence_store(),
        "decision_snapshot": empty_snapshot(task_spec),
        "run_ledger": new_run_ledger(
            method_identity, task_spec["budget"], execution_mode=execution_mode
        ),
    }
    run["run_ledger"]["task_spec_sha256"] = stable_hash(run["task_spec"])
    run["run_ledger"]["evidence_store_sha256"] = stable_hash(
        run["evidence_store"]
    )
    run["run_ledger"]["decision_snapshot_sha256"] = snapshot_hash(
        run["decision_snapshot"]
    )
    return run


def _host_input_content_hash(store, evidence_ids, source_check_ids):
    checks = {
        item.get("source_check_id"): item
        for item in store.get("source_checks", []) if isinstance(item, dict)
    }
    return stable_hash({
        "evidence_bindings": [
            {
                "evidence_id": evidence_id,
                "content_sha256": stable_hash(evidence_index(store)[evidence_id]),
            }
            for evidence_id in evidence_ids
        ],
        "source_check_bindings": [
            {
                "source_check_id": check_id,
                "content_sha256": stable_hash(checks[check_id]),
            }
            for check_id in source_check_ids if check_id in checks
        ],
    })


def seed_research_run(run, evidence_items=None, source_checks=None):
    """Append explicit user/host-supplied observations before the first dispatch."""
    validate_run_shape(run)
    if (
        run["decision_snapshot"].get("version") != 0
        or run["run_ledger"].get("calls")
        or run["run_ledger"].get("pending_dispatch")
    ):
        raise ResearchContractError(["seed.only_before_first_dispatch"])
    updated = deepcopy(run)
    seeded = []
    for raw in evidence_items if isinstance(evidence_items, list) else []:
        item = deepcopy(raw) if isinstance(raw, dict) else raw
        if isinstance(item, dict):
            item["origin"] = "USER_OR_HOST_SEED"
        seeded.append(item)
    existing_evidence_ids = set(evidence_index(updated["evidence_store"]))
    store, evidence_ids = append_evidence_items(
        updated["evidence_store"], seeded, as_of=updated["task_spec"]["as_of"]
    )
    store, source_check_ids = append_source_checks(
        store, source_checks or [], task_spec=updated["task_spec"],
        origin="HOST_INPUT",
    )
    require_new_evidence_bound(
        store, set(evidence_index(store)) - existing_evidence_ids, source_check_ids
    )
    validate_document_fact_acquisition(store)
    validate_evidence_scope(updated["task_spec"], store)
    updated["evidence_store"] = store
    ledger = updated["run_ledger"]
    ledger["evidence_store_sha256"] = stable_hash(store)
    ledger["seed_input"] = {
        "evidence_ids": evidence_ids,
        "source_check_ids": source_check_ids,
        "content_sha256": _host_input_content_hash(
            store, evidence_ids, source_check_ids
        ),
    }
    return updated


def ingest_host_evidence(run, evidence_items=None, source_checks=None, *, input_id=""):
    """Append a host-acquired evidence fragment between model calls.

    This is an EvidenceStore append, not a semantic transition: it cannot write
    DecisionSnapshot or consume research budget.  It exists so a host can freeze
    market/disclosure data for candidates discovered during an earlier Lead call.
    """
    # Host evidence is allowed to make the current Snapshot stale.  Validate
    # structural and hash lineage first, but do not re-judge old semantics
    # against observations that have not been appended yet.
    validate_persisted_run(run, require_written_snapshot=False)
    ledger = run["run_ledger"]
    if ledger.get("next_call") not in {"LEAD_RESEARCH", "LEAD_SYNTHESIS"}:
        raise ResearchContractError(["host_input.requires_lead_call"])
    updated = deepcopy(run)
    # A dispatch may already have been compiled optimistically after the prior
    # packet.  No model call has occurred yet; discard that stale prompt binding
    # and let the runtime compile a new one after this EvidenceStore append.
    updated["run_ledger"].pop("pending_dispatch", None)
    seeded = []
    for raw in evidence_items if isinstance(evidence_items, list) else []:
        item = deepcopy(raw) if isinstance(raw, dict) else raw
        if isinstance(item, dict):
            item["origin"] = "USER_OR_HOST_SEED"
        seeded.append(item)
    before_evidence = set(evidence_index(updated["evidence_store"]))
    before_checks = {
        item.get("source_check_id")
        for item in updated["evidence_store"].get("source_checks", [])
        if isinstance(item, dict)
    }
    store, _ = append_evidence_items(
        updated["evidence_store"], seeded, as_of=updated["task_spec"]["as_of"]
    )
    store, _ = append_source_checks(
        store, source_checks or [], task_spec=updated["task_spec"],
        origin="HOST_INPUT",
    )
    evidence_ids = sorted(set(evidence_index(store)) - before_evidence)
    source_check_ids = sorted({
        item.get("source_check_id")
        for item in store.get("source_checks", []) if isinstance(item, dict)
    } - before_checks)
    if not evidence_ids and not source_check_ids:
        raise ResearchContractError(["host_input.requires_new_observation"])
    require_new_evidence_bound(store, evidence_ids, source_check_ids)
    validate_document_fact_acquisition(store)
    validate_evidence_scope(updated["task_spec"], store)
    normalized_input_id = text(input_id).upper() or stable_id(
        "HOST", stable_hash({
            "evidence_ids": evidence_ids,
            "source_check_ids": source_check_ids,
        })
    )
    if not ID_RE.fullmatch(normalized_input_id):
        raise ResearchContractError(["host_input.id_invalid"])
    if normalized_input_id in {
        item.get("input_id") for item in ledger.get("host_inputs", [])
        if isinstance(item, dict)
    }:
        raise ResearchContractError(["host_input.id_already_used"])
    updated["evidence_store"] = store
    updated_ledger = updated["run_ledger"]
    updated_ledger["evidence_store_sha256"] = stable_hash(store)
    updated_ledger.setdefault("host_inputs", []).append({
        "input_id": normalized_input_id,
        "evidence_ids": evidence_ids,
        "source_check_ids": source_check_ids,
        "content_sha256": _host_input_content_hash(
            store, evidence_ids, source_check_ids
        ),
    })
    # The append creates new runtime obligations for the *next* Lead.  It must
    # never force a host script to mutate DecisionSnapshot in order to persist.
    # Persisted validation therefore checks the Snapshot against its accepted
    # evidence frontier, while the WorkingSet exposes current obligations.
    return updated


def validate_run_shape(run):
    errors = []
    if not isinstance(run, dict) or run.get("schema_version") != RUN_SCHEMA:
        errors.append("run.invalid_schema")
        raise ResearchContractError(errors)
    unknown_run_fields = set(run) - RUN_FIELDS
    missing_run_fields = RUN_FIELDS - set(run)
    if unknown_run_fields or missing_run_fields:
        errors.append(
            "run.fields_invalid:unknown=" + ",".join(sorted(unknown_run_fields))
            + ":missing=" + ",".join(sorted(missing_run_fields))
        )
    expected = (
        ("task_spec", TASK_SCHEMA, TASK_FIELDS, TASK_FIELDS),
        (
            "evidence_store", EVIDENCE_STORE_SCHEMA,
            EVIDENCE_STORE_FIELDS, EVIDENCE_STORE_FIELDS,
        ),
        ("decision_snapshot", SNAPSHOT_SCHEMA, SNAPSHOT_FIELDS, SNAPSHOT_FIELDS),
        (
            "run_ledger", LEDGER_SCHEMA, LEDGER_FIELDS,
            LEDGER_FIELDS - LEDGER_OPTIONAL_FIELDS,
        ),
    )
    for key, schema, fields, required_fields in expected:
        value = run.get(key)
        if not isinstance(value, dict) or value.get("schema_version") != schema:
            errors.append(f"run.invalid_object:{key}")
        elif set(value) - fields or required_fields - set(value):
            errors.append(
                f"run.object_fields_invalid:{key}:unknown="
                + ",".join(sorted(set(value) - fields))
                + ":missing=" + ",".join(sorted(required_fields - set(value)))
            )
    if errors:
        raise ResearchContractError(errors)
    return run


def normalize_evidence_item(raw, *, as_of):
    raw = raw if isinstance(raw, dict) else {}
    errors = []
    unknown_fields = set(raw) - EVIDENCE_INPUT_FIELDS
    if unknown_fields:
        errors.append(
            "evidence.unknown_fields:" + ",".join(sorted(unknown_fields))
        )
    claim = text(raw.get("claim"))
    source = text(raw.get("source") or raw.get("publisher"))
    url = text(raw.get("url"))
    observed = parse_iso_date(raw.get("date"))
    cutoff = parse_iso_date(as_of)
    boundary = _enum(raw.get("boundary") or raw.get("evidence_boundary"), EVIDENCE_BOUNDARIES)
    impact = _enum(raw.get("decision_impact"), DECISION_IMPACTS, "MEDIUM")
    if not claim:
        errors.append("evidence.claim_required")
    if not source:
        errors.append("evidence.source_required")
    if not concrete_url(url):
        errors.append("evidence.concrete_url_required")
    if observed is None:
        errors.append("evidence.date_requires_iso")
    elif cutoff is not None and observed > cutoff:
        errors.append("evidence.after_as_of")
    if not boundary:
        errors.append("evidence.boundary_invalid")
    entity_ids = _unique_text(raw.get("entity_ids", []), limit=8)
    security_ids = list(dict.fromkeys(
        normalize_security_id(item)
        for item in _unique_text(raw.get("security_ids", []), limit=16)
    ))
    fact_surface = text(raw.get("fact_surface")).upper()
    claim_ids = _unique_text(raw.get("claim_ids", []), limit=16)
    roles = [
        text(item).upper() for item in _unique_text(raw.get("roles", []), limit=8)
    ] or _default_evidence_roles(fact_surface)
    invalid_roles = sorted(set(roles) - EVIDENCE_ROLES)
    measures = []
    raw_measures = raw.get("measures", [])
    if raw_measures is not None and not isinstance(raw_measures, list):
        errors.append("evidence.measures_must_be_list")
        raw_measures = []
    for index, raw_measure in enumerate(raw_measures or [], start=1):
        try:
            measures.append(normalize_measure(
                raw_measure, as_of=as_of, index=index,
                allowed_subject_ids=entity_ids + security_ids,
            ))
        except ResearchContractError as exc:
            errors.extend(exc.errors)
    measure_ids = [item.get("measure_id") for item in measures]
    if len(measure_ids) != len(set(measure_ids)):
        errors.append("evidence.measure_id_must_be_unique")
    measure_semantics = {}
    for measure in measures:
        semantic_key = (
            measure.get("subject_id"), measure.get("metric"),
            measure.get("as_of"), measure.get("period"),
        )
        prior = measure_semantics.get(semantic_key)
        if prior and any(
            prior.get(field) != measure.get(field)
            for field in ("value", "unit", "dimension")
        ):
            errors.append(
                "evidence.measure_semantic_conflict:" + text(measure.get("metric"))
            )
        measure_semantics[semantic_key] = measure
    document_facts = []
    raw_document_facts = raw.get("document_facts", [])
    if raw_document_facts is not None and not isinstance(raw_document_facts, list):
        errors.append("evidence.document_facts_must_be_list")
        raw_document_facts = []
    if len(raw_document_facts or []) > 16:
        errors.append("evidence.document_facts_limit_16")
    for index, raw_fact in enumerate(raw_document_facts or [], start=1):
        try:
            document_facts.append(normalize_document_fact(raw_fact, index=index))
        except ResearchContractError as exc:
            errors.extend(exc.errors)
    document_fact_ids = [item.get("fact_id") for item in document_facts]
    if len(document_fact_ids) != len(set(document_fact_ids)):
        errors.append("evidence.document_fact_id_must_be_unique")
    for measure in measures:
        metric = measure.get("metric")
        measure_date = parse_iso_date(measure.get("as_of"))
        if observed is not None and measure_date is not None and measure_date > observed:
            errors.append(f"measure.as_of_after_source_date:{metric}")
        if metric in MARKET_MEASURE_CONTRACTS:
            allowed_periods, allowed_bases = MARKET_MEASURE_CONTRACTS[metric]
            if fact_surface != "MARKET_PRICE_LIQUIDITY":
                errors.append(f"measure.market_metric_surface_mismatch:{metric}")
            if not set(roles).intersection({"MARKET_STATE", "TECHNICAL_STATE"}):
                errors.append(f"measure.market_metric_role_required:{metric}")
            if measure.get("period") not in allowed_periods:
                errors.append(f"measure.metric_period_mismatch:{metric}")
            if measure.get("basis") not in allowed_bases:
                errors.append(f"measure.metric_basis_mismatch:{metric}")
        elif metric in DISCLOSURE_MEASURE_SURFACES:
            if fact_surface not in DISCLOSURE_MEASURE_SURFACES[metric]:
                errors.append(f"measure.disclosure_metric_surface_mismatch:{metric}")
            if measure.get("basis") not in {
                "DISCLOSURE_REPORTED", "PROVIDER_REPORTED"
            }:
                errors.append(f"measure.disclosure_metric_basis_mismatch:{metric}")
            if set(roles) and set(roles).issubset({"MARKET_STATE", "TECHNICAL_STATE"}):
                errors.append(f"measure.disclosure_metric_role_mismatch:{metric}")
    if invalid_roles:
        errors.append("evidence.roles_invalid:" + ",".join(invalid_roles))
    if "number" in raw and raw.get("number") is not None:
        errors.append("evidence.number_removed_use_typed_measures")
    validate_numeric_text(claim, measures, path="evidence.claim", errors=errors)
    validate_numeric_text(source, [], path="evidence.source", errors=errors)
    if not entity_ids:
        errors.append("evidence.entity_ids_required")
    if not fact_surface:
        errors.append("evidence.fact_surface_required")
    if not claim_ids:
        errors.append("evidence.claim_ids_required")
    if any(not SECURITY_ID_RE.fullmatch(item) for item in security_ids):
        errors.append("evidence.security_ids_invalid")
    if len(security_ids) > 1:
        errors.append("evidence.security_subject_must_be_single")
    evidence_id = text(raw.get("evidence_id")).upper() or stable_id(
        "EV", url, claim, raw.get("date")
    )
    if not ID_RE.fullmatch(evidence_id):
        errors.append("evidence.id_invalid")
    if errors:
        raise ResearchContractError(errors)
    return {
        "evidence_id": evidence_id,
        "claim": claim,
        "number": None,
        "measures": measures,
        "document_facts": document_facts,
        "roles": list(dict.fromkeys(roles)),
        "source": source,
        "url": url,
        "date": observed.isoformat(),
        "source_tier": text(raw.get("source_tier") or "PUBLIC_SOURCE"),
        "boundary": boundary,
        "decision_impact": impact,
        "entity_ids": entity_ids,
        "fact_surface": fact_surface,
        "claim_ids": claim_ids,
        "security_ids": security_ids,
        "origin": text(raw.get("origin") or "LEAD_RESEARCH"),
    }


def evidence_signature(item):
    """Identity for deduplication, deliberately narrower than content lineage.

    A producer may assign a different evidence/measure ID to the same sourced
    claim.  IDs and mutable classification fields therefore cannot define
    semantic identity; conflicting content is checked separately by ``enrich``.
    Host lineage continues to hash the complete canonical EvidenceItem.
    """
    return stable_hash({
        "claim": text(item.get("claim")).lower(),
        "url": text(item.get("url")).lower(),
        "date": text(item.get("date")),
        "fact_surface": text(item.get("fact_surface")).upper(),
        "entity_ids": sorted(_unique_text(item.get("entity_ids", []))),
        "security_ids": sorted(_unique_text(item.get("security_ids", []))),
    })


def _measure_content(measure):
    return {
        key: value for key, value in measure.items() if key != "measure_id"
    }


def _semantic_measures(item):
    return sorted(
        (_measure_content(measure) for measure in item.get("measures", [])),
        key=stable_hash,
    )


def _measure_semantic_key(measure, evidence_item):
    """Scope one metric observation to the exact economic/market subject."""
    return (
        measure.get("subject_id"), measure.get("metric"),
        measure.get("as_of"), measure.get("period"),
    )


def append_evidence_items(store, raw_items, *, as_of):
    store = deepcopy(store)
    raw_items = raw_items if isinstance(raw_items, list) else []
    if len(raw_items) > 80:
        raise ResearchContractError(["evidence.packet_limit_80"])
    if len(store.get("items", [])) + len(raw_items) > 400:
        raise ResearchContractError(["evidence.store_limit_400"])
    existing_by_id = {
        item.get("evidence_id"): item for item in store.get("items", [])
        if isinstance(item, dict) and item.get("evidence_id")
    }
    existing_by_signature = {
        evidence_signature(item): item for item in existing_by_id.values()
    }
    existing_measure_ids = {
        measure.get("measure_id"): measure
        for item in existing_by_id.values()
        for measure in item.get("measures", [])
        if isinstance(measure, dict) and measure.get("measure_id")
    }
    existing_document_fact_ids = {
        fact.get("fact_id"): fact
        for item in existing_by_id.values()
        for fact in item.get("document_facts", [])
        if isinstance(fact, dict) and fact.get("fact_id")
    }
    existing_measure_semantics = {
        _measure_semantic_key(measure, item): measure
        for item in existing_by_id.values()
        for measure in item.get("measures", [])
        if isinstance(measure, dict)
    }
    accepted = []
    def enrich(existing, incoming, *, alias=False):
        conflicts = []
        for field in (
            "claim", "source", "url", "date", "boundary", "number",
            "fact_surface", "roles", "source_tier", "decision_impact",
            "entity_ids", "security_ids", "claim_ids", "document_facts",
        ):
            if existing.get(field) != incoming.get(field):
                conflicts.append(field)
        if (
            _semantic_measures(existing) != _semantic_measures(incoming)
            if alias else existing.get("measures") != incoming.get("measures")
        ):
            conflicts.append("measures")
        if not alias and existing.get("origin") != incoming.get("origin"):
            conflicts.append("origin")
        if conflicts:
            raise ResearchContractError([
                "evidence.duplicate_semantic_conflict:"
                f"{existing.get('evidence_id')}:" + ",".join(conflicts)
            ])
        return existing

    for raw in raw_items:
        item = normalize_evidence_item(raw, as_of=as_of)
        evidence_id = item["evidence_id"]
        signature = evidence_signature(item)
        if evidence_id in existing_by_id:
            if evidence_signature(existing_by_id[evidence_id]) != signature:
                raise ResearchContractError([f"evidence.id_collision:{evidence_id}"])
            enrich(existing_by_id[evidence_id], item)
            accepted.append(evidence_id)
            continue
        if signature in existing_by_signature:
            canonical = enrich(existing_by_signature[signature], item, alias=True)
            canonical_id = canonical["evidence_id"]
            store.setdefault("aliases", {})[evidence_id] = canonical_id
            accepted.append(canonical_id)
            continue
        for measure in item.get("measures", []):
            measure_id = measure.get("measure_id")
            if measure_id in existing_measure_ids:
                raise ResearchContractError([
                    f"evidence.measure_id_conflict:{measure_id}"
                ])
            semantic_key = _measure_semantic_key(measure, item)
            prior_measure = existing_measure_semantics.get(semantic_key)
            if prior_measure and any(
                prior_measure.get(field) != measure.get(field)
                for field in ("value", "unit", "dimension")
            ):
                raise ResearchContractError([
                    "evidence.measure_semantic_conflict:"
                    + text(measure.get("metric"))
                ])
        for fact in item.get("document_facts", []):
            fact_id = fact.get("fact_id")
            if fact_id in existing_document_fact_ids:
                raise ResearchContractError([
                    f"evidence.document_fact_id_conflict:{fact_id}"
                ])
        store.setdefault("items", []).append(item)
        existing_by_id[evidence_id] = item
        existing_by_signature[signature] = item
        for measure in item.get("measures", []):
            existing_measure_ids[measure.get("measure_id")] = measure
            existing_measure_semantics[
                _measure_semantic_key(measure, item)
            ] = measure
        for fact in item.get("document_facts", []):
            existing_document_fact_ids[fact.get("fact_id")] = fact
        accepted.append(evidence_id)
    return store, list(dict.fromkeys(accepted))


def resolve_evidence_id(store, evidence_id):
    aliases = store.get("aliases", {}) if isinstance(store, dict) else {}
    return text(aliases.get(evidence_id) or evidence_id)


def evidence_index(store):
    return {
        text(item.get("evidence_id")): item
        for item in store.get("items", []) if isinstance(item, dict) and item.get("evidence_id")
    }


def validate_evidence_scope(task_spec, store):
    entities = {
        item.get("entity_id"): item for item in task_spec.get("primary_entities", [])
    }
    errors = []
    for item in store.get("items", []):
        evidence_id = item.get("evidence_id")
        fact_surface = item.get("fact_surface")
        security_ids = set(item.get("security_ids", []))
        for entity_id in item.get("entity_ids", []):
            entity = entities.get(entity_id)
            if not entity:
                errors.append(f"evidence.entity_unknown:{evidence_id}:{entity_id}")
                continue
            # A candidate discovered under an industry/event TaskSpec is not a new
            # semantic entity.  Security-bound listed-company observations may
            # therefore use the existing research subject while retaining an exact
            # ticker@MIC identity.  Unbound listed-company facts remain out of scope.
            in_scope = fact_surface in entity.get("fact_surfaces", [])
            if (
                not in_scope
                and fact_surface in LISTED_COMPANY_FACT_SURFACES
                and security_ids
            ):
                in_scope = True
            if not in_scope:
                errors.append(
                    f"evidence.fact_surface_out_of_scope:{evidence_id}:"
                    f"{entity_id}:{fact_surface}"
                )
            expected_security_id = entity_security_id(entity)
            if (
                expected_security_id
                and fact_surface in LISTED_COMPANY_FACT_SURFACES
                and expected_security_id not in security_ids
            ):
                errors.append(
                    f"evidence.listed_entity_security_mismatch:{evidence_id}:"
                    f"{entity_id}:{expected_security_id}"
                )
    if errors:
        raise ResearchContractError(errors)
    return store


def normalize_source_check(raw, *, task_spec, store, origin=None):
    raw = raw if isinstance(raw, dict) else {}
    errors = []
    entities = {
        item["entity_id"]: item for item in task_spec.get("primary_entities", [])
    }
    entity_id = text(raw.get("entity_id"))
    fact_surface = text(raw.get("fact_surface")).upper()
    source_origin = _enum(
        origin or raw.get("origin") or "LEAD_RESEARCH", SOURCE_CHECK_ORIGINS
    )
    entity = entities.get(entity_id)
    expected_security_id = entity_security_id(entity)
    security_id = normalize_security_id(
        raw.get("security_id") or expected_security_id
    )
    outcome = _enum(raw.get("outcome"), SOURCE_CHECK_OUTCOMES)
    queries = _unique_text(
        raw.get("queries") if isinstance(raw.get("queries"), list) else [raw.get("query")],
        limit=12,
    )
    index_url = text(raw.get("official_index_url"))
    checked_urls = _unique_text(
        raw.get("checked_document_urls") or raw.get("checked_urls") or [], limit=200
    )
    acquisition_receipt_ids = [
        text(item).lower()
        for item in _unique_text(raw.get("acquisition_receipt_ids", []), limit=8)
    ]
    all_urls = ([index_url] if index_url else []) + checked_urls
    evidence_ids = [
        resolve_evidence_id(store, item)
        for item in _unique_text(raw.get("evidence_ids", []), limit=200)
    ]
    known_evidence = evidence_index(store)
    window_start = parse_iso_date(raw.get("window_start"))
    window_end = parse_iso_date(raw.get("window_end") or task_spec.get("as_of"))
    cutoff = parse_iso_date(task_spec.get("as_of"))
    window_basis = text(raw.get("window_basis")).upper()
    latest_periodic_report_date = parse_iso_date(
        raw.get("latest_periodic_report_date")
    )
    try:
        index_item_count = int(raw.get("index_item_count", 0))
    except (TypeError, ValueError):
        index_item_count = -1
    raw_index_entries = raw.get("index_entries", [])
    if not isinstance(raw_index_entries, list):
        errors.append("source_check.index_entries_must_be_list")
        raw_index_entries = []
    if len(raw_index_entries) > MAX_INDEX_ENTRIES:
        errors.append(f"source_check.index_entries_limit_{MAX_INDEX_ENTRIES}")
    index_entries = []
    index_entry_urls = set()
    for entry_index, entry in enumerate(
        raw_index_entries[:MAX_INDEX_ENTRIES], start=1
    ):
        if not isinstance(entry, dict) or set(entry) != INDEX_ENTRY_FIELDS:
            errors.append(f"source_check.index_entry_fields_invalid:{entry_index}")
            continue
        title = text(entry.get("title"))
        entry_url = text(entry.get("url"))
        entry_date = parse_iso_date(entry.get("date"))
        disposition = _enum(
            entry.get("disposition"), INDEX_ENTRY_DISPOSITIONS
        )
        reason = text(entry.get("reason"))
        if (
            not title or not concrete_url(entry_url) or entry_date is None
            or not disposition or not reason
        ):
            errors.append(f"source_check.index_entry_invalid:{entry_index}")
            continue
        if disposition != "OPENED_RELEVANT" and any(
            marker in title for marker in MATERIAL_TITLE_MARKERS
        ):
            errors.append(
                f"source_check.material_title_requires_opened_evidence:{entry_index}"
            )
        if entry_url in index_entry_urls:
            errors.append(f"source_check.index_entry_url_duplicate:{entry_index}")
        index_entry_urls.add(entry_url)
        if (
            window_start is not None
            and window_end is not None
            and not window_start <= entry_date <= window_end
        ):
            errors.append(f"source_check.index_entry_outside_window:{entry_index}")
        index_entries.append({
            "title": title,
            "url": entry_url,
            "date": entry_date.isoformat(),
            "disposition": disposition,
            "reason": reason,
        })
    if not source_origin:
        errors.append("source_check.origin_invalid")
    if security_id and not SECURITY_ID_RE.fullmatch(security_id):
        errors.append("source_check.security_id_invalid")
    if entity_id not in entities:
        errors.append("source_check.entity_unknown")
    elif (
        fact_surface not in entities[entity_id].get("fact_surfaces", [])
        and not (
            security_id and fact_surface in LISTED_COMPANY_FACT_SURFACES
        )
    ):
        errors.append("source_check.fact_surface_out_of_scope")
    if expected_security_id and security_id != expected_security_id:
        errors.append("source_check.listed_entity_security_mismatch")
    if not outcome:
        errors.append("source_check.outcome_invalid")
    if not queries:
        errors.append("source_check.query_required")
    if not all_urls or any(not concrete_url(url) for url in all_urls):
        errors.append("source_check.concrete_checked_url_required")
    if any(
        not SHA256_RE.fullmatch(item)
        and not DOCUMENT_ACQUISITION_ID_RE.fullmatch(item)
        for item in acquisition_receipt_ids
    ):
        errors.append("source_check.acquisition_receipt_id_invalid")
    if window_start is None or window_end is None:
        errors.append("source_check.window_requires_iso_dates")
    elif window_start > window_end:
        errors.append("source_check.window_invalid")
    elif cutoff is not None and window_end > cutoff:
        errors.append("source_check.window_after_as_of")
    if outcome == "FOUND" and not evidence_ids:
        errors.append("source_check.found_requires_evidence")
    if outcome == "NO_RESULT" and evidence_ids:
        errors.append("source_check.no_result_cannot_bind_evidence")
    if any(item not in known_evidence for item in evidence_ids):
        errors.append("source_check.evidence_unknown")
    for evidence_id in evidence_ids:
        item = known_evidence.get(evidence_id, {})
        if entity_id not in item.get("entity_ids", []):
            errors.append(f"source_check.evidence_entity_mismatch:{evidence_id}")
        if (
            fact_surface != "OFFICIAL_DISCLOSURE_INDEX"
            and item.get("fact_surface") != fact_surface
        ):
            errors.append(f"source_check.evidence_surface_mismatch:{evidence_id}")
        allowed_evidence_urls = (
            checked_urls
            if fact_surface == "OFFICIAL_DISCLOSURE_INDEX"
            else all_urls
        )
        if item.get("url") not in allowed_evidence_urls:
            errors.append(f"source_check.evidence_url_not_checked:{evidence_id}")
        item_security_ids = item.get("security_ids", [])
        if (
            (security_id and item_security_ids != [security_id])
            or (not security_id and item_security_ids)
        ):
            errors.append(f"source_check.evidence_security_mismatch:{evidence_id}")
    if outcome == "NO_RESULT" and not text(raw.get("negative_scope")):
        errors.append("source_check.no_result_requires_negative_scope")
    if outcome == "INSUFFICIENT" and not text(raw.get("limitation")):
        errors.append("source_check.insufficient_requires_limitation")
    if fact_surface == "OFFICIAL_DISCLOSURE_INDEX" and outcome != "INSUFFICIENT":
        if source_origin not in {
            "HOST_INPUT", "CONTROLLED_FIXTURE"
        }:
            errors.append("source_check.official_index_requires_host_acquisition")
        if not index_url or raw.get("enumeration_complete") is not True:
            errors.append("source_check.official_index_requires_complete_enumeration")
        if window_basis != OFFICIAL_INDEX_WINDOW_BASIS:
            errors.append("source_check.official_index_window_basis_required")
        if latest_periodic_report_date is None:
            errors.append("source_check.latest_periodic_report_date_required")
        elif window_end and latest_periodic_report_date > window_end:
            errors.append("source_check.latest_periodic_report_after_window")
        if window_start and window_end and latest_periodic_report_date:
            required_start = min(
                window_end - timedelta(days=119), latest_periodic_report_date
            )
            if window_start > required_start:
                errors.append("source_check.official_index_window_too_short")
        if index_item_count < 0 or (outcome == "FOUND" and index_item_count == 0):
            errors.append("source_check.official_index_item_count_invalid")
        if index_item_count != len(index_entries):
            errors.append("source_check.official_index_manifest_count_mismatch")
        invalid_opened_urls = set(checked_urls) - index_entry_urls
        if index_item_count == 0:
            invalid_opened_urls.discard(index_url)
        if invalid_opened_urls:
            errors.append("source_check.opened_document_not_in_index_manifest")
        relevant_urls = {
            item["url"] for item in index_entries
            if item.get("disposition") == "OPENED_RELEVANT"
        }
        reviewed_urls = {
            item["url"] for item in index_entries
            if item.get("disposition") == "REVIEWED_NOT_MATERIAL"
        }
        evidence_urls = {
            known_evidence.get(evidence_id, {}).get("url")
            for evidence_id in evidence_ids
        }
        if relevant_urls - set(checked_urls):
            errors.append("source_check.relevant_index_entry_not_opened")
        if relevant_urls - evidence_urls:
            errors.append("source_check.relevant_index_entry_requires_evidence")
        if reviewed_urls - set(checked_urls):
            errors.append("source_check.reviewed_index_entry_not_opened")
        if outcome == "FOUND" and not relevant_urls:
            errors.append("source_check.found_requires_relevant_index_entry")
        if outcome == "NO_RESULT" and relevant_urls:
            errors.append("source_check.no_result_has_relevant_index_entry")
    elif fact_surface == "OFFICIAL_DISCLOSURE_INDEX":
        if index_item_count < len(index_entries):
            errors.append("source_check.partial_index_count_below_manifest")
    elif index_entries:
        errors.append("source_check.index_entries_only_for_official_index")
    if errors:
        raise ResearchContractError(errors)
    source_check_id = text(raw.get("source_check_id")).upper() or stable_id(
        "SC", entity_id, security_id, fact_surface, window_start, window_end,
        "|".join(queries)
    )
    if not ID_RE.fullmatch(source_check_id):
        raise ResearchContractError(["source_check.id_invalid"])
    return {
        "source_check_id": source_check_id,
        "entity_id": entity_id,
        "security_id": security_id,
        "fact_surface": fact_surface,
        "origin": source_origin,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "window_basis": window_basis,
        "latest_periodic_report_date": (
            latest_periodic_report_date.isoformat()
            if latest_periodic_report_date else ""
        ),
        "index_item_count": index_item_count,
        "index_entries": index_entries,
        "queries": queries,
        "official_index_url": index_url,
        "checked_document_urls": checked_urls,
        "acquisition_receipt_ids": acquisition_receipt_ids,
        "enumeration_complete": raw.get("enumeration_complete") is True,
        "outcome": outcome,
        "evidence_ids": list(dict.fromkeys(evidence_ids)),
        "negative_scope": text(raw.get("negative_scope")),
        "limitation": text(raw.get("limitation")),
    }


def append_source_checks(store, raw_checks, *, task_spec, origin=None):
    store = deepcopy(store)
    raw_checks = raw_checks if isinstance(raw_checks, list) else []
    if len(raw_checks) > 80:
        raise ResearchContractError(["source_check.packet_limit_80"])
    if len(store.get("source_checks", [])) + len(raw_checks) > 400:
        raise ResearchContractError(["source_check.store_limit_400"])
    by_id = {
        item.get("source_check_id"): item for item in store.get("source_checks", [])
        if isinstance(item, dict) and item.get("source_check_id")
    }
    accepted = []
    for raw in raw_checks:
        item = normalize_source_check(
            raw, task_spec=task_spec, store=store, origin=origin
        )
        item_id = item["source_check_id"]
        if item_id in by_id:
            if by_id[item_id] != item:
                raise ResearchContractError([f"source_check.id_collision:{item_id}"])
        else:
            store.setdefault("source_checks", []).append(item)
            by_id[item_id] = item
        accepted.append(item_id)
    return store, list(dict.fromkeys(accepted))


def require_new_evidence_bound(store, new_evidence_ids, source_check_ids):
    """Require every newly canonicalized item to be opened by this packet."""
    new_evidence_ids = set(new_evidence_ids)
    if not new_evidence_ids:
        return
    accepted_checks = {
        item.get("source_check_id"): item for item in store.get("source_checks", [])
        if isinstance(item, dict) and item.get("source_check_id") in source_check_ids
    }
    bound = set()
    for check in accepted_checks.values():
        bound.update(check.get("evidence_ids", []))
    missing = new_evidence_ids - bound
    if missing:
        raise ResearchContractError([
            "evidence.new_item_requires_same_packet_source_check:"
            + ",".join(sorted(missing))
        ])


def snapshot_hash(snapshot):
    return stable_hash(snapshot)


def semantic_snapshot_hash(snapshot):
    material = deepcopy(snapshot) if isinstance(snapshot, dict) else {}
    for field in ("schema_version", "version", "base_snapshot_sha256"):
        material.pop(field, None)
    return stable_hash(material)


def _claim_ids(snapshot):
    ids = set()
    core = snapshot.get("core_judgment", {}) if isinstance(snapshot, dict) else {}
    if text(core.get("claim_id")):
        ids.add(text(core.get("claim_id")))
    for field in (
        "material_changes", "agenda_answers", "value_transfer_paths",
        "market_by_horizon", "self_countercases",
    ):
        for item in snapshot.get(field, []) if isinstance(snapshot.get(field), list) else []:
            if not isinstance(item, dict):
                continue
            for key in ("claim_id", "change_id", "question_id", "path_id", "setup_id"):
                if text(item.get(key)):
                    ids.add(text(item.get(key)))
    for group in snapshot.get("market_carriers_by_horizon", []) if isinstance(
        snapshot.get("market_carriers_by_horizon"), list
    ) else []:
        if not isinstance(group, dict):
            continue
        for item in group.get("carriers", []) if isinstance(
            group.get("carriers"), list
        ) else []:
            if isinstance(item, dict) and text(item.get("claim_id")):
                ids.add(text(item.get("claim_id")))
    for group in snapshot.get("candidates_by_horizon", []) if isinstance(
        snapshot.get("candidates_by_horizon"), list
    ) else []:
        if not isinstance(group, dict):
            continue
        for item in group.get("candidates", []) if isinstance(group.get("candidates"), list) else []:
            if isinstance(item, dict) and text(item.get("claim_id")):
                ids.add(text(item.get("claim_id")))
    return ids


def challenge_receipt_index(ledger):
    result = {}
    for call in ledger.get("calls", []) if isinstance(ledger, dict) else []:
        if not isinstance(call, dict):
            continue
        if call.get("role") == "CHALLENGER" and call.get("status") == "SUCCEEDED":
            challenge_id = text(call.get("challenge_id"))
            if challenge_id:
                result[challenge_id] = call
    return result


def normalize_action_intent(raw, *, action_type="RESEARCH"):
    raw = raw if isinstance(raw, dict) else {}
    action_type = _enum(raw.get("action_type") or action_type, ACTION_TYPES)
    target = text(raw.get("target_snapshot_field"))
    errors = []
    if not action_type:
        errors.append("action_intent.type_invalid")
    if target not in ACTION_TARGETS:
        errors.append("action_intent.target_invalid")
    required = (
        "current_uncertainty", "evidence_needed", "expected_decision_delta",
        "stop_condition", "cost_bound",
    )
    for field in required:
        if not text(raw.get(field)):
            errors.append(f"action_intent.{field}_required")
        validate_numeric_text(
            raw.get(field), [], path=f"action_intent.{field}", errors=errors
        )
    if errors:
        raise ResearchContractError(errors)
    action_id = text(raw.get("action_id")).upper() or stable_id(
        "AI", action_type, target, raw.get("current_uncertainty"), raw.get("evidence_needed")
    )
    return {
        "action_id": action_id,
        "action_type": action_type,
        "target_snapshot_field": target,
        "current_uncertainty": text(raw.get("current_uncertainty")),
        "evidence_needed": text(raw.get("evidence_needed")),
        "expected_decision_delta": text(raw.get("expected_decision_delta")),
        "stop_condition": text(raw.get("stop_condition")),
        "cost_bound": text(raw.get("cost_bound")),
        "status": "PLANNED",
    }


def _normalized_ref_ids(values, store, *, limit=80):
    return list(dict.fromkeys(
        resolve_evidence_id(store, item) for item in _unique_text(values, limit=limit)
    ))


def _validate_evidence_refs(ids, evidence, errors, path):
    for evidence_id in ids:
        if evidence_id not in evidence:
            errors.append(f"snapshot.unknown_evidence:{path}:{evidence_id}")


def evidence_has_role(item, *roles):
    available = set(item.get("roles", [])) if isinstance(item, dict) else set()
    return bool(available.intersection(roles))


def _validate_alternative_binding(
    item, refs, evidence, errors, *, path, current_security_id
):
    alternative = text(item.get("closest_alternative")).upper()
    alternative_refs = item.get("alternative_evidence_ids", [])
    _validate_evidence_refs(
        alternative_refs, evidence, errors, f"{path}.alternative"
    )
    if alternative == "UNKNOWN":
        if alternative_refs:
            errors.append(f"snapshot.alternative_unknown_has_evidence:{path}")
        item["closest_alternative"] = "UNKNOWN"
        return
    alternative_id = normalize_security_id(alternative)
    item["closest_alternative"] = alternative_id
    if (
        not SECURITY_ID_RE.fullmatch(alternative_id)
        or alternative_id == current_security_id
        or not alternative_refs
        or not set(alternative_refs).issubset(set(refs))
    ):
        errors.append(f"snapshot.alternative_binding_required:{path}")
        return
    if any(
        evidence.get(evidence_id, {}).get("security_ids") != [alternative_id]
        or not evidence_has_role(
            evidence.get(evidence_id, {}), "MARKET_STATE", "TECHNICAL_STATE"
        )
        for evidence_id in alternative_refs
    ):
        errors.append(f"snapshot.alternative_evidence_invalid:{path}")


def _validate_item_numeric_text(item, fields, refs, evidence, errors, path):
    measures = [
        measure
        for evidence_id in refs
        for measure in evidence.get(evidence_id, {}).get("measures", [])
        if isinstance(measure, dict)
    ]
    for field in fields:
        validate_numeric_text(
            item.get(field), measures, path=f"{path}.{field}", errors=errors
        )


def _normalize_snapshot_lists(raw, store):
    normalized = deepcopy(raw)
    ref_fields = {
        "material_changes": "evidence_ids",
        "open_material_gaps": "evidence_ids",
        "agenda_answers": "evidence_ids",
        "value_transfer_paths": "evidence_ids",
        "market_by_horizon": "evidence_ids",
        "self_countercases": "evidence_ids",
        "challenge_resolutions": "evidence_ids",
        "unresolved_questions": "evidence_ids",
        "lowest_cost_next_validation": "evidence_ids",
    }
    for field, ref_field in ref_fields.items():
        values = normalized.get(field)
        values = values if isinstance(values, list) else []
        cleaned = []
        for value in values:
            if not isinstance(value, dict):
                continue
            item = deepcopy(value)
            item[ref_field] = _normalized_ref_ids(item.get(ref_field, []), store)
            cleaned.append(item)
        normalized[field] = cleaned
    carrier_groups = normalized.get("market_carriers_by_horizon")
    carrier_groups = carrier_groups if isinstance(carrier_groups, list) else []
    normalized_carrier_groups = []
    for group in carrier_groups:
        if not isinstance(group, dict):
            continue
        copy_group = deepcopy(group)
        carriers = []
        for carrier in group.get("carriers", []) if isinstance(
            group.get("carriers"), list
        ) else []:
            if not isinstance(carrier, dict):
                continue
            item = deepcopy(carrier)
            item["ticker"] = text(item.get("ticker")).upper()
            item["exchange"] = normalize_exchange(item.get("exchange"))
            item["evidence_ids"] = _normalized_ref_ids(
                item.get("evidence_ids", []), store
            )
            item["market_evidence_ids"] = _normalized_ref_ids(
                item.get("market_evidence_ids", []), store
            )
            item["alternative_evidence_ids"] = _normalized_ref_ids(
                item.get("alternative_evidence_ids", []), store
            )
            carriers.append(item)
        copy_group["carriers"] = carriers
        normalized_carrier_groups.append(copy_group)
    normalized["market_carriers_by_horizon"] = normalized_carrier_groups
    groups = normalized.get("candidates_by_horizon")
    groups = groups if isinstance(groups, list) else []
    normalized_groups = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        copy_group = deepcopy(group)
        candidates = []
        for candidate in group.get("candidates", []) if isinstance(group.get("candidates"), list) else []:
            if not isinstance(candidate, dict):
                continue
            item = deepcopy(candidate)
            item["ticker"] = text(item.get("ticker")).upper()
            item["exchange"] = normalize_exchange(item.get("exchange"))
            item["evidence_ids"] = _normalized_ref_ids(item.get("evidence_ids", []), store)
            item["exposure_evidence_ids"] = _normalized_ref_ids(
                item.get("exposure_evidence_ids", []), store
            )
            item["market_evidence_ids"] = _normalized_ref_ids(
                item.get("market_evidence_ids", []), store
            )
            item["alternative_evidence_ids"] = _normalized_ref_ids(
                item.get("alternative_evidence_ids", []), store
            )
            item["value_path_ids"] = _unique_text(item.get("value_path_ids", []), limit=12)
            candidates.append(item)
        copy_group["candidates"] = candidates
        normalized_groups.append(copy_group)
    normalized["candidates_by_horizon"] = normalized_groups
    core = deepcopy(normalized.get("core_judgment")) if isinstance(
        normalized.get("core_judgment"), dict
    ) else {}
    core["evidence_ids"] = _normalized_ref_ids(core.get("evidence_ids", []), store)
    normalized["core_judgment"] = core
    normalized["consumed_evidence_ids"] = _normalized_ref_ids(
        normalized.get("consumed_evidence_ids", []), store
    )
    dispositions = []
    indexed_evidence = evidence_index(store)
    for value in normalized.get("non_material_evidence_dispositions", []) if isinstance(
        normalized.get("non_material_evidence_dispositions"), list
    ) else []:
        if not isinstance(value, dict):
            continue
        item = deepcopy(value)
        item["evidence_id"] = resolve_evidence_id(store, text(item.get("evidence_id")))
        item["event_family_id"] = material_evidence_family_id(
            indexed_evidence.get(item["evidence_id"], {})
        )
        item["decision_dimension"] = text(item.get("decision_dimension")).upper()
        dispositions.append(item)
    normalized["non_material_evidence_dispositions"] = dispositions
    return normalized


def coverage_obligations(task_spec, store, snapshot=None):
    latest = {}
    latest_by_security = {}
    for check in store.get("source_checks", []):
        if not isinstance(check, dict):
            continue
        key = (
            check.get("entity_id"), check.get("security_id", ""),
            check.get("fact_surface"),
        )
        latest[key] = check
        if check.get("security_id"):
            latest_by_security[
                (check.get("security_id"), check.get("fact_surface"))
            ] = check
    obligations = []
    primary_security_ids = set()
    for entity in task_spec.get("primary_entities", []):
        security_id = entity_security_id(entity)
        if security_id:
            primary_security_ids.add(security_id)
        for surface in entity.get("fact_surfaces", []):
            check = latest.get((entity.get("entity_id"), security_id, surface))
            if not check or check.get("outcome") == "INSUFFICIENT":
                obligations.append({
                    "obligation_id": f"COVERAGE:{entity.get('entity_id')}:{surface}",
                    "kind": "SOURCE_CHECK_REQUIRED",
                    "entity_id": entity.get("entity_id"),
                    "fact_surface": surface,
                    "target_snapshot_field": "material_changes",
                })
    # A listed security discovered by the Lead inherits the same reality closure
    # as an explicitly named listed-company TaskSpec entity.  This connects
    # industry logic to a market carrier without mutating TaskSpec or creating a
    # second candidate state machine.
    seen_candidate_securities = set()
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    for group in snapshot.get("candidates_by_horizon", []):
        if not isinstance(group, dict):
            continue
        for candidate in group.get("candidates", []):
            if (
                not isinstance(candidate, dict)
                or text(candidate.get("stance")).upper() != "CONDITIONAL_PRIORITY"
            ):
                continue
            security_id = normalize_security_id(
                f"{text(candidate.get('ticker')).upper()}@"
                f"{normalize_exchange(candidate.get('exchange'))}"
            )
            if (
                not SECURITY_ID_RE.fullmatch(security_id)
                or security_id in seen_candidate_securities
                or security_id in primary_security_ids
            ):
                continue
            seen_candidate_securities.add(security_id)
            for surface in LISTED_COMPANY_FACT_SURFACES:
                check = latest_by_security.get((security_id, surface))
                if not check or check.get("outcome") == "INSUFFICIENT":
                    obligations.append({
                        "obligation_id": (
                            f"CANDIDATE_COVERAGE:{security_id}:{surface}"
                        ),
                        "kind": "SOURCE_CHECK_REQUIRED",
                        "entity_id": "",
                        "security_id": security_id,
                        "fact_surface": surface,
                        "target_snapshot_field": "candidates_by_horizon",
                    })
    return obligations


def stable_material_gap_id(obligation):
    """Return a semantic gap identity that survives evidence-store growth."""
    kind = text(obligation.get("kind"))
    if kind == "SOURCE_CHECK_REQUIRED":
        security = text(obligation.get("security_id"))
        subject = security or text(obligation.get("entity_id"))
        return f"GAP-COVERAGE-{stable_hash([subject, obligation.get('fact_surface')])[:14].upper()}"
    if kind == "HIGH_EVIDENCE_UNACCOUNTED":
        return f"GAP-ACCOUNTING-{stable_hash(obligation.get('evidence_id'))[:14].upper()}"
    if kind == "MATERIAL_INDEX_EVIDENCE_UNACCOUNTED":
        return f"GAP-MATERIAL-INDEX-{stable_hash(obligation.get('evidence_id'))[:14].upper()}"
    if kind == "MATERIAL_BODY_FACTS_REQUIRED":
        return f"GAP-MATERIAL-BODY-{stable_hash(obligation.get('evidence_id'))[:14].upper()}"
    if kind == "UNRESOLVED_CHALLENGE":
        return f"GAP-CHALLENGE-{stable_hash(obligation.get('challenge_id'))[:14].upper()}"
    return f"GAP-MATERIAL-{stable_hash(obligation)[:14].upper()}"


def material_gap_requirements(run, snapshot=None):
    return [
        {
            **deepcopy(item),
            "runtime_obligation_id": item.get("obligation_id"),
            "gap_id": stable_material_gap_id(item),
        }
        for item in hard_obligations(run, snapshot)
        if item.get("kind") in {
            "SOURCE_CHECK_REQUIRED", "HIGH_EVIDENCE_UNACCOUNTED",
            "MATERIAL_INDEX_EVIDENCE_UNACCOUNTED", "MATERIAL_BODY_FACTS_REQUIRED",
        }
    ]


def material_index_evidence_ids(store):
    """Evidence opened from a marker title must receive an explicit decision."""
    evidence = evidence_index(store)
    required = set()
    for check in store.get("source_checks", []):
        if (
            not isinstance(check, dict)
            or check.get("fact_surface") != "OFFICIAL_DISCLOSURE_INDEX"
        ):
            continue
        check_evidence_ids = set(check.get("evidence_ids", []))
        for entry in check.get("index_entries", []):
            if (
                not isinstance(entry, dict)
                or entry.get("disposition") != "OPENED_RELEVANT"
                or not any(
                    marker in text(entry.get("title"))
                    for marker in MATERIAL_TITLE_MARKERS
                )
            ):
                continue
            for evidence_id in check_evidence_ids:
                if evidence.get(evidence_id, {}).get("url") == entry.get("url"):
                    required.add(evidence_id)
    return required


def material_index_titles_by_evidence(store):
    """Map marker-derived evidence to the exact official-index titles opened."""
    evidence = evidence_index(store)
    result = {}
    for check in store.get("source_checks", []):
        if (
            not isinstance(check, dict)
            or check.get("fact_surface") != "OFFICIAL_DISCLOSURE_INDEX"
        ):
            continue
        by_url = {
            evidence_id: evidence.get(evidence_id, {}).get("url")
            for evidence_id in check.get("evidence_ids", [])
        }
        for entry in check.get("index_entries", []):
            if (
                not isinstance(entry, dict)
                or entry.get("disposition") != "OPENED_RELEVANT"
                or not any(
                    marker in text(entry.get("title"))
                    for marker in MATERIAL_TITLE_MARKERS
                )
            ):
                continue
            for evidence_id, url in by_url.items():
                if url == entry.get("url"):
                    result.setdefault(evidence_id, []).append(
                        text(entry.get("title"))
                    )
    return result


def validate_document_fact_acquisition(store):
    """Require body excerpts to enter through an explicit host acquisition path."""
    allowed_origins = {"HOST_INPUT", "CONTROLLED_FIXTURE"}
    host_bound = {}
    for check in store.get("source_checks", []):
        if not isinstance(check, dict) or check.get("origin") not in allowed_origins:
            continue
        receipt_ids = set(check.get("acquisition_receipt_ids", []))
        for evidence_id in check.get("evidence_ids", []):
            host_bound.setdefault(evidence_id, set()).update(receipt_ids)
    errors = []
    seen_fact_ids = set()
    for item in store.get("items", []):
        if not isinstance(item, dict):
            continue
        facts = item.get("document_facts", [])
        evidence_id = item.get("evidence_id")
        if facts and evidence_id not in host_bound:
            errors.append(
                f"document_fact.host_acquisition_required:{evidence_id}"
            )
        for fact in facts:
            fact_id = fact.get("fact_id") if isinstance(fact, dict) else ""
            if not fact_id or fact_id in seen_fact_ids:
                errors.append(
                    f"document_fact.global_id_required_unique:{fact_id or 'EMPTY'}"
            )
            seen_fact_ids.add(fact_id)
            bound_document_hashes = {
                match.group(1)
                for receipt_id in host_bound.get(evidence_id, set())
                for match in [DOCUMENT_ACQUISITION_ID_RE.fullmatch(receipt_id)]
                if match
            }
            if isinstance(fact, dict) and fact.get(
                "document_sha256"
            ) not in bound_document_hashes:
                errors.append(
                    f"document_fact.acquisition_hash_unbound:{fact_id or 'EMPTY'}"
                )
    if errors:
        raise ResearchContractError(errors)


def material_evidence_family_id(item):
    """Derive an event family from subject plus host-bound event identity."""
    facts = item.get("document_facts", []) if isinstance(item, dict) else []
    identities = {
        (fact.get("event_type"), fact.get("event_anchor"))
        for fact in facts if isinstance(fact, dict)
    }
    if len(identities) != 1:
        return ""
    event_type, event_anchor = next(iter(identities))
    subjects = item.get("security_ids", []) or item.get("entity_ids", [])
    if len(subjects) != 1:
        return ""
    return stable_id("EVENT", subjects[0], event_type, event_anchor)


def material_evidence_has_body_facts(store, evidence_id):
    """Check the structural body-extraction gate for one marker disclosure."""
    item = evidence_index(store).get(evidence_id, {})
    facts = item.get("document_facts", [])
    if len(facts) < 2:
        return False
    if len({fact.get("fact_type") for fact in facts}) < 2:
        return False
    if not {fact.get("fact_type") for fact in facts}.intersection({
        "SCOPE", "STATUS", "TERMS", "ECONOMIC_EFFECT", "CONDITION",
        "USE_OF_FUNDS", "AUDIT_CONCLUSION", "CONTROL_RELATIONSHIP",
    }):
        return False
    if len({fact.get("document_sha256") for fact in facts}) != 1:
        return False
    if not material_evidence_family_id(item):
        return False
    titles = material_index_titles_by_evidence(store).get(evidence_id, [])
    expected_types = {material_event_type(title) for title in titles}
    expected_types.discard("")
    actual_types = {fact.get("event_type") for fact in facts}
    if not expected_types or actual_types != expected_types:
        return False
    event_type = next(iter(actual_types))
    fact_types = {fact.get("fact_type") for fact in facts}
    if any(
        not fact_types.intersection(required_group)
        for required_group in MATERIAL_EVENT_REQUIRED_FACT_GROUPS.get(
            event_type, ()
        )
    ):
        return False
    generic = (
        "已阅读完整文件", "后续事项另行公告", "详见公告", "正文与标题一致",
        "公告正文第一页", "文件末尾说明",
    )
    for fact in facts:
        excerpt = _semantic_text(fact.get("excerpt"))
        if len(excerpt) < 12 or any(_semantic_text(value) in excerpt for value in generic):
            return False
        if any(excerpt == _semantic_text(title) for title in titles):
            return False
    return True


def material_body_fact_obligations(store):
    return [
        {
            "obligation_id": f"MATERIAL_BODY_FACTS_REQUIRED:{evidence_id}",
            "kind": "MATERIAL_BODY_FACTS_REQUIRED",
            "evidence_id": evidence_id,
            "target_snapshot_field": "open_material_gaps",
        }
        for evidence_id in sorted(material_index_evidence_ids(store))
        if not material_evidence_has_body_facts(store, evidence_id)
    ]


def material_evidence_obligations(store, snapshot):
    high_ids = {
        item.get("evidence_id") for item in store.get("items", [])
        if isinstance(item, dict) and item.get("decision_impact") == "HIGH"
    }
    accounted = set()
    for item in snapshot.get("material_changes", []):
        accounted.update(item.get("evidence_ids", []))
    for item in snapshot.get("open_material_gaps", []):
        accounted.update(item.get("evidence_ids", []))
    for item in snapshot.get("non_material_evidence_dispositions", []):
        if text(item.get("reason")):
            accounted.add(item.get("evidence_id"))
    marker_ids = material_index_evidence_ids(store)
    obligations = []
    for evidence_id in sorted((high_ids | marker_ids) - accounted):
        if not evidence_id:
            continue
        kind = (
            "HIGH_EVIDENCE_UNACCOUNTED"
            if evidence_id in high_ids
            else "MATERIAL_INDEX_EVIDENCE_UNACCOUNTED"
        )
        obligations.append({
            "obligation_id": f"{kind}:{evidence_id}",
            "kind": kind,
            "evidence_id": evidence_id,
            "target_snapshot_field": "material_changes",
        })
    return obligations


def snapshot_visible_evidence_ids(snapshot):
    visible = set()
    core = snapshot.get("core_judgment", {})
    visible.update(core.get("evidence_ids", []))
    for field in (
        "material_changes", "open_material_gaps", "agenda_answers",
        "value_transfer_paths", "market_by_horizon",
        "self_countercases", "challenge_resolutions", "unresolved_questions",
        "lowest_cost_next_validation",
    ):
        for item in snapshot.get(field, []):
            visible.update(item.get("evidence_ids", []))
    for group in snapshot.get("market_carriers_by_horizon", []):
        for carrier in group.get("carriers", []):
            visible.update(carrier.get("evidence_ids", []))
            visible.update(carrier.get("market_evidence_ids", []))
            visible.update(carrier.get("alternative_evidence_ids", []))
    for group in snapshot.get("candidates_by_horizon", []):
        for candidate in group.get("candidates", []):
            visible.update(candidate.get("evidence_ids", []))
            visible.update(candidate.get("exposure_evidence_ids", []))
            visible.update(candidate.get("market_evidence_ids", []))
            visible.update(candidate.get("alternative_evidence_ids", []))
    for disposition in snapshot.get("non_material_evidence_dispositions", []):
        if disposition.get("evidence_id"):
            visible.add(disposition["evidence_id"])
    return {item for item in visible if item}


def unresolved_challenge_obligations(ledger, snapshot):
    resolved = {
        item.get("challenge_id") for item in snapshot.get("challenge_resolutions", [])
        if isinstance(item, dict)
        and item.get("resolution") in {"ACCEPTED", "PARTIAL", "REJECTED"}
    }
    return [
        {
            "obligation_id": f"CHALLENGE:{item.get('challenge_id')}",
            "kind": "UNRESOLVED_CHALLENGE",
            "challenge_id": item.get("challenge_id"),
            "target_snapshot_field": "core_judgment",
        }
        for item in ledger.get("challenge_packets", [])
        if isinstance(item, dict) and item.get("challenge_id") not in resolved
    ]


def hard_obligations(run, snapshot=None):
    validate_run_shape(run)
    snapshot = snapshot or run["decision_snapshot"]
    obligations = []
    obligations.extend(coverage_obligations(
        run["task_spec"], run["evidence_store"], snapshot
    ))
    obligations.extend(material_evidence_obligations(run["evidence_store"], snapshot))
    obligations.extend(material_body_fact_obligations(run["evidence_store"]))
    obligations.extend(unresolved_challenge_obligations(run["run_ledger"], snapshot))
    return obligations


def snapshot_frontier(run):
    store = run["evidence_store"]
    challenges = run["run_ledger"].get("challenge_packets", [])
    return {
        "evidence_count": len(store.get("items", [])),
        "source_check_count": len(store.get("source_checks", [])),
        "challenge_count": len(challenges),
        "evidence_prefix_sha256": stable_hash(store.get("items", [])),
        "source_check_prefix_sha256": stable_hash(store.get("source_checks", [])),
        "challenge_prefix_sha256": stable_hash(challenges),
    }


def run_at_snapshot_frontier(run, frontier):
    frontier = frontier if isinstance(frontier, dict) else {}
    if set(frontier) != SNAPSHOT_FRONTIER_FIELDS:
        raise ResearchContractError(["snapshot_frontier.fields_invalid"])
    try:
        evidence_count = int(frontier.get("evidence_count"))
        check_count = int(frontier.get("source_check_count"))
        challenge_count = int(frontier.get("challenge_count"))
    except (TypeError, ValueError):
        raise ResearchContractError(["snapshot_frontier.counts_invalid"])
    items = run["evidence_store"].get("items", [])
    checks = run["evidence_store"].get("source_checks", [])
    challenges = run["run_ledger"].get("challenge_packets", [])
    if not (
        0 <= evidence_count <= len(items)
        and 0 <= check_count <= len(checks)
        and 0 <= challenge_count <= len(challenges)
    ):
        raise ResearchContractError(["snapshot_frontier.counts_out_of_range"])
    prefixes = (
        (items[:evidence_count], "evidence_prefix_sha256"),
        (checks[:check_count], "source_check_prefix_sha256"),
        (challenges[:challenge_count], "challenge_prefix_sha256"),
    )
    errors = [
        f"snapshot_frontier.hash_mismatch:{field}"
        for values, field in prefixes if stable_hash(values) != frontier.get(field)
    ]
    if errors:
        raise ResearchContractError(errors)
    result = deepcopy(run)
    result["evidence_store"]["items"] = deepcopy(items[:evidence_count])
    result["evidence_store"]["source_checks"] = deepcopy(checks[:check_count])
    result["evidence_store"]["aliases"] = {
        alias: target for alias, target in result["evidence_store"].get("aliases", {}).items()
        if target in {item.get("evidence_id") for item in items[:evidence_count]}
    }
    result["run_ledger"]["challenge_packets"] = deepcopy(
        challenges[:challenge_count]
    )
    return result


def _validate_snapshot_obligations(run, snapshot, status, errors):
    trial_run = deepcopy(run)
    trial_run["decision_snapshot"] = snapshot
    obligations = hard_obligations(trial_run, snapshot)
    coverage = [
        item for item in obligations if item["kind"] == "SOURCE_CHECK_REQUIRED"
    ]
    unaccounted = [
        item for item in obligations if item["kind"] in {
            "HIGH_EVIDENCE_UNACCOUNTED",
            "MATERIAL_INDEX_EVIDENCE_UNACCOUNTED",
            "MATERIAL_BODY_FACTS_REQUIRED",
        }
    ]
    challenges = [
        item for item in obligations if item["kind"] == "UNRESOLVED_CHALLENGE"
    ]
    open_gap_ids = {
        text(item.get("gap_id")) for item in snapshot.get("open_material_gaps", [])
    }
    expected_gap_ids = {
        stable_material_gap_id(item) for item in coverage + unaccounted
    }
    if expected_gap_ids - open_gap_ids:
        errors.append(
            "snapshot.open_material_gaps_missing:"
            + ",".join(sorted(expected_gap_ids - open_gap_ids))
        )
    if status == "DECISION_READY" and obligations:
        errors.append("snapshot.decision_ready_has_hard_obligations")
    if snapshot.get("open_material_gaps") and status == "DECISION_READY":
        errors.append("snapshot.decision_ready_has_open_material_gaps")
    if snapshot.get("open_material_gaps") and status not in {
        "MATERIAL_FACT_GAP", "RUNTIME_DEGRADED"
    }:
        errors.append("snapshot.open_material_gaps_require_gap_status")
    if coverage or unaccounted:
        if status not in {"MATERIAL_FACT_GAP", "RUNTIME_DEGRADED"}:
            errors.append("snapshot.material_obligation_requires_fact_gap_status")
    elif challenges and status != "UNRESOLVED_CHALLENGE":
        errors.append("snapshot.open_challenge_requires_challenge_status")


def normalize_and_validate_snapshot(raw, *, run, mode="LEAD", persisted=False):
    validate_run_shape(run)
    raw = raw if isinstance(raw, dict) else {}
    raw_fields = set(raw)
    previous = run["decision_snapshot"]
    store = run["evidence_store"]
    task = run["task_spec"]
    ledger = run["run_ledger"]
    snapshot = _normalize_snapshot_lists(raw, store)
    errors = []
    unknown_fields = raw_fields - SNAPSHOT_FIELDS
    missing_fields = SNAPSHOT_FIELDS - raw_fields
    if unknown_fields:
        errors.append("snapshot.unknown_fields:" + ",".join(sorted(unknown_fields)))
    if missing_fields:
        errors.append("snapshot.missing_fields:" + ",".join(sorted(missing_fields)))
    if not persisted and any(
        isinstance(item, dict) and "event_family_id" in item
        for item in (
            raw.get("non_material_evidence_dispositions", [])
            if isinstance(raw.get("non_material_evidence_dispositions"), list)
            else []
        )
    ):
        errors.append("snapshot.event_family_id_is_kernel_owned")
    _reject_unknown_keys(
        raw.get("core_judgment"), SNAPSHOT_ITEM_FIELDS["core_judgment"],
        errors, "core_judgment",
    )
    for field, limit in SNAPSHOT_LIST_LIMITS.items():
        values = raw.get(field)
        if not isinstance(values, list):
            errors.append(f"snapshot.list_required:{field}")
            continue
        if len(values) > limit:
            errors.append(f"snapshot.list_limit:{field}:{limit}")
        if field == "candidates_by_horizon":
            for group_index, group in enumerate(values, start=1):
                _reject_unknown_keys(
                    group, SNAPSHOT_ITEM_FIELDS["candidate_group"], errors,
                    f"candidates_by_horizon[{group_index}]",
                )
                candidates = group.get("candidates") if isinstance(group, dict) else None
                if not isinstance(candidates, list):
                    errors.append(
                        f"snapshot.candidate_list_required:{group_index}"
                    )
                    continue
                if len(candidates) > 20:
                    errors.append(f"snapshot.candidate_limit_20:{group_index}")
                for candidate_index, candidate in enumerate(candidates, start=1):
                    _reject_unknown_keys(
                        candidate, SNAPSHOT_ITEM_FIELDS["candidate"], errors,
                        f"candidate[{group_index}:{candidate_index}]",
                    )
            continue
        if field == "market_carriers_by_horizon":
            for group_index, group in enumerate(values, start=1):
                _reject_unknown_keys(
                    group, SNAPSHOT_ITEM_FIELDS["market_carrier_group"], errors,
                    f"market_carriers_by_horizon[{group_index}]",
                )
                carriers = group.get("carriers") if isinstance(group, dict) else None
                if not isinstance(carriers, list):
                    errors.append(
                        f"snapshot.market_carrier_list_required:{group_index}"
                    )
                    continue
                if len(carriers) > 20:
                    errors.append(
                        f"snapshot.market_carrier_limit_20:{group_index}"
                    )
                for carrier_index, carrier in enumerate(carriers, start=1):
                    _reject_unknown_keys(
                        carrier, SNAPSHOT_ITEM_FIELDS["market_carrier"], errors,
                        f"market_carrier[{group_index}:{carrier_index}]",
                    )
            continue
        item_contract = {
            "non_material_evidence_dispositions": "non_material_disposition"
        }.get(field, field)
        for index, item in enumerate(values, start=1):
            _reject_unknown_keys(
                item, SNAPSHOT_ITEM_FIELDS[item_contract], errors,
                f"{field}[{index}]",
            )
    snapshot["schema_version"] = SNAPSHOT_SCHEMA
    try:
        version = int(snapshot.get("version"))
    except (TypeError, ValueError):
        version = -1
    if persisted:
        if version <= 0:
            errors.append("snapshot.persisted_version_requires_positive")
    else:
        expected_version = int(previous.get("version", 0)) + 1
        if version != expected_version:
            errors.append(f"snapshot.version_requires:{expected_version}")
        expected_base = snapshot_hash(previous)
        if text(snapshot.get("base_snapshot_sha256")) != expected_base:
            errors.append("snapshot.base_hash_mismatch")
    if text(snapshot.get("as_of")) != task.get("as_of"):
        errors.append("snapshot.as_of_mismatch")
    status = _enum(snapshot.get("decision_status"), DECISION_STATUSES)
    if not status:
        errors.append("snapshot.decision_status_invalid")
    else:
        snapshot["decision_status"] = status
    if not text(snapshot.get("boundary")):
        errors.append("snapshot.boundary_required")

    evidence = evidence_index(store)
    _validate_item_numeric_text(
        snapshot, ("boundary",), snapshot.get("consumed_evidence_ids", []),
        evidence, errors, "snapshot",
    )
    core = snapshot.get("core_judgment", {})
    if not text(core.get("claim_id")) or not text(core.get("summary")):
        errors.append("snapshot.core_judgment_required")
    core_boundary = _enum(core.get("boundary"), EVIDENCE_BOUNDARIES)
    if not core_boundary:
        errors.append("snapshot.core_boundary_invalid")
    core["boundary"] = core_boundary or text(core.get("boundary"))
    _validate_evidence_refs(core.get("evidence_ids", []), evidence, errors, "core_judgment")
    _validate_item_numeric_text(
        core, ("summary",), core.get("evidence_ids", []), evidence, errors,
        "core_judgment",
    )
    if core_boundary and core_boundary != "HYPOTHESIS" and not core.get("evidence_ids"):
        errors.append("snapshot.core_non_hypothesis_requires_evidence")
    if status == "DECISION_READY" and not core.get("evidence_ids"):
        errors.append("snapshot.ready_core_requires_evidence")

    task_questions = {
        item.get("question_id"): item.get("question")
        for item in task.get("questions", [])
    }
    question_ids = set(task_questions)
    high_question_ids = {
        item.get("question_id") for item in task.get("questions", [])
        if item.get("decision_impact") == "HIGH"
    }
    answer_ids = set()
    for item in snapshot.get("agenda_answers", []):
        question_id = text(item.get("question_id"))
        if question_id not in question_ids:
            errors.append(f"snapshot.answer_question_unknown:{question_id}")
        elif text(item.get("question")) != text(task_questions.get(question_id)):
            errors.append(f"snapshot.answer_question_text_drift:{question_id}")
        if question_id in answer_ids:
            errors.append(f"snapshot.answer_duplicate:{question_id}")
        answer_ids.add(question_id)
        if _enum(item.get("status"), ANSWER_STATUSES) == "":
            errors.append(f"snapshot.answer_status_invalid:{question_id}")
        if not text(item.get("answer")):
            errors.append(f"snapshot.answer_required:{question_id}")
        answer_boundary = _enum(item.get("boundary"), EVIDENCE_BOUNDARIES)
        if not answer_boundary:
            errors.append(f"snapshot.answer_boundary_invalid:{question_id}")
        else:
            item["boundary"] = answer_boundary
        availability = _enum(
            item.get("next_test_availability"), NEXT_TEST_AVAILABILITIES, "UNKNOWN"
        )
        item["next_test_availability"] = availability
        _validate_evidence_refs(item.get("evidence_ids", []), evidence, errors, question_id)
        _validate_item_numeric_text(
            item,
            ("answer", "self_countercase", "missing_information"),
            item.get("evidence_ids", []), evidence, errors,
            f"agenda_answers.{question_id}",
        )
        if item.get("boundary") != "HYPOTHESIS" and not item.get("evidence_ids"):
            errors.append(f"snapshot.answer_requires_evidence:{question_id}")
    if answer_ids != question_ids:
        errors.append(
            "snapshot.answers_must_cover_task_questions:"
            + ",".join(sorted(question_ids - answer_ids))
        )
    if status == "DECISION_READY":
        for item in snapshot.get("agenda_answers", []):
            if (
                item.get("question_id") in high_question_ids
                and _enum(item.get("status"), ANSWER_STATUSES) in {"OPEN", "DISPUTED"}
            ):
                errors.append(
                    f"snapshot.ready_high_question_unresolved:{item.get('question_id')}"
                )

    for field in (
        "material_changes", "open_material_gaps", "value_transfer_paths",
        "market_by_horizon", "self_countercases",
        "unresolved_questions", "lowest_cost_next_validation",
    ):
        for index, item in enumerate(snapshot.get(field, []), start=1):
            _validate_evidence_refs(
                item.get("evidence_ids", []), evidence, errors, f"{field}[{index}]"
            )

    seen_change_ids = set()
    for item in snapshot.get("material_changes", []):
        change_id = text(item.get("change_id"))
        if not change_id or change_id in seen_change_ids:
            errors.append("snapshot.material_change_id_required_unique")
        seen_change_ids.add(change_id)
        for field in ("title", "summary", "decision_effect"):
            if not text(item.get(field)):
                errors.append(
                    f"snapshot.material_change_{field}_required:{change_id or 'UNKNOWN'}"
                )
        boundary = _enum(item.get("boundary"), EVIDENCE_BOUNDARIES)
        if not boundary:
            errors.append(f"snapshot.material_change_boundary_invalid:{change_id}")
        else:
            item["boundary"] = boundary
        if not item.get("evidence_ids"):
            errors.append(
                f"snapshot.material_change_requires_evidence:{change_id or 'UNKNOWN'}"
            )
        _validate_item_numeric_text(
            item, ("title", "summary", "decision_effect"),
            item.get("evidence_ids", []), evidence, errors,
            f"material_changes.{change_id}",
        )

    seen_gap_ids = set()
    for item in snapshot.get("open_material_gaps", []):
        gap_id = text(item.get("gap_id"))
        if not gap_id or gap_id in seen_gap_ids or not text(item.get("description")):
            errors.append("snapshot.material_gap_id_description_required_unique")
        seen_gap_ids.add(gap_id)
        _validate_item_numeric_text(
            item, ("description",), item.get("evidence_ids", []), evidence,
            errors, f"open_material_gaps.{gap_id or 'UNKNOWN'}",
        )

    current_claim_ids = _claim_ids(snapshot)
    for item in snapshot.get("self_countercases", []):
        target = text(item.get("target_claim_id"))
        if target not in current_claim_ids or not text(item.get("argument")):
            errors.append(f"snapshot.self_countercase_invalid:{target or 'UNKNOWN'}")
        _validate_item_numeric_text(
            item, ("argument",), item.get("evidence_ids", []), evidence,
            errors, f"self_countercases.{target or 'UNKNOWN'}",
        )

    seen_market_view_ids = set()
    seen_market_horizons = set()
    for item in snapshot.get("market_by_horizon", []):
        horizon = text(item.get("horizon")).upper()
        if horizon not in task.get("horizons", []):
            errors.append("snapshot.market_horizon_out_of_scope")
        if horizon in seen_market_horizons:
            errors.append(f"snapshot.market_horizon_duplicate:{horizon}")
        seen_market_horizons.add(horizon)
        market_view_id = text(item.get("market_view_id"))
        if not market_view_id or market_view_id in seen_market_view_ids:
            errors.append("snapshot.market_view_id_required_unique")
        seen_market_view_ids.add(market_view_id)
        for field in ("current_state", "mechanism", "switch_condition"):
            if not text(item.get(field)):
                errors.append(f"snapshot.market_view_{field}_required:{horizon}")
        boundary = _enum(item.get("boundary"), EVIDENCE_BOUNDARIES)
        if not boundary:
            errors.append(f"snapshot.market_view_boundary_invalid:{horizon}")
        else:
            item["boundary"] = boundary
        _validate_item_numeric_text(
            item, ("current_state", "mechanism", "switch_condition"),
            item.get("evidence_ids", []), evidence, errors,
            f"market_by_horizon.{horizon}",
        )

    value_paths = {}
    for item in snapshot.get("value_transfer_paths", []):
        path_id = text(item.get("path_id"))
        if not path_id or path_id in value_paths:
            errors.append("snapshot.value_path_id_required_unique")
        else:
            value_paths[path_id] = item
        for field in (
            "constraint_change", "profit_pool_shift", "economic_exposure",
            "market_carrier",
        ):
            if not text(item.get(field)):
                errors.append(f"snapshot.value_path_{field}_required:{path_id or 'UNKNOWN'}")
        if not item.get("evidence_ids"):
            errors.append(f"snapshot.value_path_requires_evidence:{path_id or 'UNKNOWN'}")
        elif not any(
            evidence_has_role(
                evidence.get(evidence_id, {}),
                "CURRENT_REALITY", "ECONOMIC_EXPOSURE", "CATALYST", "RISK",
            )
            for evidence_id in item.get("evidence_ids", [])
        ):
            errors.append(
                f"snapshot.value_path_requires_non_market_evidence:{path_id or 'UNKNOWN'}"
            )
        boundary = _enum(item.get("boundary"), EVIDENCE_BOUNDARIES)
        if not boundary:
            errors.append(f"snapshot.value_path_boundary_invalid:{path_id or 'UNKNOWN'}")
        else:
            item["boundary"] = boundary
        _validate_item_numeric_text(
            item,
            ("constraint_change", "profit_pool_shift", "economic_exposure", "market_carrier"),
            item.get("evidence_ids", []), evidence, errors,
            f"value_transfer_paths.{path_id}",
        )

    for item in snapshot.get("market_by_horizon", []):
        if not item.get("evidence_ids"):
            errors.append(
                f"snapshot.market_view_requires_evidence:{item.get('horizon') or 'UNKNOWN'}"
            )
        elif text(item.get("horizon")).upper() in {
            "EVENT_DAYS", "TACTICAL_WEEKS"
        } and not any(
            evidence_has_role(
                evidence.get(evidence_id, {}), "MARKET_STATE", "TECHNICAL_STATE"
            )
            for evidence_id in item.get("evidence_ids", [])
        ):
            errors.append(
                f"snapshot.market_view_requires_market_evidence:"
                f"{item.get('horizon') or 'UNKNOWN'}"
            )
    if snapshot.get("market_by_horizon") and not any(
        evidence_has_role(item, "MARKET_STATE", "TECHNICAL_STATE")
        for view in snapshot.get("market_by_horizon", [])
        for evidence_id in view.get("evidence_ids", [])
        for item in [evidence.get(evidence_id, {})]
    ):
        errors.append("snapshot.market_horizon_set_requires_market_anchor")

    market_views_by_horizon = {
        text(item.get("horizon")).upper(): item
        for item in snapshot.get("market_by_horizon", [])
        if text(item.get("horizon"))
    }

    seen_carrier_horizons = set()
    for group in snapshot.get("market_carriers_by_horizon", []):
        horizon = text(group.get("horizon")).upper()
        if horizon not in task.get("horizons", []):
            errors.append(f"snapshot.market_carrier_horizon_out_of_scope:{horizon}")
        if horizon in seen_carrier_horizons:
            errors.append(f"snapshot.market_carrier_horizon_duplicate:{horizon}")
        seen_carrier_horizons.add(horizon)
        seen_carriers = set()
        for carrier in group.get("carriers", []):
            carrier_path = text(
                carrier.get("ticker") or carrier.get("name") or "UNKNOWN"
            )
            security_id = normalize_security_id(
                f"{text(carrier.get('ticker')).upper()}@"
                f"{normalize_exchange(carrier.get('exchange'))}"
            )
            if security_id in seen_carriers:
                errors.append(
                    f"snapshot.market_carrier_duplicate_in_horizon:{carrier_path}"
                )
            seen_carriers.add(security_id)
            for field in (
                "claim_id", "name", "ticker", "exchange", "market_role",
                "why_traded", "closest_alternative", "switch_condition",
            ):
                if not text(carrier.get(field)):
                    errors.append(
                        f"snapshot.market_carrier_{field}_required:{carrier_path}"
                    )
            if not SECURITY_ID_RE.fullmatch(security_id):
                errors.append(
                    f"snapshot.market_carrier_security_identity_invalid:{carrier_path}"
                )
            boundary = _enum(carrier.get("boundary"), EVIDENCE_BOUNDARIES)
            if not boundary:
                errors.append(
                    f"snapshot.market_carrier_boundary_invalid:{carrier_path}"
                )
            else:
                carrier["boundary"] = boundary
            refs = carrier.get("evidence_ids", [])
            market_refs = carrier.get("market_evidence_ids", [])
            alternative_refs = carrier.get("alternative_evidence_ids", [])
            _validate_evidence_refs(
                refs, evidence, errors, f"market_carrier:{carrier_path}"
            )
            _validate_evidence_refs(
                market_refs, evidence, errors,
                f"market_carrier_market:{carrier_path}",
            )
            if not market_refs or not set(market_refs).issubset(set(refs)):
                errors.append(
                    f"snapshot.market_carrier_market_evidence_required:{carrier_path}"
                )
            if any(
                security_id not in evidence.get(evidence_id, {}).get("security_ids", [])
                or not evidence_has_role(
                    evidence.get(evidence_id, {}),
                    "MARKET_STATE", "TECHNICAL_STATE",
                )
                for evidence_id in market_refs
            ):
                errors.append(
                    f"snapshot.market_carrier_market_binding_invalid:{carrier_path}"
                )
            _validate_alternative_binding(
                carrier, refs, evidence, errors,
                path=f"market_carrier:{carrier_path}",
                current_security_id=security_id,
            )
            _validate_item_numeric_text(
                carrier,
                ("name", "market_role", "why_traded", "closest_alternative", "switch_condition"),
                refs, evidence, errors,
                f"market_carriers_by_horizon.{horizon}.{carrier_path}",
            )

    seen_candidate_horizons = set()
    for group in snapshot.get("candidates_by_horizon", []):
        horizon = text(group.get("horizon")).upper()
        if horizon not in task.get("horizons", []):
            errors.append(f"snapshot.candidate_horizon_out_of_scope:{horizon}")
        if horizon in seen_candidate_horizons:
            errors.append(f"snapshot.candidate_horizon_duplicate:{horizon}")
        seen_candidate_horizons.add(horizon)
        seen_candidate_securities = set()
        for candidate in group.get("candidates", []):
            candidate_path = text(candidate.get("ticker") or candidate.get("name") or "UNKNOWN")
            candidate_key = (
                text(candidate.get("ticker")).upper(),
                normalize_exchange(candidate.get("exchange")),
                text(candidate.get("name")),
            )
            if candidate_key in seen_candidate_securities:
                errors.append(
                    f"snapshot.candidate_duplicate_in_horizon:{candidate_path}"
                )
            seen_candidate_securities.add(candidate_key)
            refs = candidate.get("evidence_ids", [])
            _validate_evidence_refs(refs, evidence, errors, candidate_path)
            exposure_refs = candidate.get("exposure_evidence_ids", [])
            market_refs = candidate.get("market_evidence_ids", [])
            alternative_refs = candidate.get("alternative_evidence_ids", [])
            _validate_evidence_refs(
                exposure_refs, evidence, errors, f"candidate_exposure:{candidate_path}"
            )
            _validate_evidence_refs(
                market_refs, evidence, errors, f"candidate_market:{candidate_path}"
            )
            _validate_evidence_refs(
                alternative_refs, evidence, errors,
                f"candidate_alternative:{candidate_path}",
            )
            if not set(exposure_refs + market_refs + alternative_refs).issubset(set(refs)):
                errors.append(f"snapshot.candidate_split_evidence_not_in_total:{candidate_path}")
            stance = _enum(candidate.get("stance"), CANDIDATE_STANCES)
            if not stance:
                errors.append(f"snapshot.candidate_stance_invalid:{candidate_path}")
                continue
            candidate["stance"] = stance
            if stance == "NO_SETUP":
                semantic_fields = (
                    "name", "ticker", "exchange", "economic_exposure",
                    "market_role", "why_now", "closest_alternative",
                    "switch_condition", "trigger", "invalidation",
                    "price_crowding_boundary", "boundary",
                )
                reference_fields = (
                    "value_path_ids", "exposure_evidence_ids",
                    "market_evidence_ids", "alternative_evidence_ids",
                    "evidence_ids",
                )
                if any(text(candidate.get(field)) for field in semantic_fields) or any(
                    candidate.get(field) for field in reference_fields
                ):
                    errors.append(
                        f"snapshot.no_setup_must_be_empty_sentinel:{candidate_path}"
                    )
                continue

            for identity_field in ("name", "ticker", "exchange"):
                if not text(candidate.get(identity_field)):
                    errors.append(
                        f"snapshot.candidate_{identity_field}_required:{candidate_path}"
                    )
            candidate_boundary = _enum(
                candidate.get("boundary"), EVIDENCE_BOUNDARIES
            )
            if not candidate_boundary:
                errors.append(
                    f"snapshot.candidate_boundary_invalid:{candidate_path}"
                )
            else:
                candidate["boundary"] = candidate_boundary
            if not refs:
                errors.append(f"snapshot.candidate_requires_evidence:{candidate_path}")
            candidate_security_id = normalize_security_id(
                f"{text(candidate.get('ticker')).upper()}@"
                f"{normalize_exchange(candidate.get('exchange'))}"
            )
            _validate_alternative_binding(
                candidate, refs, evidence, errors,
                path=f"candidate:{candidate_path}",
                current_security_id=candidate_security_id,
            )
            required = (
                "name", "ticker", "exchange", "economic_exposure", "market_role",
                "why_now", "closest_alternative", "switch_condition", "trigger",
                "invalidation", "price_crowding_boundary",
            )
            if stance in {"WATCH", "CONDITIONAL_PRIORITY"}:
                stance_label = (
                    "priority" if stance == "CONDITIONAL_PRIORITY" else "watch"
                )
                missing = [field for field in required if not text(candidate.get(field))]
                if missing:
                    errors.append(
                        f"snapshot.{stance_label}_candidate_missing:"
                        f"{candidate_path}:{','.join(missing)}"
                    )
                if not refs:
                    errors.append(
                        f"snapshot.{stance_label}_candidate_requires_evidence:"
                        f"{candidate_path}"
                    )
                if not exposure_refs:
                    errors.append(
                        f"snapshot.{stance_label}_candidate_exposure_evidence_required:"
                        f"{candidate_path}"
                    )
                if not market_refs:
                    errors.append(
                        f"snapshot.{stance_label}_candidate_market_evidence_required:"
                        f"{candidate_path}"
                    )
                if horizon not in market_views_by_horizon:
                    errors.append(
                        f"snapshot.{stance_label}_candidate_market_view_required:"
                        f"{candidate_path}"
                    )
                if not SECURITY_ID_RE.fullmatch(candidate_security_id):
                    errors.append(
                        f"snapshot.{stance_label}_candidate_security_identity_invalid:"
                        f"{candidate_path}"
                    )
                if any(
                    evidence.get(evidence_id, {}).get("security_ids")
                    != [candidate_security_id]
                    or not evidence_has_role(
                        evidence.get(evidence_id, {}), "ECONOMIC_EXPOSURE"
                    )
                    for evidence_id in exposure_refs
                ):
                    errors.append(
                        f"snapshot.{stance_label}_candidate_exposure_binding_invalid:"
                        f"{candidate_path}"
                    )
                if any(
                    evidence.get(evidence_id, {}).get("security_ids")
                    != [candidate_security_id]
                    or not evidence_has_role(
                        evidence.get(evidence_id, {}),
                        "MARKET_STATE", "TECHNICAL_STATE",
                    )
                    for evidence_id in market_refs
                ):
                    errors.append(
                        f"snapshot.{stance_label}_candidate_market_binding_invalid:"
                        f"{candidate_path}"
                    )
                market_view = market_views_by_horizon.get(horizon, {})
                if market_refs and not set(market_refs).intersection(
                    market_view.get("evidence_ids", [])
                ):
                    errors.append(
                        f"snapshot.{stance_label}_candidate_market_view_disconnected:"
                        f"{candidate_path}"
                    )

            if stance == "CONDITIONAL_PRIORITY":
                path_ids = candidate.get("value_path_ids", [])
                if not path_ids or any(path_id not in value_paths for path_id in path_ids):
                    errors.append(f"snapshot.priority_candidate_value_path_required:{candidate_path}")
                bound_path_evidence = set()
                for path_id in path_ids:
                    bound_path_evidence.update(
                        value_paths.get(path_id, {}).get("evidence_ids", [])
                    )
                if exposure_refs and not set(exposure_refs).intersection(
                    bound_path_evidence
                ):
                    errors.append(
                        f"snapshot.priority_candidate_exposure_path_disconnected:{candidate_path}"
                    )
                if status != "DECISION_READY":
                    errors.append(f"snapshot.priority_requires_decision_ready:{candidate_path}")
            _validate_item_numeric_text(
                candidate,
                (
                    "name", "economic_exposure", "market_role", "why_now",
                    "closest_alternative", "switch_condition", "trigger",
                    "invalidation", "price_crowding_boundary",
                ),
                refs, evidence, errors,
                f"candidates_by_horizon.{horizon}.{candidate_path}",
            )

    receipts = challenge_receipt_index(ledger)
    challenge_packets = {
        item.get("challenge_id"): item for item in ledger.get("challenge_packets", [])
        if isinstance(item, dict) and item.get("challenge_id")
    }
    seen_challenges = set()
    for item in snapshot.get("challenge_resolutions", []):
        challenge_id = text(item.get("challenge_id"))
        if not challenge_id or challenge_id in seen_challenges:
            errors.append("snapshot.challenge_id_required_unique")
        seen_challenges.add(challenge_id)
        resolution = _enum(item.get("resolution"), CHALLENGE_RESOLUTIONS)
        item["resolution"] = resolution
        if not resolution:
            errors.append(f"snapshot.challenge_resolution_invalid:{challenge_id}")
        if challenge_id not in receipts:
            errors.append(f"snapshot.challenge_without_receipt:{challenge_id}")
        packet = challenge_packets.get(challenge_id)
        if not packet:
            errors.append(f"snapshot.challenge_packet_missing:{challenge_id}")
        else:
            if text(item.get("challenge_packet_sha256")) != stable_hash(packet):
                errors.append(f"snapshot.challenge_packet_hash_mismatch:{challenge_id}")
            if _unique_text(item.get("target_claim_ids", [])) != packet.get(
                "target_claim_ids", []
            ):
                errors.append(f"snapshot.challenge_target_drift:{challenge_id}")
            packet_evidence = set(packet.get("evidence_ids", []))
            for attack in packet.get("attacks", []):
                packet_evidence.update(attack.get("evidence_ids", []))
            if not set(item.get("evidence_ids", [])).issubset(packet_evidence):
                errors.append(f"snapshot.challenge_evidence_drift:{challenge_id}")
        if not text(item.get("summary")) or not text(item.get("lead_response")):
            errors.append(f"snapshot.challenge_resolution_text_required:{challenge_id}")
        if not _unique_text(item.get("target_claim_ids", [])):
            errors.append(f"snapshot.challenge_targets_required:{challenge_id}")
        elif not set(_unique_text(item.get("target_claim_ids", []))).issubset(
            current_claim_ids
        ):
            errors.append(f"snapshot.challenge_target_not_in_snapshot:{challenge_id}")
        if resolution == "UNRESOLVED" and status == "DECISION_READY":
            errors.append(f"snapshot.unresolved_challenge_blocks_ready:{challenge_id}")
        _validate_evidence_refs(
            item.get("evidence_ids", []), evidence, errors, f"challenge:{challenge_id}"
        )
        _validate_item_numeric_text(
            item, ("summary", "lead_response"), item.get("evidence_ids", []),
            evidence, errors, f"challenge_resolutions.{challenge_id}",
        )

    dispositions = snapshot.get("non_material_evidence_dispositions", [])
    family_assessments = {}
    seen_disposition_evidence = set()
    generic_reasons = {
        "不影响判断", "不重要", "影响有限", "无重大影响", "暂不影响",
        "已打开判断不重要", "与本次研究无关",
    }
    for item in dispositions:
        evidence_id = item.get("evidence_id")
        family_id = text(item.get("event_family_id")).upper()
        dimension = _enum(
            item.get("decision_dimension"), MATERIAL_DECISION_DIMENSIONS
        )
        reason = text(item.get("reason"))
        reversal = text(item.get("reversal_condition"))
        derived_family_id = material_evidence_family_id(evidence.get(evidence_id, {}))
        if (
            evidence_id not in evidence
            or evidence_id in seen_disposition_evidence
            or not derived_family_id
            or family_id != derived_family_id
            or not dimension
            or not material_evidence_has_body_facts(store, evidence_id)
            or len(_semantic_text(reason)) < 10
            or _semantic_text(reason) in {
                _semantic_text(value) for value in generic_reasons
            }
            or len(_semantic_text(reversal)) < 6
        ):
            errors.append("snapshot.non_material_disposition_invalid")
        seen_disposition_evidence.add(evidence_id)
        item["event_family_id"] = family_id
        item["decision_dimension"] = dimension or text(
            item.get("decision_dimension")
        )
        assessment = (dimension, reason, reversal)
        prior_assessment = family_assessments.get(family_id)
        if prior_assessment and prior_assessment != assessment:
            errors.append(
                f"snapshot.event_family_assessment_conflict:{family_id}"
            )
        family_assessments[family_id] = assessment
        _validate_item_numeric_text(
            item, ("reason", "reversal_condition"), [evidence_id], evidence,
            errors, f"non_material_disposition.{evidence_id or 'UNKNOWN'}",
        )

    marker_ids = material_index_evidence_ids(store)
    material_outcome_evidence_owner = {}
    material_family_owner = {}
    for outcome, items, identity_field in (
        ("MATERIAL_CHANGE", snapshot.get("material_changes", []), "change_id"),
        ("OPEN_GAP", snapshot.get("open_material_gaps", []), "gap_id"),
    ):
        for item_index, item in enumerate(items, start=1):
            owner = text(item.get(identity_field)) or f"{outcome}-{item_index}"
            marker_families = set()
            for evidence_id in item.get("evidence_ids", []):
                prior_owner = material_outcome_evidence_owner.get(evidence_id)
                if prior_owner and prior_owner != (outcome, owner):
                    errors.append(
                        "snapshot.material_evidence_assigned_multiple_times:"
                        f"{evidence_id}"
                    )
                material_outcome_evidence_owner[evidence_id] = (outcome, owner)
                if evidence_id not in marker_ids:
                    continue
                family_id = material_evidence_family_id(
                    evidence.get(evidence_id, {})
                )
                if family_id:
                    marker_families.add(family_id)
            if len(marker_families) > 1:
                errors.append(
                    "snapshot.material_event_families_must_not_merge:"
                    f"{outcome}:{owner}"
                )
            for family_id in marker_families:
                family_key = (outcome, family_id)
                prior_owner = material_family_owner.get(family_key)
                if prior_owner and prior_owner != owner:
                    errors.append(
                        "snapshot.material_event_family_must_be_single_aggregate:"
                        f"{outcome}:{family_id}"
                    )
                material_family_owner[family_key] = owner

    change_ids = {
        evidence_id
        for item in snapshot.get("material_changes", [])
        for evidence_id in item.get("evidence_ids", [])
    }
    gap_ids = {
        evidence_id
        for item in snapshot.get("open_material_gaps", [])
        for evidence_id in item.get("evidence_ids", [])
    }
    disposition_ids = {
        item.get("evidence_id") for item in dispositions if item.get("evidence_id")
    }
    if change_ids.intersection(gap_ids | disposition_ids) or gap_ids.intersection(
        disposition_ids
    ):
        errors.append("snapshot.material_evidence_outcome_must_be_exclusive")
    family_outcomes = {}
    for outcome, evidence_ids in (
        ("MATERIAL_CHANGE", change_ids), ("OPEN_GAP", gap_ids),
        ("NON_MATERIAL", disposition_ids),
    ):
        for evidence_id in marker_ids.intersection(evidence_ids):
            family_id = material_evidence_family_id(evidence.get(evidence_id, {}))
            if not family_id:
                continue
            prior = family_outcomes.get(family_id)
            if prior and prior != outcome:
                errors.append(
                    f"snapshot.event_family_outcome_conflict:{family_id}"
                )
            family_outcomes[family_id] = outcome
    _validate_evidence_refs(
        snapshot.get("consumed_evidence_ids", []), evidence, errors, "consumed"
    )
    visible_evidence = snapshot_visible_evidence_ids(snapshot)
    if set(snapshot.get("consumed_evidence_ids", [])) != visible_evidence:
        errors.append("snapshot.consumed_evidence_must_equal_visible_references")
    # Snapshot references are the authoritative support links. EvidenceItem
    # claim_ids describe the source-time hypothesis and may legitimately become
    # stale after synthesis; forcing ID equality creates fake claims instead of
    # better semantics.

    for index, item in enumerate(
        snapshot.get("unresolved_questions", []), start=1
    ):
        if not text(item.get("question_id") or item.get("gap_id")) or not text(
            item.get("question") or item.get("description")
        ):
            errors.append(f"snapshot.unresolved_question_invalid:{index}")
        _validate_item_numeric_text(
            item, ("question", "description"), item.get("evidence_ids", []),
            evidence, errors, f"unresolved_questions.{index}",
        )
    for index, item in enumerate(
        snapshot.get("lowest_cost_next_validation", []), start=1
    ):
        availability = _enum(
            item.get("availability"), NEXT_TEST_AVAILABILITIES, ""
        )
        if not availability or not text(item.get("action")) or not text(
            item.get("expected_decision_delta")
        ):
            errors.append(f"snapshot.next_validation_invalid:{index}")
        else:
            item["availability"] = availability
        _validate_item_numeric_text(
            item, ("action", "expected_decision_delta"),
            item.get("evidence_ids", []), evidence, errors,
            f"lowest_cost_next_validation.{index}",
        )

    # Runtime obligations are evaluated only when accepting a new Lead
    # Snapshot.  A later host append intentionally makes the accepted Snapshot
    # stale and queues work for the next Lead; persisted validation must not
    # retroactively reject history or tempt a host-side semantic repair.
    if not persisted:
        _validate_snapshot_obligations(run, snapshot, status, errors)

    if errors:
        raise ResearchContractError(errors)
    return snapshot


def _normalize_receipt(receipt, *, role, action_id="", challenge_id=""):
    receipt = receipt if isinstance(receipt, dict) else {}
    receipt_id = text(receipt.get("receipt_id"))
    if not receipt_id:
        raise ResearchContractError(["receipt.id_required"])
    status = text(receipt.get("status") or "SUCCEEDED").upper()
    if status != "SUCCEEDED":
        raise ResearchContractError(["receipt.must_succeed_for_submission"])
    prompt_sha256 = text(receipt.get("prompt_sha256")).lower()
    payload_sha256 = text(receipt.get("payload_sha256")).lower()
    agent_id = text(receipt.get("agent_id"))
    isolation = text(receipt.get("isolation") or "UNVERIFIED").upper()
    provenance = text(
        receipt.get("receipt_provenance") or "SELF_DECLARED"
    ).upper()
    try:
        process_id = int(receipt.get("process_id") or 0)
    except (TypeError, ValueError):
        process_id = -1
    host_runtime = text(receipt.get("host_runtime")).lower()
    external_tools_enabled = receipt.get("external_tools_enabled") is True
    parent_agent_id = text(receipt.get("parent_agent_id"))
    attestation_level = text(receipt.get("attestation_level")).upper()
    if not SHA256_RE.fullmatch(prompt_sha256):
        raise ResearchContractError(["receipt.prompt_sha256_required"])
    if not SHA256_RE.fullmatch(payload_sha256):
        raise ResearchContractError(["receipt.payload_sha256_required"])
    if not agent_id:
        raise ResearchContractError(["receipt.agent_id_required"])
    if provenance not in RECEIPT_PROVENANCES:
        raise ResearchContractError(["receipt.provenance_invalid"])
    if provenance == "SELF_DECLARED" and (
        isolation != "UNVERIFIED" or process_id != 0 or external_tools_enabled
        or parent_agent_id or attestation_level not in {"", "UNVERIFIED"}
    ):
        raise ResearchContractError([
            "receipt.self_declared_receipt_must_be_unverified"
        ])
    if provenance == "HOST_PROCESS" and (
        isolation != "PROCESS_CONTEXT_REPORTED" or process_id <= 0 or not host_runtime
        or parent_agent_id
        or attestation_level != "PROCESS_REPORTED"
    ):
        raise ResearchContractError(["receipt.host_process_fields_invalid"])
    if provenance == "HARNESS_SUBAGENT" and (
        role != "CHALLENGER"
        or isolation != "SEPARATE_CONTEXT_REPORTED"
        or process_id != 0
        or external_tools_enabled
        or not host_runtime
        or not parent_agent_id
        or parent_agent_id == agent_id
        or attestation_level != "HARNESS_REPORTED"
    ):
        raise ResearchContractError(["receipt.harness_subagent_fields_invalid"])
    if provenance == "CONTROLLED_FIXTURE" and (
        isolation != "CONTROLLED_FIXTURE" or process_id != 0
        or external_tools_enabled
        or parent_agent_id
        or attestation_level not in {"", "CONTROLLED_FIXTURE"}
    ):
        raise ResearchContractError(["receipt.fixture_fields_invalid"])
    return {
        "receipt_id": receipt_id,
        "role": role,
        "status": "SUCCEEDED",
        "action_id": action_id,
        "challenge_id": challenge_id,
        "prompt_sha256": prompt_sha256,
        "payload_sha256": payload_sha256,
        "agent_id": agent_id,
        "isolation": isolation,
        "receipt_provenance": provenance,
        "process_id": process_id,
        "host_runtime": host_runtime,
        "external_tools_enabled": external_tools_enabled,
        "parent_agent_id": parent_agent_id,
        "attestation_level": (
            "UNVERIFIED" if provenance == "SELF_DECLARED"
            else "PROCESS_REPORTED" if provenance == "HOST_PROCESS"
            else "CONTROLLED_FIXTURE" if provenance == "CONTROLLED_FIXTURE"
            else "HARNESS_REPORTED"
        ),
    }


def bind_dispatch(run, *, call_mode, role, prompt_sha256):
    """Bind the exact next prompt before a model call; idempotent on replay."""
    validate_run_shape(run)
    call_mode = text(call_mode).upper()
    role = text(role).upper()
    prompt_sha256 = text(prompt_sha256).lower()
    if call_mode != text(run["run_ledger"].get("next_call")).upper():
        raise ResearchContractError(["dispatch.call_mode_mismatch"])
    if role not in {"LEAD", "CHALLENGER"}:
        raise ResearchContractError(["dispatch.role_invalid"])
    if not SHA256_RE.fullmatch(prompt_sha256):
        raise ResearchContractError(["dispatch.prompt_sha256_invalid"])
    expected = {
        "call_mode": call_mode,
        "role": role,
        "prompt_sha256": prompt_sha256,
        "base_snapshot_sha256": snapshot_hash(run["decision_snapshot"]),
    }
    existing = run["run_ledger"].get("pending_dispatch")
    if existing:
        if existing != expected:
            raise ResearchContractError(["dispatch.pending_dispatch_conflict"])
        return deepcopy(run)
    updated = deepcopy(run)
    updated["run_ledger"]["pending_dispatch"] = expected
    return updated


def register_host_invocation(run, record):
    """Bind one caller-reported external-process record to its payload."""
    validate_run_shape(run)
    record = record if isinstance(record, dict) else {}
    pending = run["run_ledger"].get("pending_dispatch")
    if not isinstance(pending, dict):
        raise ResearchContractError(["host_invocation.pending_dispatch_required"])
    normalized = {
        "invocation_id": text(record.get("invocation_id")),
        "role": text(record.get("role")).upper(),
        "host_runtime": text(record.get("host_runtime")).lower(),
        "host_executable": text(record.get("host_executable")),
        "process_id": record.get("process_id"),
        "exit_code": record.get("exit_code"),
        "timed_out": record.get("timed_out") is True,
        "prompt_sha256": text(record.get("prompt_sha256")).lower(),
        "payload_sha256": text(record.get("payload_sha256")).lower(),
        "external_tools_enabled": record.get("external_tools_enabled") is True,
    }
    errors = []
    try:
        normalized["process_id"] = int(normalized["process_id"])
        normalized["exit_code"] = int(normalized["exit_code"])
    except (TypeError, ValueError):
        errors.append("host_invocation.process_fields_invalid")
    if run["run_ledger"].get("execution_mode") != "EXTERNAL_PROCESS_REPORTED":
        errors.append("host_invocation.requires_reported_process_run")
    if (
        not normalized["invocation_id"] or not normalized["host_runtime"]
        or not normalized["host_executable"]
    ):
        errors.append("host_invocation.identity_required")
    if (
        normalized["role"] != pending.get("role")
        or normalized["prompt_sha256"] != pending.get("prompt_sha256")
    ):
        errors.append("host_invocation.dispatch_mismatch")
    if (
        normalized.get("process_id", 0) <= 0
        or normalized.get("exit_code") != 0
        or normalized["timed_out"]
        or not SHA256_RE.fullmatch(normalized["payload_sha256"])
    ):
        errors.append("host_invocation.unsuccessful_or_unbound_payload")
    if errors:
        raise ResearchContractError(errors)
    existing = {
        item.get("invocation_id"): item
        for item in run["run_ledger"].get("host_invocations", [])
        if isinstance(item, dict)
    }.get(normalized["invocation_id"])
    if existing:
        if existing != normalized:
            raise ResearchContractError(["host_invocation.id_collision"])
        return deepcopy(run)
    updated = deepcopy(run)
    updated["run_ledger"].setdefault("host_invocations", []).append(normalized)
    return updated


def _bound_submission_receipt(run, packet, receipt, *, role, call_mode,
                              action_id="", challenge_id=""):
    ledger = run["run_ledger"]
    pending = ledger.get("pending_dispatch")
    if not isinstance(pending, dict):
        raise ResearchContractError(["receipt.pending_dispatch_required"])
    if pending.get("role") != role or pending.get("call_mode") != call_mode:
        raise ResearchContractError(["receipt.dispatch_role_or_mode_mismatch"])
    normalized = _normalize_receipt(
        receipt, role=role, action_id=action_id, challenge_id=challenge_id
    )
    if normalized["prompt_sha256"] != pending.get("prompt_sha256"):
        raise ResearchContractError(["receipt.prompt_hash_mismatch"])
    if normalized["payload_sha256"] != stable_hash(packet):
        raise ResearchContractError(["receipt.payload_hash_mismatch"])
    if pending.get("base_snapshot_sha256") != snapshot_hash(run["decision_snapshot"]):
        raise ResearchContractError(["receipt.snapshot_base_drift"])
    provenance = normalized["receipt_provenance"]
    if provenance == "HOST_PROCESS":
        invocation = {
            item.get("invocation_id"): item
            for item in ledger.get("host_invocations", []) if isinstance(item, dict)
        }.get(normalized["receipt_id"])
        if not invocation or any((
            invocation.get("role") != role,
            invocation.get("prompt_sha256") != normalized["prompt_sha256"],
            invocation.get("payload_sha256") != normalized["payload_sha256"],
            invocation.get("process_id") != normalized["process_id"],
            invocation.get("host_runtime") != normalized["host_runtime"],
            invocation.get("external_tools_enabled")
            != normalized["external_tools_enabled"],
            normalized["agent_id"] != normalized["receipt_id"],
        )):
            raise ResearchContractError(["receipt.host_invocation_mismatch"])
    elif provenance == "CONTROLLED_FIXTURE":
        if ledger.get("execution_mode") != "CONTROLLED_FIXTURE":
            raise ResearchContractError(["receipt.fixture_requires_fixture_run"])
    elif provenance == "HARNESS_SUBAGENT":
        if ledger.get("execution_mode") != "HARNESS_ORCHESTRATED":
            raise ResearchContractError([
                "receipt.harness_subagent_requires_harness_run"
            ])
    if role == "CHALLENGER":
        if provenance not in {
            "HARNESS_SUBAGENT", "HOST_PROCESS", "CONTROLLED_FIXTURE"
        }:
            raise ResearchContractError([
                "receipt.challenger_requires_bounded_role_provenance"
            ])
        prior_leads = [
            item for item in ledger.get("calls", [])
            if isinstance(item, dict) and item.get("role") == "LEAD"
            and item.get("status") == "SUCCEEDED"
        ]
        if not prior_leads or prior_leads[-1].get("agent_id") == normalized["agent_id"]:
            raise ResearchContractError(["receipt.challenger_requires_distinct_agent"])
        if (
            provenance == "HARNESS_SUBAGENT"
            and normalized["parent_agent_id"] != prior_leads[-1].get("agent_id")
        ):
            raise ResearchContractError([
                "receipt.harness_parent_must_match_latest_lead"
            ])
    return normalized


def remaining_budget(ledger):
    return max(
        0,
        int(ledger.get("authorized_research_loops", 0))
        - int(ledger.get("completed_research_loops", 0)),
    )


def apply_lead_packet(run, packet, receipt, *, resolution=False):
    """Atomically apply one Lead research or challenge-resolution packet."""
    validate_run_shape(run)
    packet = packet if isinstance(packet, dict) else {}
    unknown_packet_fields = set(packet) - LEAD_PACKET_FIELDS
    missing_packet_fields = LEAD_PACKET_FIELDS - set(packet)
    if unknown_packet_fields or missing_packet_fields:
        raise ResearchContractError([
            "lead.packet_fields_invalid:unknown="
            + ",".join(sorted(unknown_packet_fields))
            + ":missing=" + ",".join(sorted(missing_packet_fields))
        ])
    updated = deepcopy(run)
    ledger = updated["run_ledger"]
    expected_call = "LEAD_RESOLUTION" if resolution else ledger.get("next_call")
    if expected_call not in {"LEAD_RESEARCH", "LEAD_SYNTHESIS", "LEAD_RESOLUTION"}:
        raise ResearchContractError([f"lead.call_mode_invalid:{expected_call}"])
    if ledger.get("next_call") != expected_call:
        raise ResearchContractError([
            f"lead.unexpected_call:{ledger.get('next_call')}:{expected_call}"
        ])
    pending_receipt = _bound_submission_receipt(
        run, packet, receipt, role="LEAD", call_mode=expected_call
    )
    intent = normalize_action_intent(
        packet.get("action_intent"),
        action_type="RESOLUTION" if resolution else "RESEARCH",
    )
    required_intent_type = "RESOLUTION" if resolution else "RESEARCH"
    if intent["action_type"] != required_intent_type:
        raise ResearchContractError([
            f"action_intent.type_requires:{required_intent_type}"
        ])
    packet_text_errors = []
    validate_numeric_text(
        packet.get("stop_reason"), [], path="lead.stop_reason",
        errors=packet_text_errors,
    )
    challenge_request_raw = packet.get("challenge_request")
    if isinstance(challenge_request_raw, dict):
        for field in ("question", "why_load_bearing"):
            validate_numeric_text(
                challenge_request_raw.get(field), [],
                path=f"lead.challenge_request.{field}",
                errors=packet_text_errors,
            )
    if packet_text_errors:
        raise ResearchContractError(packet_text_errors)
    if intent["action_id"] in {
        item.get("action_id") for item in ledger.get("action_intents", [])
        if isinstance(item, dict)
    }:
        raise ResearchContractError([
            f"action_intent.id_already_used:{intent['action_id']}"
        ])
    if expected_call == "LEAD_RESEARCH" and remaining_budget(ledger) <= 0:
        raise ResearchContractError(["lead.research_budget_exhausted"])
    if expected_call in {"LEAD_SYNTHESIS", "LEAD_RESOLUTION"} and (
        packet.get("evidence_items") or packet.get("source_checks")
    ):
        raise ResearchContractError([
            f"lead.{expected_call.lower()}_cannot_add_research_evidence"
        ])
    lead_evidence = []
    for raw in packet.get("evidence_items", []) if isinstance(
        packet.get("evidence_items"), list
    ) else []:
        item = deepcopy(raw) if isinstance(raw, dict) else raw
        if isinstance(item, dict):
            item["origin"] = "LEAD_RESEARCH"
        lead_evidence.append(item)
    existing_evidence_ids = set(evidence_index(updated["evidence_store"]))
    existing_source_check_ids = {
        item.get("source_check_id")
        for item in updated["evidence_store"].get("source_checks", [])
        if isinstance(item, dict)
    }
    store, evidence_ids = append_evidence_items(
        updated["evidence_store"], lead_evidence,
        as_of=updated["task_spec"]["as_of"],
    )
    store, source_check_ids = append_source_checks(
        store, packet.get("source_checks", []), task_spec=updated["task_spec"],
        origin=(
            "CONTROLLED_FIXTURE"
            if ledger.get("execution_mode") == "CONTROLLED_FIXTURE"
            else "LEAD_RESEARCH"
        ),
    )
    require_new_evidence_bound(
        store, set(evidence_index(store)) - existing_evidence_ids, source_check_ids
    )
    validate_document_fact_acquisition(store)
    updated["evidence_store"] = store
    validate_evidence_scope(updated["task_spec"], store)
    snapshot = normalize_and_validate_snapshot(
        packet.get("decision_snapshot"), run=updated, mode="RESOLUTION" if resolution else "LEAD"
    )
    new_evidence_ids = sorted(set(evidence_index(store)) - existing_evidence_ids)
    new_source_check_ids = sorted({
        item.get("source_check_id")
        for item in store.get("source_checks", []) if isinstance(item, dict)
    } - existing_source_check_ids)
    if (
        expected_call == "LEAD_RESEARCH"
        and not new_evidence_ids
        and not new_source_check_ids
    ):
        raise ResearchContractError(["lead.research_requires_observation_delta"])
    if semantic_snapshot_hash(run["decision_snapshot"]) == semantic_snapshot_hash(
        snapshot
    ):
        raise ResearchContractError([
            "action_intent.requires_semantic_snapshot_delta"
        ])
    updated["decision_snapshot"] = snapshot
    intent["status"] = "COMPLETED"
    intent["evidence_ids"] = new_evidence_ids
    intent["source_check_ids"] = new_source_check_ids
    intent["base_snapshot_sha256"] = snapshot["base_snapshot_sha256"]
    intent["snapshot_version"] = snapshot["version"]
    intent["snapshot_sha256"] = snapshot_hash(snapshot)
    intent["submission_payload_sha256"] = pending_receipt["payload_sha256"]
    intent["snapshot_frontier"] = snapshot_frontier(updated)
    ledger.setdefault("action_intents", []).append(intent)
    call = dict(pending_receipt)
    call["action_id"] = intent["action_id"]
    call["mode"] = expected_call
    ledger.setdefault("calls", []).append(call)
    ledger["evidence_store_sha256"] = stable_hash(updated["evidence_store"])
    ledger["decision_snapshot_sha256"] = snapshot_hash(snapshot)
    ledger.pop("pending_dispatch", None)
    if expected_call == "LEAD_RESEARCH":
        ledger["completed_research_loops"] += 1

    challenge_request = packet.get("challenge_request")
    if challenge_request:
        if resolution:
            raise ResearchContractError(["lead.resolution_cannot_request_challenger"])
        if packet.get("continue_research") is True:
            raise ResearchContractError(["lead.challenge_and_continue_are_mutually_exclusive"])
        if remaining_budget(ledger) <= 0:
            raise ResearchContractError(["lead.challenge_requires_remaining_budget"])
        fact_blockers = [
            item for item in hard_obligations(updated)
            if item.get("kind") in {
                "SOURCE_CHECK_REQUIRED", "HIGH_EVIDENCE_UNACCOUNTED"
            }
        ]
        if fact_blockers:
            raise ResearchContractError([
                "lead.challenge_requires_current_reality_complete"
            ])
        target_ids = _unique_text(challenge_request.get("target_claim_ids", []), limit=12)
        unknown = set(target_ids) - _claim_ids(snapshot)
        if not target_ids or unknown:
            raise ResearchContractError([
                "lead.challenge_targets_invalid:" + ",".join(sorted(unknown))
            ])
        challenge_id = text(challenge_request.get("challenge_id")).upper() or stable_id(
            "CH", snapshot_hash(snapshot), "|".join(target_ids)
        )
        if not ID_RE.fullmatch(challenge_id):
            raise ResearchContractError(["lead.challenge_id_invalid"])
        if challenge_id in {
            item.get("challenge_id") for item in ledger.get("challenge_packets", [])
            if isinstance(item, dict)
        }:
            raise ResearchContractError([f"lead.challenge_id_already_used:{challenge_id}"])
        ledger["pending_challenge_request"] = {
            "challenge_id": challenge_id,
            "target_claim_ids": target_ids,
            "question": text(challenge_request.get("question")),
            "why_load_bearing": text(challenge_request.get("why_load_bearing")),
            "snapshot_sha256": snapshot_hash(snapshot),
        }
        if not ledger["pending_challenge_request"]["question"] or not ledger[
            "pending_challenge_request"
        ]["why_load_bearing"]:
            raise ResearchContractError(["lead.challenge_request_requires_question_and_reason"])
        ledger["next_call"] = "CHALLENGER"
    else:
        ledger.pop("pending_challenge_request", None)
        if packet.get("continue_research") is True:
            if remaining_budget(ledger) <= 0:
                raise ResearchContractError(["lead.continue_requires_remaining_budget"])
        elif not text(packet.get("stop_reason")):
            raise ResearchContractError(["lead.stop_reason_required"])
        ledger["next_call"] = (
            "LEAD_RESEARCH"
            if remaining_budget(ledger) > 0 and packet.get("continue_research") is True
            else "REPORT"
        )
        if ledger["next_call"] == "REPORT":
            ledger["stopped_reason"] = text(packet.get("stop_reason")) or (
                "NO_HIGH_VALUE_ACTION" if remaining_budget(ledger) > 0 else "BUDGET_EXHAUSTED"
            )
    return updated


def apply_challenge_packet(run, packet, receipt):
    """Store a bounded ChallengePacket without letting it write the Snapshot."""
    validate_run_shape(run)
    packet = packet if isinstance(packet, dict) else {}
    unknown_packet_fields = set(packet) - CHALLENGE_PACKET_FIELDS
    missing_packet_fields = CHALLENGE_PACKET_FIELDS - set(packet)
    if unknown_packet_fields or missing_packet_fields:
        raise ResearchContractError([
            "challenge.packet_fields_invalid:unknown="
            + ",".join(sorted(unknown_packet_fields))
            + ":missing=" + ",".join(sorted(missing_packet_fields))
        ])
    updated = deepcopy(run)
    ledger = updated["run_ledger"]
    if ledger.get("next_call") != "CHALLENGER":
        raise ResearchContractError(["challenge.not_requested"])
    if remaining_budget(ledger) <= 0:
        raise ResearchContractError(["challenge.budget_exhausted"])
    request = ledger.get("pending_challenge_request")
    if not isinstance(request, dict):
        raise ResearchContractError(["challenge.request_missing"])
    challenge_id = text(packet.get("challenge_id"))
    if challenge_id != request.get("challenge_id"):
        raise ResearchContractError(["challenge.id_mismatch"])
    target_claim_ids = _unique_text(packet.get("target_claim_ids", []), limit=12)
    if target_claim_ids != request.get("target_claim_ids"):
        raise ResearchContractError(["challenge.targets_mismatch"])
    pending_receipt = _bound_submission_receipt(
        run, packet, receipt, role="CHALLENGER", call_mode="CHALLENGER",
        challenge_id=challenge_id,
    )
    challenger_evidence = []
    for raw in packet.get("evidence_items", []) if isinstance(
        packet.get("evidence_items"), list
    ) else []:
        item = deepcopy(raw) if isinstance(raw, dict) else raw
        if isinstance(item, dict):
            item["origin"] = "CHALLENGER"
        challenger_evidence.append(item)
    existing_evidence_ids = set(evidence_index(updated["evidence_store"]))
    store, evidence_ids = append_evidence_items(
        updated["evidence_store"], challenger_evidence,
        as_of=updated["task_spec"]["as_of"],
    )
    store, source_check_ids = append_source_checks(
        store, packet.get("source_checks", []), task_spec=updated["task_spec"],
        origin=(
            "CONTROLLED_FIXTURE"
            if ledger.get("execution_mode") == "CONTROLLED_FIXTURE"
            else "CHALLENGER"
        ),
    )
    require_new_evidence_bound(
        store, set(evidence_index(store)) - existing_evidence_ids, source_check_ids
    )
    validate_document_fact_acquisition(store)
    updated["evidence_store"] = store
    validate_evidence_scope(updated["task_spec"], store)
    ledger["evidence_store_sha256"] = stable_hash(store)
    challenge_evidence_index = evidence_index(store)
    attacks = []
    attack_errors = []
    for index, raw in enumerate(packet.get("attacks", []) if isinstance(
        packet.get("attacks"), list
    ) else [], start=1):
        if not isinstance(raw, dict):
            continue
        target = text(raw.get("target_claim_id"))
        if target not in target_claim_ids or not text(raw.get("argument")):
            raise ResearchContractError([f"challenge.attack_invalid:{index}"])
        refs = _normalized_ref_ids(raw.get("evidence_ids", []), store)
        _validate_evidence_refs(
            refs, challenge_evidence_index, attack_errors, f"challenge:{index}"
        )
        _validate_item_numeric_text(
            raw, ("argument",), refs, challenge_evidence_index,
            attack_errors, f"challenge.attacks.{index}",
        )
        severity = text(raw.get("severity") or "LOAD_BEARING").upper()
        if severity != "LOAD_BEARING":
            raise ResearchContractError([
                f"challenge.attack_must_be_load_bearing:{index}"
            ])
        attacks.append({
            "target_claim_id": target,
            "argument": text(raw.get("argument")),
            "evidence_ids": refs,
            "severity": severity,
        })
    if not attacks:
        raise ResearchContractError(["challenge.attack_required"])
    if attack_errors:
        raise ResearchContractError(attack_errors)
    normalized = {
        "challenge_id": challenge_id,
        "target_claim_ids": target_claim_ids,
        "attacks": attacks,
        "evidence_ids": evidence_ids,
        "source_check_ids": source_check_ids,
        "submission_payload_sha256": pending_receipt["payload_sha256"],
        "strongest_countercase": text(packet.get("strongest_countercase")),
    }
    if not normalized["strongest_countercase"]:
        raise ResearchContractError(["challenge.strongest_countercase_required"])
    strongest_refs = list(dict.fromkeys(
        evidence_ids + [
            evidence_id
            for attack in attacks
            for evidence_id in attack.get("evidence_ids", [])
        ]
    ))
    strongest_errors = []
    validate_numeric_text(
        normalized["strongest_countercase"],
        [
            measure
            for evidence_id in strongest_refs
            for measure in challenge_evidence_index.get(evidence_id, {}).get(
                "measures", []
            )
            if isinstance(measure, dict)
        ],
        path="challenge.strongest_countercase", errors=strongest_errors,
    )
    if strongest_errors:
        raise ResearchContractError(strongest_errors)
    call = dict(pending_receipt)
    call["mode"] = "CHALLENGER"
    ledger.setdefault("calls", []).append(call)
    ledger.pop("pending_dispatch", None)
    ledger.setdefault("challenge_packets", []).append(normalized)
    ledger["completed_research_loops"] += 1
    ledger["next_call"] = "LEAD_RESOLUTION"
    ledger.pop("pending_challenge_request", None)
    return updated


def record_contract_rejection(run, packet, receipt, errors):
    """Record real model cost while leaving every semantic object untouched."""
    validate_run_shape(run)
    pending = run["run_ledger"].get("pending_dispatch")
    if not isinstance(pending, dict):
        raise ResearchContractError(["rejection.pending_dispatch_required"])
    role = text(pending.get("role")).upper()
    call_mode = text(pending.get("call_mode")).upper()
    challenge_id = ""
    if role == "CHALLENGER":
        request = run["run_ledger"].get("pending_challenge_request") or {}
        challenge_id = text(request.get("challenge_id"))
    normalized_receipt = _bound_submission_receipt(
        run, packet if isinstance(packet, dict) else {}, receipt,
        role=role, call_mode=call_mode, challenge_id=challenge_id,
    )
    normalized_errors = _unique_text(
        [text(error) for error in errors if text(error)]
        if isinstance(errors, (list, tuple, set)) else [errors],
        limit=40,
    )
    if not normalized_errors:
        raise ResearchContractError(["rejection.errors_required"])
    updated = deepcopy(run)
    ledger = updated["run_ledger"]
    rejection_id = normalized_receipt["receipt_id"]
    if rejection_id in {
        item.get("rejection_id") for item in ledger.get("rejections", [])
        if isinstance(item, dict)
    }:
        raise ResearchContractError([f"rejection.id_already_used:{rejection_id}"])
    ledger.setdefault("rejections", []).append({
        "rejection_id": rejection_id,
        "role": role,
        "call_mode": call_mode,
        "prompt_sha256": normalized_receipt["prompt_sha256"],
        "payload_sha256": normalized_receipt["payload_sha256"],
        "agent_id": normalized_receipt["agent_id"],
        "isolation": normalized_receipt["isolation"],
        "receipt_provenance": normalized_receipt["receipt_provenance"],
        "process_id": normalized_receipt["process_id"],
        "host_runtime": normalized_receipt["host_runtime"],
        "external_tools_enabled": normalized_receipt["external_tools_enabled"],
        "parent_agent_id": normalized_receipt["parent_agent_id"],
        "attestation_level": normalized_receipt["attestation_level"],
        "base_snapshot_sha256": pending["base_snapshot_sha256"],
        "errors": normalized_errors,
    })
    ledger.pop("pending_dispatch", None)
    return updated


def record_runtime_failure(run, *, role, reason, receipt_id=""):
    updated = deepcopy(run)
    ledger = updated["run_ledger"]
    call_mode = text(ledger.get("next_call")).upper()
    role = text(role).upper()
    expected_role = "CHALLENGER" if call_mode == "CHALLENGER" else "LEAD"
    if call_mode not in ALL_CALL_MODES:
        raise ResearchContractError(["runtime_failure.requires_active_model_call"])
    if role != expected_role:
        raise ResearchContractError(["runtime_failure.role_mode_mismatch"])
    if not text(reason):
        raise ResearchContractError(["runtime_failure.reason_required"])
    pending = ledger.get("pending_dispatch")
    if not isinstance(pending, dict) or (
        pending.get("call_mode") != call_mode or pending.get("role") != role
    ):
        raise ResearchContractError(["runtime_failure.pending_dispatch_required"])
    ledger.setdefault("failures", []).append({
        "role": role,
        "call_mode": call_mode,
        "reason": text(reason),
        "receipt_id": text(receipt_id),
        "prompt_sha256": pending.get("prompt_sha256"),
        "base_snapshot_sha256": pending.get("base_snapshot_sha256"),
    })
    ledger["retry_call"] = call_mode
    ledger.pop("pending_dispatch", None)
    ledger["next_call"] = "REPORT"
    ledger["stopped_reason"] = "RUNTIME_FAILURE"
    return updated


def _working_set_check_summary(check):
    """Keep enumeration proof in storage without replaying every title to the model."""
    summary = deepcopy(check)
    entries = summary.pop("index_entries", [])
    summary["index_manifest_sha256"] = stable_hash(entries) if entries else ""
    summary["index_manifest_entry_count"] = len(entries)
    summary["material_review_entries"] = [
        {
            "title": item.get("title"), "url": item.get("url"),
            "date": item.get("date"), "disposition": item.get("disposition"),
            "reason": item.get("reason"),
        }
        for item in entries
        if any(marker in text(item.get("title")) for marker in MATERIAL_TITLE_MARKERS)
    ]
    return summary


def compile_working_set(run, *, max_evidence=48, max_checks=32):
    """Compile bounded current semantics; never replay raw role history."""
    validate_run_shape(run)
    snapshot = run["decision_snapshot"]
    store = run["evidence_store"]
    referenced = set(snapshot.get("consumed_evidence_ids", []))
    for field in (
        "material_changes", "open_material_gaps", "agenda_answers",
        "value_transfer_paths", "market_by_horizon",
        "challenge_resolutions",
    ):
        for item in snapshot.get(field, []):
            referenced.update(item.get("evidence_ids", []))
    material_required_ids = {
        item.get("evidence_id")
        for item in (
            material_evidence_obligations(store, snapshot)
            + material_body_fact_obligations(store)
        )
    }
    high = [
        item for item in store.get("items", [])
        if item.get("decision_impact") == "HIGH"
        or item.get("evidence_id") in material_required_ids
    ]
    selected = []
    seen = set()
    # HIGH and already-visible evidence are correctness inputs, not truncation
    # candidates.  The bound applies only to additional context.
    required_ids = referenced | {item.get("evidence_id") for item in high}
    ordered = high + [
        item for item in store.get("items", [])
        if item.get("evidence_id") in referenced
    ] + list(reversed(store.get("items", [])))
    for item in ordered:
        evidence_id = item.get("evidence_id")
        if evidence_id in seen:
            continue
        if len(selected) >= max_evidence and evidence_id not in required_ids:
            continue
        selected.append(deepcopy(item))
        seen.add(evidence_id)
    latest_checks = {}
    for check in store.get("source_checks", []):
        latest_checks[(
            check.get("entity_id"), check.get("security_id", ""),
            check.get("fact_surface"),
        )] = check
    required_check_ids = {
        check.get("source_check_id") for check in latest_checks.values()
    }
    checks = []
    seen_checks = set()
    for check in list(reversed(store.get("source_checks", []))):
        check_id = check.get("source_check_id")
        if check_id in seen_checks:
            continue
        if len(checks) >= max_checks and check_id not in required_check_ids:
            continue
        checks.append(_working_set_check_summary(check))
        seen_checks.add(check_id)
    ledger = run["run_ledger"]
    return {
        "schema_version": WORKING_SET_SCHEMA,
        "task_spec": deepcopy(run["task_spec"]),
        "decision_snapshot": deepcopy(snapshot),
        "base_snapshot_sha256": snapshot_hash(snapshot),
        "hard_obligations": hard_obligations(run),
        "material_gap_requirements": material_gap_requirements(run, snapshot),
        "measure_contract": {
            "market_metrics": {
                metric: [
                    sorted(MEASURE_METRIC_UNITS[metric]),
                    sorted(contract[0]),
                    sorted(contract[1]),
                ]
                for metric, contract in MARKET_MEASURE_CONTRACTS.items()
            },
            "disclosure_metrics": {
                metric: [
                    sorted(MEASURE_METRIC_UNITS[metric]), sorted(surfaces)
                ]
                for metric, surfaces in DISCLOSURE_MEASURE_SURFACES.items()
            },
            "tuple_legend": {
                "market_metrics": ["units", "periods", "bases"],
                "disclosure_metrics": ["units", "fact_surfaces"],
            },
            "disclosure_defaults": {
                "periods": [
                    "POINT_IN_TIME", "QUARTER", "HALF_YEAR", "YEAR", "OTHER"
                ],
                "bases": ["DISCLOSURE_REPORTED", "PROVIDER_REPORTED"],
                "roles": "not MARKET_STATE/TECHNICAL_STATE only",
            },
            "basis_ids": sorted(MEASURE_BASES),
            "market_surface_and_roles": (
                "MARKET_PRICE_LIQUIDITY plus MARKET_STATE or TECHNICAL_STATE"
            ),
            "definition_rule": (
                "omit definition; registry supplies it"
            ),
            "subject_rule": (
                "subject_id must equal one entity_id or the single security_id "
                "on the same EvidenceItem"
            ),
        },
        "material_event_contract": {
            "decision_dimensions": sorted(MATERIAL_DECISION_DIMENSIONS),
            "controlled_event_types": sorted(
                event_type for event_type, _markers in MATERIAL_EVENT_RULES
            ),
            "host_only_body_extraction": True,
            "rules": [
                "marker evidence needs two host excerpts bound to a SourceCheck document hash",
                "choose exactly one outcome: material change, open gap, or non-material",
                "the kernel derives event_family_id; never merge event families",
            ],
        },
        "candidate_contract": {
            "allowed_stances": sorted(CANDIDATE_STANCES),
            "prohibited_stances": ["AVOID", "SHORT", "BUY", "SELL"],
            "watch_is_not_recommendation": True,
            "watch_requires": [
                "security identity", "economic exposure", "market role",
                "why now", "trigger", "invalidation", "crowding boundary",
                "security-bound exposure evidence", "security-bound market evidence",
            ],
            "no_setup_representation": "empty candidates list or an empty NO_SETUP sentinel; never name an alternative security",
        },
        "evidence_items": selected,
        "source_check_summaries": checks,
        "remaining_budget": remaining_budget(ledger),
        "execution_context": {
            "execution_mode": ledger.get("execution_mode"),
            "host_input_count": len(ledger.get("host_inputs", [])),
            "reported_context_is_not_independence_proof": True,
            "challenger_execution_preference": (
                "NATIVE_CODEX_SUBAGENT_THEN_OPTIONAL_CLI_ADAPTER"
            ),
        },
        "next_call": ledger.get("next_call"),
        "pending_challenge_request": deepcopy(ledger.get("pending_challenge_request")),
        "last_contract_rejection": deepcopy(
            ledger.get("rejections", [])[-1] if ledger.get("rejections") else None
        ),
        "latest_challenge_packet": deepcopy(
            ledger.get("challenge_packets", [])[-1]
            if ledger.get("challenge_packets") else None
        ),
        "latest_challenge_packet_sha256": (
            stable_hash(ledger.get("challenge_packets", [])[-1])
            if ledger.get("challenge_packets") else ""
        ),
        "output_contract": (
            "Return one LeadPacket with ActionIntent, new EvidenceItems/SourceChecks, "
            "and a full replacement DecisionSnapshot. Stored index manifests are represented "
            "here only by count and hash. Only the Lead writes the Snapshot."
        ),
    }


def delivery_state(run):
    obligations = hard_obligations(run)
    ledger = run["run_ledger"]
    snapshot = run["decision_snapshot"]
    calls = [item for item in ledger.get("calls", []) if isinstance(item, dict)]
    def receipt_descriptor(item):
        return " / ".join((
            text(item.get("receipt_provenance")) or "UNKNOWN",
            text(item.get("attestation_level")) or "UNKNOWN",
            text(item.get("isolation")) or "UNKNOWN",
        ))

    lead_receipts = sorted({
        receipt_descriptor(item) for item in calls
        if item.get("role") == "LEAD"
    })
    challenger_receipts = sorted({
        receipt_descriptor(item) for item in calls
        if item.get("role") == "CHALLENGER"
    })
    return {
        "decision_status": snapshot.get("decision_status"),
        "snapshot_version": snapshot.get("version"),
        "snapshot_sha256": snapshot_hash(snapshot),
        "hard_obligation_count": len(obligations),
        "hard_obligations": obligations,
        "authorized_research_loops": ledger.get("authorized_research_loops"),
        "completed_research_loops": ledger.get("completed_research_loops"),
        "remaining_budget": remaining_budget(ledger),
        "next_call": ledger.get("next_call"),
        "stopped_reason": ledger.get("stopped_reason"),
        "requested_execution_mode": ledger.get("execution_mode"),
        "achieved_execution": {
            "lead_receipts": lead_receipts or ["NONE"],
            "challenger_receipts": challenger_receipts or ["NONE"],
            "reported_subagent_challenge_count": sum(
                1 for item in calls
                if item.get("role") == "CHALLENGER"
                and item.get("receipt_provenance") == "HARNESS_SUBAGENT"
                and item.get("attestation_level") == "HARNESS_REPORTED"
            ),
            "reported_process_challenge_count": sum(
                1 for item in calls
                if item.get("role") == "CHALLENGER"
                and item.get("receipt_provenance") == "HOST_PROCESS"
                and item.get("attestation_level") == "PROCESS_REPORTED"
            ),
            "controlled_fixture_challenge_count": sum(
                1 for item in calls
                if item.get("role") == "CHALLENGER"
                and item.get("receipt_provenance") == "CONTROLLED_FIXTURE"
            ),
        },
        "failure_count": len(ledger.get("failures", [])),
        "rejection_count": len(ledger.get("rejections", [])),
        "accepted_model_call_count": len(ledger.get("calls", [])),
        "total_model_attempt_count": (
            len(ledger.get("calls", []))
            + len(ledger.get("rejections", []))
            + len(ledger.get("failures", []))
        ),
        "retry_call": ledger.get("retry_call"),
    }


def _list_has_prefix(before, after):
    return (
        isinstance(before, list) and isinstance(after, list)
        and len(after) >= len(before) and after[:len(before)] == before
    )


def validate_transition(
    before, after, *, allow_host_invocation_append=False,
    allow_budget_change=False,
):
    """Fail closed on destructive or host-side semantic state rewrites."""
    validate_run_shape(before)
    validate_run_shape(after)
    errors = []
    if before["task_spec"] != after["task_spec"]:
        errors.append("transition.task_spec_immutable")
    before_ledger = before["run_ledger"]
    after_ledger = after["run_ledger"]
    for field in ("method_identity", "execution_mode"):
        if before_ledger.get(field) != after_ledger.get(field):
            errors.append(f"transition.{field}_immutable")
    for field in ("items", "source_checks"):
        if not _list_has_prefix(
            before["evidence_store"].get(field),
            after["evidence_store"].get(field),
        ):
            errors.append(f"transition.evidence_store_{field}_append_only")
    before_aliases = before["evidence_store"].get("aliases", {})
    after_aliases = after["evidence_store"].get("aliases", {})
    if not isinstance(before_aliases, dict) or not isinstance(after_aliases, dict) or any(
        after_aliases.get(key) != value for key, value in before_aliases.items()
    ):
        errors.append("transition.evidence_aliases_append_only")
    append_only_ledger_fields = (
        "action_intents", "calls", "rejections", "failures",
        "challenge_packets", "host_inputs", "host_invocations",
    )
    for field in append_only_ledger_fields:
        if not _list_has_prefix(before_ledger.get(field), after_ledger.get(field)):
            errors.append(f"transition.{field}_append_only")
    if (
        after_ledger.get("host_invocations")
        != before_ledger.get("host_invocations")
        and not allow_host_invocation_append
    ):
        errors.append(
            "transition.host_invocations_require_reported_process_cas"
        )
    before_budget = int(before_ledger.get("authorized_research_loops", -1))
    after_budget = int(after_ledger.get("authorized_research_loops", -1))
    if before_budget != after_budget and not allow_budget_change:
        errors.append("transition.budget_change_requires_authorization_cas")
    elif allow_budget_change and after_budget < before_budget:
        errors.append("transition.authorized_budget_cannot_decrease")
    snapshot_changed = before["decision_snapshot"] != after["decision_snapshot"]
    new_actions = len(after_ledger.get("action_intents", [])) - len(
        before_ledger.get("action_intents", [])
    )
    new_lead_calls = sum(
        1 for item in after_ledger.get("calls", [])[len(before_ledger.get("calls", [])):]
        if isinstance(item, dict) and item.get("role") == "LEAD"
    )
    if snapshot_changed and (new_actions != 1 or new_lead_calls != 1):
        errors.append("transition.snapshot_requires_one_lead_action_and_call")
    if not snapshot_changed and new_actions:
        errors.append("transition.lead_action_requires_snapshot_change")
    if snapshot_changed:
        if int(after["decision_snapshot"].get("version", -1)) != int(
            before["decision_snapshot"].get("version", -1)
        ) + 1:
            errors.append("transition.snapshot_version_must_increment_one")
        if after["decision_snapshot"].get("base_snapshot_sha256") != snapshot_hash(
            before["decision_snapshot"]
        ):
            errors.append("transition.snapshot_base_hash_invalid")
    if errors:
        raise ResearchContractError(errors)
    return after


def validate_initial_run(run):
    """Accept only the deterministic pre-call state at create-CAS time."""
    validate_run_shape(run)
    task = run["task_spec"]
    snapshot = run["decision_snapshot"]
    ledger = run["run_ledger"]
    errors = []
    budget = int(task.get("budget", -1))
    if ledger.get("authorized_research_loops") != budget:
        errors.append("initial.authorized_budget_must_equal_task_budget")
    if ledger.get("completed_research_loops") != 0:
        errors.append("initial.completed_budget_must_be_zero")
    for field in (
        "action_intents", "calls", "rejections", "failures",
        "challenge_packets", "host_inputs", "host_invocations",
    ):
        if ledger.get(field) != []:
            errors.append(f"initial.{field}_must_be_empty")
    if ledger.get("stopped_reason"):
        errors.append("initial.stopped_reason_must_be_empty")
    if ledger.get("retry_call"):
        errors.append("initial.retry_call_forbidden")
    if ledger.get("pending_challenge_request"):
        errors.append("initial.pending_challenge_forbidden")
    expected_next = "LEAD_RESEARCH" if budget > 0 else "LEAD_SYNTHESIS"
    if ledger.get("next_call") != expected_next:
        errors.append("initial.next_call_invalid")
    pending = ledger.get("pending_dispatch")
    if pending is not None and (
        not isinstance(pending, dict)
        or pending.get("call_mode") != expected_next
        or pending.get("role") != "LEAD"
        or pending.get("base_snapshot_sha256") != snapshot_hash(snapshot)
    ):
        errors.append("initial.pending_dispatch_invalid")
    if snapshot != empty_snapshot(task):
        errors.append("initial.snapshot_must_be_empty")
    if errors:
        raise ResearchContractError(errors)
    return run


def validate_persisted_run(run, *, require_written_snapshot=True):
    """Detect tampering or semantic drift before dispatch, resume or render."""
    validate_run_shape(run)
    errors = []
    task = run["task_spec"]
    snapshot = run["decision_snapshot"]
    store = run["evidence_store"]
    ledger = run["run_ledger"]
    try:
        normalized_task = normalize_task_spec(
            task, round_budget=task.get("budget")
        )
        if normalized_task != task:
            errors.append("persisted.task_spec_not_canonical")
    except ResearchContractError as exc:
        errors.extend(f"persisted.{item}" for item in exc.errors)
    if ledger.get("task_spec_sha256") != stable_hash(task):
        errors.append("persisted.task_spec_hash_drift")
    if ledger.get("evidence_store_sha256") != stable_hash(store):
        errors.append("persisted.evidence_store_hash_drift")
    if ledger.get("decision_snapshot_sha256") != snapshot_hash(snapshot):
        errors.append("persisted.decision_snapshot_hash_drift")
    if not isinstance(ledger.get("method_identity"), dict):
        errors.append("persisted.method_identity_invalid")
    if text(ledger.get("execution_mode")).upper() not in EXECUTION_MODES:
        errors.append("persisted.execution_mode_invalid")
    try:
        state_revision = int(ledger.get("state_revision"))
    except (TypeError, ValueError):
        state_revision = -1
    if state_revision < 0 or state_revision != ledger.get("state_revision"):
        errors.append("persisted.state_revision_invalid")

    evidence_ids = set()
    evidence_signatures = {}
    for item in store.get("items", []) if isinstance(store.get("items"), list) else []:
        normalized = None
        try:
            normalized = normalize_evidence_item(item, as_of=task.get("as_of"))
            if normalized != item:
                errors.append(f"persisted.evidence_not_canonical:{item.get('evidence_id')}")
            if normalized.get("origin") not in EVIDENCE_ORIGINS:
                errors.append(
                    f"persisted.evidence_origin_invalid:{item.get('evidence_id')}"
                )
        except ResearchContractError as exc:
            errors.extend(f"persisted.{value}" for value in exc.errors)
        evidence_id = text(item.get("evidence_id"))
        if not evidence_id or evidence_id in evidence_ids:
            errors.append(f"persisted.evidence_id_duplicate:{evidence_id or 'EMPTY'}")
        evidence_ids.add(evidence_id)
        if normalized is not None:
            signature = evidence_signature(normalized)
            prior = evidence_signatures.get(signature)
            if prior and prior != evidence_id:
                errors.append(
                    f"persisted.evidence_signature_duplicate:{prior}:{evidence_id}"
                )
            evidence_signatures[signature] = evidence_id
    try:
        validate_evidence_scope(task, store)
    except ResearchContractError as exc:
        errors.extend(f"persisted.{value}" for value in exc.errors)
    aliases = store.get("aliases", {})
    if not isinstance(aliases, dict):
        errors.append("persisted.evidence_aliases_invalid")
    else:
        for alias, target in aliases.items():
            if (
                not ID_RE.fullmatch(text(alias))
                or not ID_RE.fullmatch(text(target))
                or alias in evidence_ids
                or target not in evidence_ids
                or alias == target
            ):
                errors.append(f"persisted.evidence_alias_invalid:{alias}")

    source_check_ids = set()
    for check in store.get("source_checks", []) if isinstance(
        store.get("source_checks"), list
    ) else []:
        try:
            normalized = normalize_source_check(check, task_spec=task, store=store)
            if normalized != check:
                errors.append(
                    f"persisted.source_check_not_canonical:{check.get('source_check_id')}"
                )
        except ResearchContractError as exc:
            errors.extend(f"persisted.{value}" for value in exc.errors)
        check_id = text(check.get("source_check_id"))
        if not check_id or check_id in source_check_ids:
            errors.append(f"persisted.source_check_id_duplicate:{check_id or 'EMPTY'}")
        source_check_ids.add(check_id)
    try:
        validate_document_fact_acquisition(store)
    except ResearchContractError as exc:
        errors.extend(f"persisted.{value}" for value in exc.errors)

    seed_input = ledger.get("seed_input")
    if seed_input is not None:
        if _validate_exact_record(
            seed_input, SEED_INPUT_FIELDS, errors, "seed_input"
        ):
            seed_evidence_ids = _unique_text(seed_input.get("evidence_ids", []))
            seed_source_check_ids = _unique_text(
                seed_input.get("source_check_ids", [])
            )
            if seed_evidence_ids != seed_input.get("evidence_ids"):
                errors.append("persisted.seed_evidence_ids_not_canonical")
            if seed_source_check_ids != seed_input.get("source_check_ids"):
                errors.append("persisted.seed_source_check_ids_not_canonical")
            if not set(seed_evidence_ids).issubset(evidence_ids):
                errors.append("persisted.seed_evidence_missing")
            if not set(seed_source_check_ids).issubset(source_check_ids):
                errors.append("persisted.seed_source_check_missing")
            expected_seed_hash = stable_hash({
                "evidence_bindings": [
                    {
                        "evidence_id": evidence_id,
                        "content_sha256": stable_hash(evidence_index(store)[evidence_id]),
                    }
                    for evidence_id in seed_evidence_ids if evidence_id in evidence_index(store)
                ],
                "source_check_bindings": [
                    {
                        "source_check_id": check_id,
                        "content_sha256": stable_hash({
                            item.get("source_check_id"): item
                            for item in store.get("source_checks", [])
                            if isinstance(item, dict)
                        }[check_id]),
                    }
                    for check_id in seed_source_check_ids
                    if check_id in {
                        item.get("source_check_id")
                        for item in store.get("source_checks", [])
                        if isinstance(item, dict)
                    }
                ],
            })
            if seed_input.get("content_sha256") != expected_seed_hash:
                errors.append("persisted.seed_input_hash_drift")

    raw_host_inputs = ledger.get("host_inputs")
    if not isinstance(raw_host_inputs, list):
        errors.append("persisted.host_inputs_must_be_list")
    host_input_ids = set()
    for index, host_input in enumerate(
        raw_host_inputs if isinstance(raw_host_inputs, list) else [], start=1
    ):
        if not _validate_exact_record(
            host_input, HOST_INPUT_FIELDS, errors, f"host_input[{index}]"
        ):
            continue
        input_id = text(host_input.get("input_id"))
        input_evidence_ids = _unique_text(host_input.get("evidence_ids", []))
        input_check_ids = _unique_text(host_input.get("source_check_ids", []))
        if (
            not ID_RE.fullmatch(input_id) or input_id in host_input_ids
            or input_evidence_ids != host_input.get("evidence_ids")
            or input_check_ids != host_input.get("source_check_ids")
            or not set(input_evidence_ids).issubset(evidence_ids)
            or not set(input_check_ids).issubset(source_check_ids)
        ):
            errors.append(f"persisted.host_input_invalid:{input_id or index}")
        host_input_ids.add(input_id)
        if set(input_evidence_ids).issubset(evidence_ids) and (
            host_input.get("content_sha256") != _host_input_content_hash(
                store, input_evidence_ids, input_check_ids
            )
        ):
            errors.append(f"persisted.host_input_hash_drift:{input_id}")

    raw_host_invocations = ledger.get("host_invocations")
    if not isinstance(raw_host_invocations, list):
        errors.append("persisted.host_invocations_must_be_list")
    host_invocations = {}
    for index, invocation in enumerate(
        raw_host_invocations if isinstance(raw_host_invocations, list) else [], start=1
    ):
        if not _validate_exact_record(
            invocation, HOST_INVOCATION_FIELDS, errors,
            f"host_invocation[{index}]",
        ):
            continue
        invocation_id = text(invocation.get("invocation_id"))
        if (
            not invocation_id or invocation_id in host_invocations
            or text(invocation.get("role")).upper() not in {"LEAD", "CHALLENGER"}
            or invocation.get("role") != text(invocation.get("role")).upper()
            or not text(invocation.get("host_runtime"))
            or not text(invocation.get("host_executable"))
            or not isinstance(invocation.get("process_id"), int)
            or invocation.get("process_id", 0) <= 0
            or invocation.get("exit_code") != 0
            or invocation.get("timed_out") is not False
            or not isinstance(invocation.get("external_tools_enabled"), bool)
            or not SHA256_RE.fullmatch(text(invocation.get("prompt_sha256")))
            or not SHA256_RE.fullmatch(text(invocation.get("payload_sha256")))
        ):
            errors.append(
                f"persisted.host_invocation_invalid:{invocation_id or index}"
            )
        host_invocations[invocation_id] = invocation

    try:
        original_budget = int(task.get("budget"))
        authorized = int(ledger.get("authorized_research_loops"))
        completed = int(ledger.get("completed_research_loops"))
    except (TypeError, ValueError):
        original_budget, authorized, completed = -1, -1, -1
    if not 0 <= original_budget <= authorized <= 10:
        errors.append("persisted.authorized_budget_invalid")
    if not 0 <= completed <= authorized:
        errors.append("persisted.completed_budget_invalid")
    next_call = text(ledger.get("next_call")).upper()
    if next_call not in {
        "LEAD_RESEARCH", "LEAD_SYNTHESIS", "CHALLENGER",
        "LEAD_RESOLUTION", "REPORT",
    }:
        errors.append("persisted.next_call_invalid")
    retry_call = text(ledger.get("retry_call")).upper()
    if retry_call:
        if (
            ledger.get("stopped_reason") != "RUNTIME_FAILURE"
            or next_call != "REPORT"
            or retry_call not in {
                "LEAD_RESEARCH", "LEAD_SYNTHESIS", "CHALLENGER", "LEAD_RESOLUTION"
            }
        ):
            errors.append("persisted.retry_call_invalid")
    elif ledger.get("stopped_reason") == "RUNTIME_FAILURE":
        errors.append("persisted.runtime_failure_missing_retry_call")

    raw_calls = ledger.get("calls")
    if not isinstance(raw_calls, list):
        errors.append("persisted.calls_must_be_list")
    calls = raw_calls if isinstance(raw_calls, list) else []
    receipt_ids = set()
    counted_loops = 0
    lead_calls = []
    challenger_calls = []
    last_lead_agent = ""
    for index, call in enumerate(calls, start=1):
        if not _validate_exact_record(
            call, CALL_RECORD_FIELDS, errors, f"call[{index}]"
        ):
            continue
        receipt_id = text(call.get("receipt_id"))
        if not receipt_id or receipt_id in receipt_ids:
            errors.append(f"persisted.receipt_id_duplicate:{receipt_id or 'EMPTY'}")
        receipt_ids.add(receipt_id)
        if call.get("status") != "SUCCEEDED":
            errors.append(f"persisted.call_status_invalid:{receipt_id}")
        if not SHA256_RE.fullmatch(text(call.get("prompt_sha256"))):
            errors.append(f"persisted.call_prompt_hash_invalid:{receipt_id}")
        if not SHA256_RE.fullmatch(text(call.get("payload_sha256"))):
            errors.append(f"persisted.call_payload_hash_invalid:{receipt_id}")
        if not text(call.get("agent_id")):
            errors.append(f"persisted.call_agent_id_required:{receipt_id}")
        provenance = text(call.get("receipt_provenance")).upper()
        if provenance not in RECEIPT_PROVENANCES:
            errors.append(f"persisted.call_provenance_invalid:{receipt_id}")
        elif provenance == "SELF_DECLARED" and (
            call.get("isolation") != "UNVERIFIED"
            or call.get("process_id") != 0
            or call.get("external_tools_enabled") is not False
            or text(call.get("parent_agent_id"))
            or call.get("attestation_level") != "UNVERIFIED"
        ):
            errors.append(f"persisted.call_self_declared_invalid:{receipt_id}")
        elif provenance == "CONTROLLED_FIXTURE" and (
            ledger.get("execution_mode") != "CONTROLLED_FIXTURE"
            or call.get("isolation") != "CONTROLLED_FIXTURE"
            or call.get("process_id") != 0
            or call.get("external_tools_enabled") is not False
            or text(call.get("parent_agent_id"))
            or call.get("attestation_level") != "CONTROLLED_FIXTURE"
        ):
            errors.append(f"persisted.call_fixture_invalid:{receipt_id}")
        elif provenance == "HOST_PROCESS":
            invocation = host_invocations.get(receipt_id)
            if not invocation or any((
                invocation.get("role") != call.get("role"),
                invocation.get("prompt_sha256") != call.get("prompt_sha256"),
                invocation.get("payload_sha256") != call.get("payload_sha256"),
                invocation.get("process_id") != call.get("process_id"),
                invocation.get("host_runtime") != call.get("host_runtime"),
                invocation.get("external_tools_enabled")
                != call.get("external_tools_enabled"),
                call.get("isolation") != "PROCESS_CONTEXT_REPORTED",
                call.get("agent_id") != receipt_id,
                text(call.get("parent_agent_id")),
                call.get("attestation_level") != "PROCESS_REPORTED",
            )):
                errors.append(f"persisted.call_host_invocation_drift:{receipt_id}")
        elif provenance == "HARNESS_SUBAGENT" and (
            ledger.get("execution_mode") != "HARNESS_ORCHESTRATED"
            or call.get("role") != "CHALLENGER"
            or call.get("isolation") != "SEPARATE_CONTEXT_REPORTED"
            or call.get("process_id") != 0
            or call.get("external_tools_enabled") is not False
            or not text(call.get("host_runtime"))
            or not text(call.get("parent_agent_id"))
            or text(call.get("parent_agent_id")) == text(call.get("agent_id"))
            or call.get("attestation_level") != "HARNESS_REPORTED"
        ):
            errors.append(f"persisted.call_harness_subagent_invalid:{receipt_id}")
        role = text(call.get("role")).upper()
        mode = text(call.get("mode")).upper()
        if role != call.get("role") or mode != call.get("mode"):
            errors.append(f"persisted.call_role_or_mode_not_canonical:{receipt_id}")
        if role == "LEAD" and mode in LEAD_CALL_MODES:
            lead_calls.append(call)
            last_lead_agent = text(call.get("agent_id"))
            if mode == "LEAD_RESEARCH":
                counted_loops += 1
            if not text(call.get("action_id")) or text(call.get("challenge_id")):
                errors.append(f"persisted.lead_call_binding_invalid:{receipt_id}")
        elif role == "CHALLENGER" and mode == "CHALLENGER":
            challenger_calls.append(call)
            counted_loops += 1
            if text(call.get("action_id")) or not text(call.get("challenge_id")):
                errors.append(f"persisted.challenger_call_binding_invalid:{receipt_id}")
            if provenance not in {
                "HARNESS_SUBAGENT", "HOST_PROCESS", "CONTROLLED_FIXTURE"
            }:
                errors.append(f"persisted.challenger_provenance_invalid:{receipt_id}")
            if not last_lead_agent or last_lead_agent == text(call.get("agent_id")):
                errors.append(f"persisted.challenger_agent_not_distinct:{receipt_id}")
            if (
                provenance == "HARNESS_SUBAGENT"
                and text(call.get("parent_agent_id")) != last_lead_agent
            ):
                errors.append(
                    f"persisted.challenger_parent_not_latest_lead:{receipt_id}"
                )
        else:
            errors.append(f"persisted.call_role_or_mode_invalid:{receipt_id}")

    raw_rejections = ledger.get("rejections")
    if not isinstance(raw_rejections, list):
        errors.append("persisted.rejections_must_be_list")
    rejections = raw_rejections if isinstance(raw_rejections, list) else []
    for index, rejection in enumerate(rejections, start=1):
        if not _validate_exact_record(
            rejection, REJECTION_RECORD_FIELDS, errors, f"rejection[{index}]"
        ):
            continue
        rejection_id = text(rejection.get("rejection_id"))
        role = text(rejection.get("role")).upper()
        mode = text(rejection.get("call_mode")).upper()
        expected_role = "CHALLENGER" if mode == "CHALLENGER" else "LEAD"
        rejection_errors = _unique_text(rejection.get("errors", []), limit=40)
        if not rejection_id or rejection_id in receipt_ids:
            errors.append(
                f"persisted.rejection_id_duplicate:{rejection_id or 'EMPTY'}"
            )
        receipt_ids.add(rejection_id)
        if (
            role != rejection.get("role")
            or mode != rejection.get("call_mode")
            or mode not in ALL_CALL_MODES
            or role != expected_role
            or not SHA256_RE.fullmatch(text(rejection.get("prompt_sha256")))
            or not SHA256_RE.fullmatch(text(rejection.get("payload_sha256")))
            or not SHA256_RE.fullmatch(text(rejection.get("base_snapshot_sha256")))
            or not text(rejection.get("agent_id"))
            or rejection_errors != rejection.get("errors")
            or not rejection_errors
        ):
            errors.append(f"persisted.rejection_invalid:{rejection_id}")
        rejection_provenance = text(
            rejection.get("receipt_provenance")
        ).upper()
        if rejection_provenance not in RECEIPT_PROVENANCES:
            errors.append(f"persisted.rejection_provenance_invalid:{rejection_id}")
        elif rejection_provenance == "SELF_DECLARED" and (
            rejection.get("isolation") != "UNVERIFIED"
            or rejection.get("process_id") != 0
            or rejection.get("external_tools_enabled") is not False
            or text(rejection.get("parent_agent_id"))
            or rejection.get("attestation_level") != "UNVERIFIED"
        ):
            errors.append(f"persisted.rejection_self_declared_invalid:{rejection_id}")
        elif rejection_provenance == "CONTROLLED_FIXTURE" and (
            ledger.get("execution_mode") != "CONTROLLED_FIXTURE"
            or rejection.get("isolation") != "CONTROLLED_FIXTURE"
            or rejection.get("process_id") != 0
            or rejection.get("external_tools_enabled") is not False
            or text(rejection.get("parent_agent_id"))
            or rejection.get("attestation_level") != "CONTROLLED_FIXTURE"
        ):
            errors.append(f"persisted.rejection_fixture_invalid:{rejection_id}")
        elif rejection_provenance == "HOST_PROCESS":
            invocation = host_invocations.get(rejection_id)
            if not invocation or any((
                invocation.get("role") != role,
                invocation.get("prompt_sha256") != rejection.get("prompt_sha256"),
                invocation.get("payload_sha256") != rejection.get("payload_sha256"),
                invocation.get("process_id") != rejection.get("process_id"),
                invocation.get("host_runtime") != rejection.get("host_runtime"),
                invocation.get("external_tools_enabled")
                != rejection.get("external_tools_enabled"),
                text(rejection.get("parent_agent_id")),
                rejection.get("isolation") != "PROCESS_CONTEXT_REPORTED",
                rejection.get("attestation_level") != "PROCESS_REPORTED",
            )):
                errors.append(
                    f"persisted.rejection_host_invocation_drift:{rejection_id}"
                )
        elif rejection_provenance == "HARNESS_SUBAGENT" and (
            ledger.get("execution_mode") != "HARNESS_ORCHESTRATED"
            or role != "CHALLENGER"
            or rejection.get("isolation") != "SEPARATE_CONTEXT_REPORTED"
            or rejection.get("process_id") != 0
            or rejection.get("external_tools_enabled") is not False
            or not text(rejection.get("host_runtime"))
            or not text(rejection.get("parent_agent_id"))
            or text(rejection.get("parent_agent_id"))
            == text(rejection.get("agent_id"))
            or rejection.get("attestation_level") != "HARNESS_REPORTED"
        ):
            errors.append(
                f"persisted.rejection_harness_subagent_invalid:{rejection_id}"
            )
        if role == "CHALLENGER" and rejection_provenance not in {
            "HARNESS_SUBAGENT", "HOST_PROCESS", "CONTROLLED_FIXTURE"
        }:
            errors.append(f"persisted.rejection_isolation_invalid:{rejection_id}")
    if counted_loops != completed:
        errors.append("persisted.completed_loop_count_drift")

    raw_actions = ledger.get("action_intents")
    if not isinstance(raw_actions, list):
        errors.append("persisted.action_intents_must_be_list")
    actions = raw_actions if isinstance(raw_actions, list) else []
    if len(actions) != len(lead_calls):
        errors.append("persisted.lead_action_call_count_mismatch")
    action_ids = set()
    expected_base = snapshot_hash(empty_snapshot(task))
    prior_frontier_counts = (0, 0, 0)
    for index, action in enumerate(actions, start=1):
        if not _validate_exact_record(
            action, ACTION_RECORD_FIELDS, errors, f"action_intent[{index}]"
        ):
            continue
        action_id = text(action.get("action_id"))
        if (
            not ID_RE.fullmatch(action_id)
            or action_id in action_ids
            or action.get("status") != "COMPLETED"
        ):
            errors.append(f"persisted.action_identity_or_status_invalid:{action_id}")
        action_ids.add(action_id)
        try:
            canonical_intent = normalize_action_intent(
                action, action_type=action.get("action_type")
            )
            for field, value in canonical_intent.items():
                if field != "status" and action.get(field) != value:
                    errors.append(
                        f"persisted.action_not_canonical:{action_id}:{field}"
                    )
        except ResearchContractError as exc:
            errors.extend(f"persisted.{value}" for value in exc.errors)
        action_evidence = _unique_text(action.get("evidence_ids", []))
        action_checks = _unique_text(action.get("source_check_ids", []))
        if action_evidence != action.get("evidence_ids"):
            errors.append(f"persisted.action_evidence_not_canonical:{action_id}")
        if action_checks != action.get("source_check_ids"):
            errors.append(f"persisted.action_source_checks_not_canonical:{action_id}")
        if not set(action_evidence).issubset(evidence_ids):
            errors.append(f"persisted.action_evidence_missing:{action_id}")
        if not set(action_checks).issubset(source_check_ids):
            errors.append(f"persisted.action_source_check_missing:{action_id}")
        if action.get("base_snapshot_sha256") != expected_base:
            errors.append(f"persisted.action_base_chain_drift:{action_id}")
        if action.get("snapshot_version") != index:
            errors.append(f"persisted.action_snapshot_version_drift:{action_id}")
        if not SHA256_RE.fullmatch(text(action.get("snapshot_sha256"))):
            errors.append(f"persisted.action_snapshot_hash_invalid:{action_id}")
        if not SHA256_RE.fullmatch(text(action.get("submission_payload_sha256"))):
            errors.append(f"persisted.action_payload_hash_invalid:{action_id}")
        frontier = action.get("snapshot_frontier")
        try:
            frontier_run = run_at_snapshot_frontier(run, frontier)
        except ResearchContractError as exc:
            errors.extend(
                f"persisted.{value}:{action_id}" for value in exc.errors
            )
        else:
            counts = (
                frontier["evidence_count"], frontier["source_check_count"],
                frontier["challenge_count"],
            )
            if any(current < prior for current, prior in zip(
                counts, prior_frontier_counts
            )):
                errors.append(f"persisted.action_frontier_not_monotonic:{action_id}")
            prior_frontier_counts = counts
        expected_base = text(action.get("snapshot_sha256"))

    for action, call in zip(actions, lead_calls):
        if not isinstance(action, dict):
            continue
        action_id = text(action.get("action_id"))
        if call.get("action_id") != action_id:
            errors.append(f"persisted.action_call_id_mismatch:{action_id or 'EMPTY'}")
        expected_modes = (
            {"LEAD_RESOLUTION"}
            if action.get("action_type") == "RESOLUTION"
            else {"LEAD_RESEARCH", "LEAD_SYNTHESIS"}
        )
        if call.get("mode") not in expected_modes:
            errors.append(f"persisted.action_call_mode_mismatch:{action_id}")
        if action.get("submission_payload_sha256") != call.get("payload_sha256"):
            errors.append(f"persisted.action_call_payload_drift:{action_id}")

    raw_challenges = ledger.get("challenge_packets")
    if not isinstance(raw_challenges, list):
        errors.append("persisted.challenge_packets_must_be_list")
    challenge_packets = raw_challenges if isinstance(raw_challenges, list) else []
    if len(challenge_packets) != len(challenger_calls):
        errors.append("persisted.challenge_packet_call_count_mismatch")
    challenge_ids = set()
    for index, packet in enumerate(challenge_packets, start=1):
        if not _validate_exact_record(
            packet, CHALLENGE_RECORD_FIELDS, errors, f"challenge_packet[{index}]"
        ):
            continue
        challenge_id = text(packet.get("challenge_id"))
        targets = _unique_text(packet.get("target_claim_ids", []), limit=12)
        packet_evidence = _unique_text(packet.get("evidence_ids", []), limit=80)
        packet_checks = _unique_text(packet.get("source_check_ids", []), limit=80)
        if (
            not ID_RE.fullmatch(challenge_id)
            or challenge_id in challenge_ids
            or not targets
            or targets != packet.get("target_claim_ids")
        ):
            errors.append(f"persisted.challenge_identity_invalid:{challenge_id}")
        challenge_ids.add(challenge_id)
        if packet_evidence != packet.get("evidence_ids") or not set(
            packet_evidence
        ).issubset(evidence_ids):
            errors.append(f"persisted.challenge_evidence_invalid:{challenge_id}")
        if packet_checks != packet.get("source_check_ids") or not set(
            packet_checks
        ).issubset(source_check_ids):
            errors.append(f"persisted.challenge_source_checks_invalid:{challenge_id}")
        if not SHA256_RE.fullmatch(text(packet.get("submission_payload_sha256"))):
            errors.append(f"persisted.challenge_payload_hash_invalid:{challenge_id}")
        if not text(packet.get("strongest_countercase")):
            errors.append(f"persisted.challenge_countercase_required:{challenge_id}")
        attacks = packet.get("attacks")
        if not isinstance(attacks, list) or not attacks:
            errors.append(f"persisted.challenge_attacks_required:{challenge_id}")
            attacks = []
        for attack_index, attack in enumerate(attacks, start=1):
            if not _validate_exact_record(
                attack, CHALLENGE_ATTACK_FIELDS, errors,
                f"challenge_packet[{index}].attack[{attack_index}]",
            ):
                continue
            attack_evidence = _unique_text(attack.get("evidence_ids", []), limit=80)
            if (
                text(attack.get("target_claim_id")) not in targets
                or not text(attack.get("argument"))
                or attack.get("severity") != "LOAD_BEARING"
                or attack_evidence != attack.get("evidence_ids")
                or not set(attack_evidence).issubset(evidence_ids)
            ):
                errors.append(
                    f"persisted.challenge_attack_invalid:{challenge_id}:{attack_index}"
                )
    for packet, call in zip(challenge_packets, challenger_calls):
        if not isinstance(packet, dict):
            continue
        challenge_id = text(packet.get("challenge_id"))
        if call.get("challenge_id") != challenge_id:
            errors.append(f"persisted.challenge_call_id_mismatch:{challenge_id}")
        if packet.get("submission_payload_sha256") != call.get("payload_sha256"):
            errors.append(f"persisted.challenge_call_payload_drift:{challenge_id}")

    raw_failures = ledger.get("failures")
    if not isinstance(raw_failures, list):
        errors.append("persisted.failures_must_be_list")
    failures = raw_failures if isinstance(raw_failures, list) else []
    for index, failure in enumerate(failures, start=1):
        if not _validate_exact_record(
            failure, FAILURE_RECORD_FIELDS, errors, f"failure[{index}]"
        ):
            continue
        failure_role = text(failure.get("role")).upper()
        failure_mode = text(failure.get("call_mode")).upper()
        failure_receipt_id = text(failure.get("receipt_id"))
        if failure_receipt_id:
            if failure_receipt_id in receipt_ids:
                errors.append(
                    f"persisted.failure_receipt_id_duplicate:{failure_receipt_id}"
                )
            receipt_ids.add(failure_receipt_id)
        expected_role = "CHALLENGER" if failure_mode == "CHALLENGER" else "LEAD"
        if (
            failure_role != failure.get("role")
            or failure_mode != failure.get("call_mode")
            or failure_mode not in ALL_CALL_MODES
            or failure_role != expected_role
            or not text(failure.get("reason"))
            or not SHA256_RE.fullmatch(text(failure.get("prompt_sha256")))
            or not SHA256_RE.fullmatch(text(failure.get("base_snapshot_sha256")))
        ):
            errors.append(f"persisted.failure_invalid:{index}")
    if ledger.get("stopped_reason") == "RUNTIME_FAILURE":
        if (
            not failures
            or not isinstance(failures[-1], dict)
            or failures[-1].get("call_mode") != retry_call
            or failures[-1].get("base_snapshot_sha256") != snapshot_hash(snapshot)
        ):
            errors.append("persisted.runtime_failure_record_drift")

    pending_request = ledger.get("pending_challenge_request")
    if pending_request is not None:
        if _validate_exact_record(
            pending_request, PENDING_CHALLENGE_FIELDS, errors,
            "pending_challenge_request",
        ):
            pending_id = text(pending_request.get("challenge_id"))
            pending_targets = _unique_text(
                pending_request.get("target_claim_ids", []), limit=12
            )
            if (
                not ID_RE.fullmatch(pending_id)
                or pending_id in challenge_ids
                or not pending_targets
                or pending_targets != pending_request.get("target_claim_ids")
                or not set(pending_targets).issubset(_claim_ids(snapshot))
                or not text(pending_request.get("question"))
                or not text(pending_request.get("why_load_bearing"))
                or pending_request.get("snapshot_sha256") != snapshot_hash(snapshot)
            ):
                errors.append("persisted.pending_challenge_request_invalid")
        if not (
            next_call == "CHALLENGER"
            or (next_call == "REPORT" and retry_call == "CHALLENGER")
        ):
            errors.append("persisted.pending_challenge_request_state_invalid")
    elif next_call == "CHALLENGER" or retry_call == "CHALLENGER":
        errors.append("persisted.challenger_requires_pending_request")

    pending = ledger.get("pending_dispatch")
    if pending is not None:
        if _validate_exact_record(
            pending, PENDING_DISPATCH_FIELDS, errors, "pending_dispatch"
        ):
            expected_role = "CHALLENGER" if next_call == "CHALLENGER" else "LEAD"
            if pending.get("call_mode") != next_call:
                errors.append("persisted.pending_dispatch_mode_drift")
            if pending.get("role") != expected_role:
                errors.append("persisted.pending_dispatch_role_drift")
            if pending.get("base_snapshot_sha256") != snapshot_hash(snapshot):
                errors.append("persisted.pending_dispatch_snapshot_drift")
            if not SHA256_RE.fullmatch(text(pending.get("prompt_sha256"))):
                errors.append("persisted.pending_dispatch_prompt_hash_invalid")
    if next_call == "REPORT" and pending is not None:
        errors.append("persisted.report_cannot_have_pending_dispatch")
    stopped_reason = text(ledger.get("stopped_reason"))
    if next_call == "REPORT" and not stopped_reason:
        errors.append("persisted.report_requires_stopped_reason")
    if next_call != "REPORT" and stopped_reason:
        errors.append("persisted.active_run_cannot_have_stopped_reason")
    try:
        snapshot_version = int(snapshot.get("version", 0) or 0)
    except (TypeError, ValueError):
        snapshot_version = -1
    if require_written_snapshot and snapshot_version <= 0:
        errors.append("persisted.snapshot_not_written")
    if snapshot.get("as_of") != task.get("as_of"):
        errors.append("persisted.as_of_mismatch")
    if snapshot_version == 0:
        if snapshot != empty_snapshot(task):
            errors.append("persisted.empty_snapshot_drift")
        if actions:
            errors.append("persisted.empty_snapshot_has_lead_actions")
    elif snapshot_version > 0:
        if snapshot_version != len(actions):
            errors.append("persisted.snapshot_version_action_count_drift")
        if not actions:
            errors.append("persisted.snapshot_without_lead_action")
        else:
            latest_action = actions[-1]
            if not isinstance(latest_action, dict):
                errors.append("persisted.snapshot_latest_action_invalid")
            else:
                if latest_action.get("snapshot_sha256") != snapshot_hash(snapshot):
                    errors.append("persisted.snapshot_not_bound_to_latest_lead_action")
                if latest_action.get("snapshot_version") != snapshot_version:
                    errors.append("persisted.snapshot_latest_version_drift")
                if latest_action.get("base_snapshot_sha256") != snapshot.get(
                    "base_snapshot_sha256"
                ):
                    errors.append("persisted.snapshot_latest_base_drift")
        try:
            canonical_snapshot = normalize_and_validate_snapshot(
                snapshot, run=run, mode="PERSISTED", persisted=True
            )
            if canonical_snapshot != snapshot:
                errors.append("persisted.snapshot_not_canonical")
            if actions and isinstance(actions[-1], dict):
                try:
                    committed_run = run_at_snapshot_frontier(
                        run, actions[-1].get("snapshot_frontier")
                    )
                except ResearchContractError as exc:
                    errors.extend(
                        f"persisted.{value}" for value in exc.errors
                    )
                else:
                    _validate_snapshot_obligations(
                        committed_run, snapshot,
                        snapshot.get("decision_status"), errors,
                    )
        except ResearchContractError as exc:
            errors.extend(f"persisted.{value}" for value in exc.errors)
    else:
        errors.append("persisted.snapshot_version_invalid")
    if errors:
        raise ResearchContractError(errors)
    return run


def authorize_more_loops(run, extra_loops):
    try:
        extra_loops = int(extra_loops)
    except (TypeError, ValueError):
        extra_loops = 0
    if extra_loops < 0:
        raise ResearchContractError(["authorization.extra_loops_nonnegative_required"])
    updated = deepcopy(run)
    ledger = updated["run_ledger"]
    if ledger.get("next_call") != "REPORT" or ledger.get("pending_dispatch"):
        raise ResearchContractError(["authorization.requires_stopped_report_state"])
    if extra_loops == 0 and (
        ledger.get("stopped_reason") != "RUNTIME_FAILURE"
        or ledger.get("retry_call") not in {
            "LEAD_RESEARCH", "LEAD_SYNTHESIS", "CHALLENGER", "LEAD_RESOLUTION"
        }
        or (
            ledger.get("retry_call") in {"LEAD_RESEARCH", "CHALLENGER"}
            and remaining_budget(ledger) <= 0
        )
    ):
        raise ResearchContractError([
            "authorization.zero_only_resumes_failed_remaining_call"
        ])
    new_budget = int(ledger.get("authorized_research_loops", 0)) + extra_loops
    if new_budget > 10:
        raise ResearchContractError(["authorization.total_budget_exceeds_10"])
    ledger["authorized_research_loops"] = new_budget
    if ledger.get("stopped_reason") == "RUNTIME_FAILURE":
        ledger["next_call"] = ledger.pop("retry_call")
    else:
        ledger["next_call"] = "LEAD_RESEARCH"
        ledger.pop("retry_call", None)
    if ledger.get("next_call") != "REPORT":
        ledger["stopped_reason"] = ""
    return updated
