#!/usr/bin/env python3
"""Generate the checked-in platform event catalog from capabilities.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def render(events: list[str]) -> str:
    members = "\n".join(f'    {event} = "{event}"' for event in events)
    return f'''"""Generated from VoiceRoute Bot Platform capabilities; do not edit."""

from enum import StrEnum


class PlatformEventType(StrEnum):
    """Event names advertised by the contract used for this SDK release."""

{members}


KNOWN_EVENT_TYPES = frozenset(PlatformEventType)
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("capabilities", help="capabilities.json path, or - for stdin")
    parser.add_argument("output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    source = (
        sys.stdin.read()
        if args.capabilities == "-"
        else Path(args.capabilities).read_text(encoding="utf-8")
    )
    document = json.loads(source)
    raw_events = document.get("events")
    if not isinstance(raw_events, list) or not raw_events:
        raise SystemExit("capabilities document does not contain events")
    events = [str(event) for event in raw_events]
    if len(events) != len(set(events)):
        raise SystemExit("capabilities document contains duplicate events")
    rendered = render(events)

    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != rendered:
            raise SystemExit("generated event catalog is stale")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
