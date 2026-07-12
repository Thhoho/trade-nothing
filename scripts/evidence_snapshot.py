#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create reproducible, content-hashed evidence snapshots.

The network path blocks local/private destinations and validates redirects.
Tests use snapshot_from_bytes and never require live network access.
"""
import argparse
import datetime as dt
import hashlib
from html import unescape
from html.parser import HTMLParser
import io
import ipaddress
import json
from pathlib import Path
import re
import socket
import sys
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


MAX_BYTES = 2_000_000
MAX_TEXT_CHARS = 500_000
TIMEOUT_SECONDS = 20
USER_AGENT = "Trade-Nothing-Evidence-Snapshot/1.0"


def normalize_text(value):
    return " ".join(unescape(str(value or "")).split())


class _HTMLText(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "canvas"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.title_parts = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.SKIP:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        if tag in {"p", "br", "li", "tr", "h1", "h2", "h3", "h4", "section", "article"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.SKIP and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False
        if tag in {"p", "li", "tr", "h1", "h2", "h3", "h4", "section", "article"}:
            self.parts.append(" ")

    def handle_data(self, data):
        if self._skip_depth:
            return
        self.parts.append(data)
        if self._in_title:
            self.title_parts.append(data)

    @property
    def text(self):
        return normalize_text(" ".join(self.parts))

    @property
    def title(self):
        return normalize_text(" ".join(self.title_parts))


def _public_ip(address):
    ip = ipaddress.ip_address(address)
    return not any([
        ip.is_private,
        ip.is_loopback,
        ip.is_link_local,
        ip.is_multicast,
        ip.is_reserved,
        ip.is_unspecified,
    ])


def validate_public_url(url, resolve_dns=True):
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("only public http/https URLs are allowed")
    if parsed.username or parsed.password:
        raise ValueError("userinfo in evidence URL is forbidden")
    if parsed.port not in (None, 80, 443):
        raise ValueError("non-standard evidence URL port is forbidden")
    host = parsed.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        raise ValueError("local evidence URL is forbidden")
    try:
        if not _public_ip(host):
            raise ValueError("private or special-purpose evidence URL is forbidden")
        return url
    except ValueError as exc:
        if "private or special-purpose" in str(exc):
            raise
        # Not an IP literal; resolve below.
    if resolve_dns:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        addresses = {item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
        if not addresses or not all(_public_ip(address) for address in addresses):
            raise ValueError("evidence hostname resolves to a private or special-purpose address")
    return url


class _SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urljoin(req.full_url, newurl)
        validate_public_url(target, resolve_dns=True)
        return super().redirect_request(req, fp, code, msg, headers, target)


def _decode_text(body, content_type, charset="utf-8"):
    media_type = (content_type or "").split(";", 1)[0].strip().lower()
    if media_type in {"text/html", "application/xhtml+xml"}:
        parser = _HTMLText()
        parser.feed(body.decode(charset or "utf-8", errors="replace"))
        return parser.text, parser.title, "OK"
    if media_type.startswith("text/") or media_type in {
        "application/json", "application/xml", "application/rss+xml", "application/atom+xml"
    }:
        return normalize_text(body.decode(charset or "utf-8", errors="replace")), "", "OK"
    if media_type == "application/pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(body))
            text = normalize_text(" ".join(page.extract_text() or "" for page in reader.pages))
            return text, "", "OK" if text else "EMPTY_TEXT"
        except Exception:
            return "", "", "UNSUPPORTED_PDF_EXTRACTION"
    return "", "", "UNSUPPORTED_CONTENT_TYPE"


def snapshot_from_bytes(source_url, body, content_type="text/html; charset=utf-8",
                        retrieved_at=None, final_url=None, http_status=200):
    if not isinstance(body, (bytes, bytearray)):
        raise TypeError("body must be bytes")
    if len(body) > MAX_BYTES:
        raise ValueError(f"response exceeds {MAX_BYTES} bytes")
    source_url = str(source_url)
    final_url = str(final_url or source_url)
    charset_match = re.search(r"charset=([^;\s]+)", content_type or "", flags=re.I)
    charset = charset_match.group(1).strip("'\"") if charset_match else "utf-8"
    text, title, extraction_status = _decode_text(bytes(body), content_type, charset)
    text = text[:MAX_TEXT_CHARS]
    raw_sha = hashlib.sha256(bytes(body)).hexdigest()
    text_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    snapshot_id = "SS-" + hashlib.sha256(
        f"{source_url}|{final_url}|{text_sha}".encode("utf-8")
    ).hexdigest()[:12].upper()
    return {
        "snapshot_id": snapshot_id,
        "status": extraction_status,
        "source_url": source_url,
        "final_url": final_url,
        "retrieved_at": retrieved_at or dt.datetime.now(dt.timezone.utc).isoformat(),
        "http_status": int(http_status),
        "content_type": content_type,
        "title": title,
        "raw_sha256": raw_sha,
        "text_sha256": text_sha,
        "text_length": len(text),
        "text": text,
    }


def snapshot_url(url):
    validate_public_url(url, resolve_dns=True)
    opener = build_opener(_SafeRedirect())
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain,application/json,application/pdf"})
    with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError(f"response exceeds {MAX_BYTES} bytes")
        content_type = response.headers.get("Content-Type", "application/octet-stream")
        return snapshot_from_bytes(
            source_url=url,
            body=body,
            content_type=content_type,
            final_url=response.geturl(),
            http_status=getattr(response, "status", 200),
        )


def snapshot_file(path, source_url, content_type=None):
    validate_public_url(source_url, resolve_dns=False)
    path = Path(path)
    body = path.read_bytes()
    if content_type is None:
        suffix = path.suffix.lower()
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".htm": "text/html; charset=utf-8",
            ".txt": "text/plain; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".pdf": "application/pdf",
        }.get(suffix, "application/octet-stream")
    return snapshot_from_bytes(source_url, body, content_type=content_type)


def main():
    ap = argparse.ArgumentParser(description="Create content-hashed evidence snapshots")
    ap.add_argument("--url", action="append", default=[], help="public citation URL; repeatable")
    ap.add_argument("--input-file", default="", help="local captured page/PDF")
    ap.add_argument("--source-url", default="", help="original public URL for --input-file")
    ap.add_argument("--content-type", default="")
    ap.add_argument("--output", default="", help="optional JSON output path")
    args = ap.parse_args()
    snapshots, errors = [], []
    for url in args.url:
        try:
            snapshots.append(snapshot_url(url))
        except Exception as exc:
            errors.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
    if args.input_file:
        try:
            if not args.source_url:
                raise ValueError("--source-url is required with --input-file")
            snapshots.append(snapshot_file(args.input_file, args.source_url, args.content_type or None))
        except Exception as exc:
            errors.append({"path": args.input_file, "error": f"{type(exc).__name__}: {exc}"})
    rendered = json.dumps({"snapshots": snapshots, "errors": errors}, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 2 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
