#!/usr/bin/env python3
"""Post-process agent JSON to align landscape_findings evidence with crux_evidence.

The landscape engine requires evidence citations in landscape_findings to be
byte-for-byte identical to the same agent's crux_evidence / crux_attacks entries.
General-purpose sub-agents often paraphrase claims, causing citation-identity
mismatch.  This script fuzzy-matches landscape evidence back to the parent
evidence array by URL (which is the most stable field) and replaces the
landscape copy with the verbatim parent citation.

Usage:
  python3 scripts/align_landscape_evidence.py detective < agent_output.json
  python3 scripts/align_landscape_evidence.py inquisitor < agent_output.json
"""

import json
import sys
from urllib.parse import urlparse


def _normalize_url(url):
    """Strip query/fragment for fuzzy matching."""
    if not isinstance(url, str) or not url:
        return ""
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}{p.path}".rstrip("/").lower()


def _match_url(target_url, pool):
    """Return the first pool citation whose normalized URL matches target_url."""
    target = _normalize_url(target_url)
    if not target:
        return None
    for cit in pool:
        if _normalize_url(cit.get("url", "")) == target:
            return cit
    return None


def align(payload, role):
    role = str(role).lower()
    if role == "detective":
        groups_key = "crux_evidence"
        items_key = "evidence"
    elif role == "inquisitor":
        groups_key = "crux_attacks"
        items_key = "attacks"
    else:
        raise ValueError(f"Unknown role: {role}")

    if not isinstance(payload, dict):
        return payload

    lf = payload.get("landscape_findings")
    if not isinstance(lf, list) or not lf:
        return payload  # Nothing to align

    # Build evidence pool: {crux_id: [citation, ...]}
    pool = {}
    for group in payload.get(groups_key, []) if isinstance(payload.get(groups_key), list) else []:
        if not isinstance(group, dict):
            continue
        cid = group.get("crux_id", "")
        pool[cid] = list(group.get(items_key, []) if isinstance(group.get(items_key), list) else [])

    aligned_count = 0
    for finding in lf:
        if not isinstance(finding, dict):
            continue
        linked = finding.get("linked_crux_id", "")
        evidence_pool = pool.get(linked, [])
        if not evidence_pool:
            continue

        finding_evidence = finding.get("evidence")
        if not isinstance(finding_evidence, list) or not finding_evidence:
            continue

        new_evidence = []
        seen = set()
        for cit in finding_evidence:
            matched = _match_url(cit.get("url", ""), evidence_pool)
            if matched is not None:
                key = (matched.get("url", ""), matched.get("claim", "")[:80])
                if key not in seen:
                    seen.add(key)
                    new_evidence.append(matched)
                    aligned_count += 1
        finding["evidence"] = new_evidence

    payload["_aligned"] = aligned_count
    return payload


def main():
    if len(sys.argv) < 2:
        print("Usage: align_landscape_evidence.py detective|inquisitor", file=sys.stderr)
        sys.exit(1)
    role = sys.argv[1]
    raw = sys.stdin.read().strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON input: {e}", file=sys.stderr)
        sys.exit(1)
    result = align(payload, role)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
