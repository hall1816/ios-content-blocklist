#!/usr/bin/env python3
"""Build the AdBlock EasyList from the three reviewed public source lists."""

from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from pathlib import Path


EASYLIST_SOURCE = "https://raw.githubusercontent.com/dlln147/RandomNSFW/refs/heads/main/RandomNSFW"
POSTPONE_SOURCE = "https://api.postpone.app/api/reddit/nsfw-subreddits/?limit=5000"
KINKY_SOURCE = "https://thekinkytourist.com/subreddits/"
KINKY_PART_COUNT = 26
OUTPUT = Path("reddit-nsfw-easylist.txt")
NAME = re.compile(r"^[A-Za-z0-9_]+$")
KINKY_RULE = re.compile(r"https?://(?:www\.)?reddit\.com/r/([A-Za-z0-9_]+)(?=[/?#\"'<]|$)", re.IGNORECASE)


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "ios-content-blocklist/0.1"})
    with urllib.request.urlopen(request, timeout=90) as response:
        data = response.read(16 * 1024 * 1024 + 1)
    if len(data) > 16 * 1024 * 1024:
        raise ValueError(f"source exceeds the 16 MiB safety limit: {url}")
    return data


def deduplicate(names: list[str]) -> list[str]:
    unique: dict[str, str] = {}
    for name in names:
        unique.setdefault(name.lower(), name)
    return [unique[key] for key in sorted(unique, key=str.lower)]


def extract_plain_names(data: bytes) -> tuple[list[str], int]:
    names: list[str] = []
    rejected = 0
    for line in data.decode("utf-8", errors="replace").splitlines():
        candidate = line.strip()
        if not candidate or candidate.startswith("#"):
            continue
        if not NAME.fullmatch(candidate):
            rejected += 1
            continue
        names.append(candidate)
    return deduplicate(names), rejected


def extract_postpone_names(data: bytes) -> tuple[list[str], int]:
    rows = json.loads(data.decode("utf-8")).get("result")
    if not isinstance(rows, list):
        raise ValueError("Postpone response has no result list")
    names: list[str] = []
    rejected = 0
    for row in rows:
        candidate = row.get("name") if isinstance(row, dict) else None
        if not isinstance(candidate, str) or not NAME.fullmatch(candidate):
            rejected += 1
            continue
        names.append(candidate)
    return deduplicate(names), rejected


def extract_kinky_names(data: bytes) -> list[str]:
    return deduplicate([match.group(1) for match in KINKY_RULE.finditer(data.decode("utf-8", errors="replace"))])


def kinky_page_url(part: int) -> str:
    return KINKY_SOURCE if part == 1 else f"https://thekinkytourist.com/subreddits-part-{part}/"


def main() -> None:
    all_names: list[str] = []
    source_rows: list[tuple[str, str, int, int, str]] = []

    easylist_data = fetch(EASYLIST_SOURCE)
    easylist_names, easylist_rejected = extract_plain_names(easylist_data)
    all_names.extend(easylist_names)
    source_rows.append(("RandomNSFW", EASYLIST_SOURCE, len(easylist_names), easylist_rejected, hashlib.sha256(easylist_data).hexdigest()))

    postpone_data = fetch(POSTPONE_SOURCE)
    postpone_names, postpone_rejected = extract_postpone_names(postpone_data)
    all_names.extend(postpone_names)
    source_rows.append(("Postpone top 5,000", POSTPONE_SOURCE, len(postpone_names), postpone_rejected, hashlib.sha256(postpone_data).hexdigest()))

    kinky_pages: list[bytes] = []
    kinky_names: list[str] = []
    for part in range(1, KINKY_PART_COUNT + 1):
        data = fetch(kinky_page_url(part))
        names = extract_kinky_names(data)
        if not names:
            raise ValueError(f"Kinky Tourist part {part} contains no supported Reddit links")
        kinky_pages.append(data)
        kinky_names.extend(names)
    kinky_unique = deduplicate(kinky_names)
    all_names.extend(kinky_unique)
    kinky_digest = hashlib.sha256(b"\n--- source page boundary ---\n".join(kinky_pages)).hexdigest()
    source_rows.append(("Kinky Tourist 26-part list", KINKY_SOURCE, len(kinky_unique), 0, kinky_digest))

    names = deduplicate(all_names)
    lines = [
        "[Adblock Plus 2.0]",
        "! Title: Reddit NSFW Subreddit Blocklist",
        "! Description: Blocks reviewed Reddit community URL paths from three public source lists.",
        f"! Rules: {len(names)}",
    ]
    for label, url, accepted, rejected, digest in source_rows:
        lines.append(f"! Source: {label}; accepted: {accepted}; rejected: {rejected}; SHA-256: {digest}")
        lines.append(f"! URL: {url}")
    lines.append("")
    lines.extend(f"||reddit.com/r/{name}^" for name in names)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as output:
        output.write("\n".join(lines) + "\n")
    print(f"Wrote {OUTPUT} with {len(names)} EasyList rules")


if __name__ == "__main__":
    main()
