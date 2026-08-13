#!/usr/bin/env python3
"""Pure DecisionSnapshot -> Markdown renderer for Trade Nothing.

The renderer formats already-decided semantics.  It must not rank candidates,
upgrade evidence, infer a conclusion, or manufacture stronger Challenger provenance.
"""
from __future__ import annotations

import research_core


def _text(value):
    return research_core.text(value)


def _refs(values):
    values = [str(item) for item in values if str(item)] if isinstance(values, list) else []
    return " ".join(f"[{item}]" for item in values) or "—"


def _boundary(item):
    return _text(item.get("boundary") or item.get("evidence_boundary") or "HYPOTHESIS")


def _table_cell(value):
    return _text(value).replace("|", "\\|").replace("\n", " ") or "—"


def _render_key_measures(snapshot, store):
    visible = set(snapshot.get("consumed_evidence_ids", []))
    measures = []
    seen = set()
    for item in store.get("items", []):
        if item.get("evidence_id") not in visible:
            continue
        for measure in item.get("measures", []):
            measure_id = measure.get("measure_id")
            if not measure_id or measure_id in seen:
                continue
            seen.add(measure_id)
            measures.append((item.get("evidence_id"), measure))
    lines = ["### 统一量化事实", ""]
    if not measures:
        return lines + ["- 当前判断未消费结构化量化事实。"]
    for evidence_id, measure in measures:
        lines.append(
            f"- **{research_core.format_measure(measure)}**｜"
            f"{_text(measure.get('definition'))} "
            f"(`{_text(measure.get('subject_id'))}` / `{_text(measure.get('metric'))}` / "
            f"`{_text(measure.get('period'))}` / "
            f"截至 `{_text(measure.get('as_of'))}`) [{evidence_id}]"
        )
    return lines


def _render_material(snapshot, store):
    evidence = research_core.evidence_index(store)
    lines = ["## 2. Current Reality 与重大变化", ""]
    changes = snapshot.get("material_changes", [])
    if changes:
        for item in changes:
            lines.append(
                f"- **{_text(item.get('title') or item.get('change_id') or '重大变化')}**："
                f"{_text(item.get('summary'))} {_refs(item.get('evidence_ids', []))} "
                f"`{_boundary(item)}`"
            )
            if _text(item.get("decision_effect")):
                lines.append(f"  - 对判断的改变：{_text(item.get('decision_effect'))}")
            anchors = [
                f"{_text(fact.get('fact_type'))}@{_text(fact.get('locator'))}"
                for evidence_id in item.get("evidence_ids", [])
                for fact in evidence.get(evidence_id, {}).get("document_facts", [])
            ]
            if anchors:
                lines.append(f"  - 宿主正文锚点：{'；'.join(anchors)}")
    else:
        lines.append("- 当前 Snapshot 未记录已核实重大变化。")
    lines.extend(["", "### 开放重大缺口", ""])
    gaps = snapshot.get("open_material_gaps", [])
    if gaps:
        for item in gaps:
            lines.append(
                f"- `{_text(item.get('gap_id'))}`：{_text(item.get('description'))} "
                f"{_refs(item.get('evidence_ids', []))}"
            )
    else:
        lines.append("- 无。")
    lines.extend(["", "### 已明确判定为不改写结论的重大标题证据", ""])
    dispositions = snapshot.get("non_material_evidence_dispositions", [])
    if dispositions:
        families = {}
        for item in dispositions:
            families.setdefault(item.get("event_family_id"), []).append(item)
        for family_id, items in families.items():
            first = items[0]
            evidence_ids = [item.get("evidence_id") for item in items]
            anchors = [
                f"{_text(fact.get('fact_type'))}@{_text(fact.get('locator'))}"
                for evidence_id in evidence_ids
                for fact in evidence.get(evidence_id, {}).get("document_facts", [])
            ]
            lines.append(
                f"- **{_text(family_id)}**｜`{_text(first.get('decision_dimension'))}`："
                f"正文锚点：{'；'.join(anchors) or '缺失'}；"
                f"处置理由：{_text(first.get('reason'))}；"
                f"反转条件：{_text(first.get('reversal_condition'))} "
                f"{_refs(evidence_ids)}"
            )
    else:
        lines.append("- 无。")
    return lines


