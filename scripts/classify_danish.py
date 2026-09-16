#!/usr/bin/env python3
"""Apply the project's transparent Danish-evidence classification rule."""

from __future__ import annotations

import argparse
import csv
import ipaddress
from collections import defaultdict
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def parse_network(value: str) -> ipaddress._BaseNetwork | ipaddress._BaseAddress | None:
    try:
        if "/" in value:
            return ipaddress.ip_network(value, strict=False)
        return ipaddress.ip_address(value)
    except ValueError:
        return None


def overlaps(left: ipaddress._BaseNetwork | ipaddress._BaseAddress, right: ipaddress._BaseNetwork | ipaddress._BaseAddress) -> bool:
    if left.version != right.version:
        return False
    if isinstance(left, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
        return left in right
    if isinstance(right, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
        return right in left
    return left.overlaps(right)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="normalized observations CSV")
    parser.add_argument("--evidence", type=Path, required=True, help="filled Danish evidence CSV")
    parser.add_argument("--prefixes", type=Path, required=True, help="filled Danish prefix CSV")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    observations = read_csv(args.input)
    evidence = read_csv(args.evidence)
    prefixes = read_csv(args.prefixes)

    evidence_by_indicator: dict[str, list[dict[str, str]]] = defaultdict(list)
    for item in evidence:
        indicator = (item.get("indicator") or "").strip().lower()
        if indicator:
            evidence_by_indicator[indicator].append(item)

    prefix_networks: list[tuple[ipaddress._BaseNetwork, dict[str, str]]] = []
    for item in prefixes:
        parsed = parse_network((item.get("prefix") or "").strip())
        if isinstance(parsed, (ipaddress.IPv4Network, ipaddress.IPv6Network)):
            prefix_networks.append((parsed, item))

    unique = sorted(
        {
            (item.get("source_name", ""), item.get("indicator_type", ""), item.get("indicator", ""))
            for item in observations
            if item.get("indicator")
        }
    )
    result: list[dict[str, object]] = []
    for source, indicator_type, indicator in unique:
        signals: set[str] = set()
        non_dk_signals: set[str] = set()
        supporting_notes: list[str] = []

        for item in evidence_by_indicator.get(indicator.lower(), []):
            signal = (item.get("signal") or "unspecified").strip()
            country = (item.get("country") or "").strip().upper()
            evidence_source = (item.get("evidence_source") or "unknown-source").strip()
            key = f"{signal} ({evidence_source})"
            if country == "DK":
                signals.add(key)
                supporting_notes.append(f"{signal}:DK/{evidence_source}")
            elif country and country not in {"UNKNOWN", "N/A", "NA"}:
                non_dk_signals.add(key)
                supporting_notes.append(f"{signal}:{country}/{evidence_source}")

        parsed = parse_network(indicator) if indicator_type in {"ip", "cidr"} else None
        if parsed is not None:
            for network, item in prefix_networks:
                if overlaps(parsed, network):
                    evidence_source = (item.get("evidence_source") or "prefix-register").strip()
                    key = f"allocation-prefix ({evidence_source})"
                    signals.add(key)
                    supporting_notes.append(f"allocation-prefix:DK/{evidence_source}")

        if signals and non_dk_signals:
            classification = "Conflicting"
        elif len(signals) >= 2:
            classification = "DK-supported"
        elif len(signals) == 1:
            classification = "DK-weak"
        else:
            classification = "Unknown"

        result.append(
            {
                "source_name": source,
                "indicator_type": indicator_type,
                "indicator": indicator,
                "country_class": classification,
                "danish_signal_count": len(signals),
                "non_danish_signal_count": len(non_dk_signals),
                "evidence_notes": "; ".join(sorted(set(supporting_notes))),
            }
        )

    fields = [
        "source_name",
        "indicator_type",
        "indicator",
        "country_class",
        "danish_signal_count",
        "non_danish_signal_count",
        "evidence_notes",
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(result)
    print(f"wrote {len(result)} classifications to {args.out}")


if __name__ == "__main__":
    main()

