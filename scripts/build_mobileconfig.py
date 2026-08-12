#!/usr/bin/env python3
from __future__ import annotations

import plistlib
import re
import uuid
from pathlib import Path

SOURCE = Path("reddit-nsfw-easylist.txt")
OUTPUT = Path("reddit-nsfw-blocklist.mobileconfig")
MAX_URLS_PER_PAYLOAD = 500

RULE_RE = re.compile(r"^\|\|reddit\.com/r/([A-Za-z0-9_]+)\^\s*$")


def extract_subreddits(text: str) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    for raw_line in text.splitlines():
        match = RULE_RE.match(raw_line.strip())
        if not match:
            continue
        name = match.group(1)
        key = name.lower()
        if key not in seen:
            seen.add(key)
            names.append(name)

    if not names:
        raise SystemExit("No subreddit rules were found in reddit-nsfw-easylist.txt")

    return names


def make_payload(urls: list[str], index: int) -> dict:
    return {
        "PayloadType": "com.apple.webcontent-filter",
        "PayloadVersion": 1,
        "PayloadIdentifier": f"com.hall1816.reddit-nsfw-blocklist.filter.{index}",
        "PayloadUUID": str(uuid.uuid4()).upper(),
        "PayloadDisplayName": f"Reddit NSFW Blocklist {index}",
        "FilterType": "BuiltIn",
        "AutoFilterEnabled": False,
        "DenyListURLs": urls,
    }


def main() -> None:
    subreddits = extract_subreddits(SOURCE.read_text(encoding="utf-8"))

    # Apple's built-in web-content filter performs string-based URL matching.
    # A trailing slash also matches the same path without the slash and all
    # descendants, which blocks the subreddit without catching similarly
    # prefixed subreddit names.
    urls = [f"reddit.com/r/{name}/" for name in subreddits]

    chunks = [
        urls[i : i + MAX_URLS_PER_PAYLOAD]
        for i in range(0, len(urls), MAX_URLS_PER_PAYLOAD)
    ]

    profile = {
        "PayloadType": "Configuration",
        "PayloadVersion": 1,
        "PayloadIdentifier": "com.hall1816.reddit-nsfw-blocklist",
        "PayloadUUID": str(uuid.uuid4()).upper(),
        "PayloadDisplayName": "Reddit NSFW Blocklist",
        "PayloadDescription": (
            f"Blocks {len(urls)} Reddit subreddit URL paths using iOS built-in "
            "web content filtering."
        ),
        "PayloadOrganization": "hall1816",
        "PayloadRemovalDisallowed": False,
        "PayloadContent": [
            make_payload(chunk, i + 1) for i, chunk in enumerate(chunks)
        ],
    }

    with OUTPUT.open("wb") as f:
        plistlib.dump(profile, f, fmt=plistlib.FMT_XML, sort_keys=False)

    print(
        f"Wrote {OUTPUT} with {len(urls)} URL rules "
        f"across {len(chunks)} payloads."
    )


if __name__ == "__main__":
    main()