def _render_agenda(snapshot):
    lines = ["## 3. 研究问题", ""]
    answers = snapshot.get("agenda_answers", [])
    if not answers:
        return lines + ["- 当前 Snapshot 未形成问题级答案。"]
    for item in answers:
        lines.extend([
            f"### {_text(item.get('question_id'))}｜{_text(item.get('question'))}",
            "",
            f"- 状态：`{_text(item.get('status'))}`",
            f"- 当前答案：{_text(item.get('answer'))} {_refs(item.get('evidence_ids', []))}",
            f"- 证据边界：`{_boundary(item)}`",
            f"- 自我反例：{_text(item.get('self_countercase')) or '—'}",
            f"- 缺失信息：{_text(item.get('missing_information')) or '—'}",
            f"- 下一测试：`{_text(item.get('next_test_availability') or 'UNKNOWN')}`",
            "",
        ])
    return lines


def _render_market(snapshot):
    lines = ["## 4. 产业价值转移与市场运行", "", "### 价值转移路径", ""]
    paths = snapshot.get("value_transfer_paths", [])
    if paths:
        for item in paths:
            lines.append(
                f"- **{_text(item.get('path_id'))}**：{_text(item.get('constraint_change'))}"
                f" → {_text(item.get('profit_pool_shift'))} → "
                f"{_text(item.get('economic_exposure'))}；市场载体="
                f"{_text(item.get('market_carrier'))} {_refs(item.get('evidence_ids', []))} "
                f"`{_boundary(item)}`"
            )
    else:
        lines.append("- 尚未形成有证据约束的价值转移路径。")
    lines.extend(["", "### 分时间视野", ""])
    horizons = snapshot.get("market_by_horizon", [])
    if horizons:
        lines.extend([
            "| 时间视野 | 当前状态 | 市场机制 | 确认/切换条件 | 证据 / 边界 |",
            "|---|---|---|---|---|",
        ])
        for item in horizons:
            lines.append(
                f"| {_table_cell(item.get('horizon'))} | {_table_cell(item.get('current_state'))} | "
                f"{_table_cell(item.get('mechanism'))} | {_table_cell(item.get('switch_condition'))} | "
                f"{_refs(item.get('evidence_ids', []))} `{_boundary(item)}` |"
            )
    else:
        lines.append("- 尚无分时间视野判断。")
    return lines


def _render_candidates(snapshot):
    lines = ["## 5. 市场载体与研究立场", "", "### 市场实际在交易什么", ""]
    carrier_groups = snapshot.get("market_carriers_by_horizon", [])
    if carrier_groups:
        for group in carrier_groups:
            lines.extend([
                f"#### {_text(group.get('horizon'))}", "",
                "| 证券 | 市场角色 | 为何被交易 | 最近替代 / 切换条件 | 市场证据 / 边界 |",
                "|---|---|---|---|---|",
            ])
            for item in group.get("carriers", []):
                security = " ".join(filter(None, [
                    _text(item.get("name")),
                    f"({_text(item.get('ticker'))}.{_text(item.get('exchange'))})"
                    if item.get("ticker") else "",
                ]))
                lines.append(
                    f"| {_table_cell(security)} | {_table_cell(item.get('market_role'))} | "
                    f"{_table_cell(item.get('why_traded'))} | "
                    f"{_table_cell(item.get('closest_alternative'))} / "
                    f"{_table_cell(item.get('switch_condition'))} | "
                    f"市场={_refs(item.get('market_evidence_ids', []))}；"
                    f"替代={_refs(item.get('alternative_evidence_ids', []))} `"
                    f"{_boundary(item)}` |"
                )
            lines.append("")
    else:
        lines.extend([
            "- 当前 Snapshot 未形成有市场证据绑定的具名载体；这不等于没有题材映射。",
            "",
        ])
    lines.extend([
        "### 是否形成条件性研究标的", "",
        "- `WATCH` 与 `EXPLORE` 只是观察/待验证状态，不构成推荐；只有满足完整证据拓扑的 `CONDITIONAL_PRIORITY` 才是条件性研究优先级，仍不等于交易指令。",
        "",
    ])
    groups = snapshot.get("candidates_by_horizon", [])
    if not groups:
        return lines + ["- 当前没有通过经济暴露与市场状态双重约束的条件性标的。"]
    for group in groups:
        lines.extend([
            f"### {_text(group.get('horizon'))}",
            "",
            "| 立场 | 证券 | 价值路径 / 经济暴露 / 市场角色 | 为何现在 / 最近替代 | 触发 / 切换 / 失效 | 价格与拥挤边界 | 产业证据 / 市场证据 / 边界 |",
            "|---|---|---|---|---|---|---|",
        ])
        candidates = group.get("candidates", [])
        if not candidates:
            lines.append("| `NO_SETUP` | — | — | — | — | — | — |")
        for item in candidates:
            security = " ".join(filter(None, [
                _text(item.get("name")),
                f"({_text(item.get('ticker'))}.{_text(item.get('exchange'))})"
                if item.get("ticker") else "",
            ]))
            lines.append(
                f"| `{_table_cell(item.get('stance'))}` | {_table_cell(security)} | "
                f"{_table_cell(', '.join(item.get('value_path_ids', [])))} / "
                f"{_table_cell(item.get('economic_exposure'))} / {_table_cell(item.get('market_role'))} | "
                f"{_table_cell(item.get('why_now'))} / {_table_cell(item.get('closest_alternative'))} | "
                f"{_table_cell(item.get('trigger'))} / {_table_cell(item.get('switch_condition'))} / "
                f"{_table_cell(item.get('invalidation'))} | "
                f"{_table_cell(item.get('price_crowding_boundary'))} | "
                f"产业={_refs(item.get('exposure_evidence_ids', []))} / "
                f"市场={_refs(item.get('market_evidence_ids', []))} / "
                f"替代={_refs(item.get('alternative_evidence_ids', []))} / `{_boundary(item)}` |"
            )
        lines.append("")
    return lines


def _render_challenges(snapshot):
    lines = ["## 6. 反例与 Challenger 质证", "", "### Lead 自我反例", ""]
    countercases = snapshot.get("self_countercases", [])
    if countercases:
        for item in countercases:
            lines.append(
                f"- 针对 `{_text(item.get('target_claim_id'))}`："
                f"{_text(item.get('argument'))} {_refs(item.get('evidence_ids', []))}"
            )
    else:
        lines.append("- 无已记录自我反例。")
    lines.extend(["", "### Challenger 质证与 Lead 处理", ""])
    challenges = snapshot.get("challenge_resolutions", [])
    if challenges:
        for item in challenges:
            lines.extend([
                f"- **{_text(item.get('challenge_id'))}**｜处理结果 `"
                f"{_text(item.get('resolution'))}`｜目标 "
                f"{', '.join(item.get('target_claim_ids', []))}",
                f"  - 挑战：{_text(item.get('summary'))} {_refs(item.get('evidence_ids', []))}",
                f"  - Lead 处理：{_text(item.get('lead_response'))}",
            ])
    else:
        lines.append("- 本次没有带执行来源的 Challenger 产物；不得把 Lead 自我反例冒充为 Challenger 质证。")
    return lines


def _render_next(snapshot):
    lines = ["## 7. 未决问题与最低成本下一验证", ""]
    unresolved = snapshot.get("unresolved_questions", [])
    if unresolved:
        for item in unresolved:
            lines.append(
                f"- **{_text(item.get('question_id') or item.get('gap_id'))}**："
                f"{_text(item.get('question') or item.get('description'))} "
                f"{_refs(item.get('evidence_ids', []))}"
            )
    else:
        lines.append("- 无额外未决问题。")
    lines.extend(["", "### 下一验证", ""])
    validations = snapshot.get("lowest_cost_next_validation", [])
    if validations:
        for item in validations:
            lines.append(
                f"- `{_text(item.get('availability') or 'UNKNOWN')}` "
                f"{_text(item.get('action'))}；预期改变："
                f"{_text(item.get('expected_decision_delta'))}"
            )
    else:
        lines.append("- 当前 Snapshot 未建议继续消耗研究预算。")
    return lines


def _render_evidence(
    store, *, compact=False, evidence_ids=None, event_families=None
):
    lines = ["## 8. Evidence Ledger", ""]
    allowed = set(evidence_ids or []) if evidence_ids is not None else None
    items = [
        item for item in store.get("items", [])
        if allowed is None or item.get("evidence_id") in allowed
    ]
    if not items:
        return lines + ["- 无可引用证据。"]
    event_families = event_families or {}
    if compact and event_families:
        grouped = {}
        ungrouped = []
        for item in items:
            family_id = event_families.get(item.get("evidence_id"))
            if family_id:
                grouped.setdefault(family_id, []).append(item)
            else:
                ungrouped.append(item)
        for family_id, family_items in grouped.items():
            links = "；".join(
                f"[{item.get('evidence_id')}]({item.get('url')})：{_text(item.get('claim'))}"
                for item in family_items
            )
            lines.append(
                f"- **{family_id}**｜重大事件文档组 "
                f"({len(family_items)} 份)：{links}"
            )
        items = ungrouped
    for item in items:
        securities = (
            f"；证券={','.join(item.get('security_ids', []))}"
            if item.get("security_ids") else ""
        )
        lines.append(
            f"- **{item.get('evidence_id')}**｜`{item.get('boundary')}`｜"
            f"{item.get('claim')}{securities} — "
            f"[{item.get('source')}（{item.get('date')}）]({item.get('url')})"
        )
        if compact:
            continue
        for measure in item.get("measures", []):
            lines.append(
                f"  - `{measure.get('measure_id')}` {_text(measure.get('definition'))}："
                f"**{research_core.format_measure(measure)}**；"
                f"主体：`{_text(measure.get('subject_id'))}`；口径："
                f"{_text(research_core.MEASURE_BASES.get(measure.get('basis')))}；"
                f"截至 `{_text(measure.get('as_of'))}` / `{_text(measure.get('period'))}`"
            )
        for fact in item.get("document_facts", []):
            lines.append(
                f"  - `{fact.get('fact_id')}` 宿主正文摘录｜"
                f"`{_text(fact.get('event_type'))}` / `{_text(fact.get('fact_type'))}` / "
                f"`{_text(fact.get('locator'))}`：{_text(fact.get('excerpt'))}；"
                f"文档 SHA-256 `{_text(fact.get('document_sha256'))}`"
            )
    return lines


def render(run, *, view="audit"):
    research_core.validate_persisted_run(run)
    if view not in {"user", "audit"}:
        raise ValueError("report_view_invalid")
    task = run["task_spec"]
    snapshot = run["decision_snapshot"]
    ledger = run["run_ledger"]
    truth = research_core.delivery_state(run)
    execution_state = (
        "RUNTIME_FAILURE"
        if ledger.get("stopped_reason") == "RUNTIME_FAILURE"
        else "COMPLETE_AFTER_EXPLICIT_RETRY"
        if ledger.get("failures")
        else "COMPLETE_AFTER_PACKET_REPAIR"
        if ledger.get("rejections")
        else "COMPLETE"
    )
    lines = [
        f"# {_text(task.get('question'))}",
        "",
        f"> 截止日：`{task.get('as_of')}`｜DecisionSnapshot `v{snapshot.get('version')}`｜"
        f"交付状态 `{snapshot.get('decision_status')}`｜执行状态 `"
        f"{execution_state}`",
        "",
        "## 1. 核心判断与边界",
        "",
        _text(snapshot.get("core_judgment", {}).get("summary")),
        "",
        f"- 证据边界：`{_boundary(snapshot.get('core_judgment', {}))}` "
        f"{_refs(snapshot.get('core_judgment', {}).get('evidence_ids', []))}",
        f"- 明确边界：{_text(snapshot.get('boundary'))}",
        "",
    ]
    lines.extend(_render_key_measures(snapshot, run["evidence_store"]))
    lines.extend([""] + _render_material(snapshot, run["evidence_store"]))
    lines.extend([""] + _render_agenda(snapshot))
    lines.extend([""] + _render_market(snapshot))
    lines.extend([""] + _render_candidates(snapshot))
    lines.extend([""] + _render_challenges(snapshot))
    lines.extend([""] + _render_next(snapshot))
    if view == "user":
        event_families = {
            item.get("evidence_id"): item.get("event_family_id")
            for item in snapshot.get("non_material_evidence_dispositions", [])
        }
        lines.extend([""] + _render_evidence(
            run["evidence_store"], compact=True,
            evidence_ids=snapshot.get("consumed_evidence_ids", []),
            event_families=event_families,
        ))
        lines.extend([
            "", "## 9. 执行边界", "",
            f"- Lead 实际回执：`{', '.join(truth['achieved_execution']['lead_receipts'])}`",
            f"- Challenger 实际回执：`{', '.join(truth['achieved_execution']['challenger_receipts'])}`",
            f"- 执行状态：`{execution_state}`",
        ])
        if truth["achieved_execution"]["reported_subagent_challenge_count"]:
            lines.append(
                "- `HARNESS_REPORTED` 只记录宿主报告的子智能体身份与内容谱系，"
                "不是上下文独立性的应用侧强证明。"
            )
        if truth["achieved_execution"]["reported_process_challenge_count"]:
            lines.append(
                "- `PROCESS_REPORTED` 只记录调用方观察到的外部进程字段与内容谱系，"
                "不是不可伪造的宿主进程证明。"
            )
        for item in ledger.get("failures", []):
            lines.append(
                f"- 运行失败 `{_text(item.get('call_mode') or item.get('role'))}`："
                f"{_text(item.get('reason'))}；未自动重试。"
            )
        lines.extend(["", "本报告不构成订单、仓位、目标收益或自动执行授权。"])
        return "\n".join(lines).rstrip() + "\n"
    lines.extend([""] + _render_evidence(run["evidence_store"]))
    lines.extend([
        "",
        "## 9. 执行真实性与非目标",
        "",
        f"- 请求的编排模式：`{_text(truth.get('requested_execution_mode'))}`",
        f"- Lead 实际回执：`{', '.join(truth['achieved_execution']['lead_receipts'])}`",
        f"- Challenger 实际回执：`{', '.join(truth['achieved_execution']['challenger_receipts'])}`",
        f"- 执行状态：`{execution_state}`",
        f"- 研究循环：{ledger.get('completed_research_loops', 0)} / "
        f"{ledger.get('authorized_research_loops', 0)}",
        f"- 模型尝试：{len(ledger.get('calls', [])) + len(ledger.get('rejections', [])) + len(ledger.get('failures', []))} 次；"
        f"接受 {len(ledger.get('calls', []))} 次",
        f"- 停止原因：`{_text(ledger.get('stopped_reason')) or 'NOT_RECORDED'}`",
        f"- 宿主报告的 Codex 子智能体 Challenger："
        f"{truth['achieved_execution']['reported_subagent_challenge_count']} 次（非独立性强证明）",
        f"- 调用方报告的外部进程 Challenger："
        f"{truth['achieved_execution']['reported_process_challenge_count']} 次（非独立性强证明）",
        f"- 受控 fixture Challenger："
        f"{truth['achieved_execution']['controlled_fixture_challenge_count']} 次（仅测试）",
        f"- 被拒绝且未消费轮次的模型产物：{len(ledger.get('rejections', []))} 次",
        f"- 非目标：{', '.join(task.get('non_goals', []))}",
    ])
    failures = ledger.get("failures", [])
    rejections = ledger.get("rejections", [])
    if rejections:
        lines.extend(["", "### 合约拒绝历史", ""])
        for item in rejections:
            lines.append(
                f"- `{_text(item.get('call_mode'))}`："
                f"{'; '.join(item.get('errors', []))}；收据 "
                f"`{_text(item.get('rejection_id'))}`。该产物未进入 Snapshot、证据或轮次。"
            )
    if failures:
        lines.extend(["", "### 运行失败", ""])
        for item in failures:
            lines.append(
                f"- `{_text(item.get('call_mode') or item.get('role'))}`："
                f"{_text(item.get('reason'))}；收据 `{_text(item.get('receipt_id')) or 'NONE'}`"
            )
        if ledger.get("retry_call"):
            lines.append(
                f"- 未自动重试；可在用户明确授权后恢复 `{ledger.get('retry_call')}`。"
            )
    lines.extend(["", "本报告不构成订单、仓位、目标收益或自动执行授权。"])
    return "\n".join(lines).rstrip() + "\n"
