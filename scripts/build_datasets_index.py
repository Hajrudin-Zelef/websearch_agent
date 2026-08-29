#!/usr/bin/env python3
"""
Build datasets_index.json from two curated awesome-datasets repos:
  - awesome-public-datasets (RST format, ~250 static datasets)
  - awesome-public-real-time-datasets (Markdown format, ~90 real-time sources)

Usage:
  python scripts/build_datasets_index.py

Output:
  sources/datasets_index.json
"""

import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger("build_datasets_index")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# --- Config ----------------------------------------------------------------

RST_URL = (
    "https://raw.githubusercontent.com/awesomedata/"
    "awesome-public-datasets/master/README.rst"
)
RT_MD_URL = (
    "https://raw.githubusercontent.com/bytewax/"
    "awesome-public-real-time-datasets/master/README.md"
)

HEADERS = {"User-Agent": "websearch-agent/1.0 (index builder)"}

# Categories from RST we want to keep (top-level sections)
RST_SECTIONS: set[str] = {
    "Agriculture", "Architecture", "Biology", "Climate+Weather",
    "ComplexNetworks", "ComputerNetworks", "DataChallenges", "EarthScience",
    "Economics", "Education", "Energy", "Finance", "GIS", "Government",
    "Healthcare", "ImageProcessing", "MachineLearning", "Museums",
    "NaturalLanguage", "Neuroscience", "Physics", "Psychology+Cognition",
    "PublicDomains", "SearchEngines", "SocialNetworks", "SocialSciences",
    "Software", "Sports", "TimeSeries", "Transportation",
}

# --- Helpers ---------------------------------------------------------------


def fetch_text(url: str) -> str:
    """Fetch raw text from a URL, raise on failure."""
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def clean_description(desc: str) -> str:
    """Collapse whitespace and truncate long descriptions."""
    desc = re.sub(r"\s+", " ", desc).strip()
    # Remove trailing "[...]" artifact from RST
    desc = re.sub(r"\s*\[\.\.\.\]$", "", desc)
    if len(desc) > 250:
        desc = desc[:247] + "..."
    return desc


# --- RST parser (awesome-public-datasets) ----------------------------------

# Matches: * |OK_ICON| `Name - Description <URL>`_
RST_ENTRY_RE = re.compile(
    r"^\*\s+\|(OK|FIXME)_ICON\|\s+"
    r"`(.+?)\s+<((?:https?|ftp)://[^>]+)>`_"
)


def parse_rst(text: str) -> list[dict[str, str]]:
    """Parse RST README into a list of dataset dicts."""
    datasets: list[dict[str, str]] = []
    current_section = "Other"
    lines = text.splitlines()
    section_underline_re = re.compile(r"^-{3,}$")

    for i, line in enumerate(lines):
        # Section header? Title on line i, dashes on line i+1
        if i + 1 < len(lines) and section_underline_re.match(lines[i + 1]):
            candidate = line.strip()
            if candidate in RST_SECTIONS:
                current_section = candidate
            continue

        # Skip the underline line itself
        if section_underline_re.match(line):
            continue

        # Dataset entry?
        entry_match = RST_ENTRY_RE.match(line)
        if not entry_match:
            continue

        status = entry_match.group(1)  # OK or FIXME
        body = entry_match.group(2).strip()
        url = entry_match.group(3).strip()

        # Split body into name and description: "Name - Description"
        if " - " in body:
            name, _, desc = body.partition(" - ")
        else:
            name = body
            desc = ""

        name = name.strip()
        desc = clean_description(desc)

        # Skip entries without a meaningful name
        if not name or len(name) < 3:
            continue

        datasets.append({
            "title": name,
            "url": url,
            "description": desc,
            "category": current_section,
            "type": "static",
            "status": "ok" if status == "OK" else "fixme",
        })

    return datasets


# --- Markdown parser (awesome-public-real-time-datasets) -------------------

MD_SECTION_RE = re.compile(r"^###\s+(.+)$")
# Matches: - [Name](URL) - Description  (with optional leading space)
MD_ENTRY_RE = re.compile(
    r"^\s*- \[(.+?)\]\(((?:https?|wss?)://[^)]+)\)"
    r"\s*(?:-|—|–)?\s*(.*)$"
)


def parse_realtime_md(text: str) -> list[dict[str, str]]:
    """Parse the real-time datasets README (Markdown)."""
    datasets: list[dict[str, str]] = []
    current_section = "Other"
    current_tier = "free"  # "free" or "paid"

    for line in text.splitlines():
        # Tier: ## Free or ## Paid
        if line.startswith("## Free"):
            current_tier = "free"
            continue
        if line.startswith("## Paid"):
            current_tier = "paid"
            continue

        # Section: ### Category
        section_match = MD_SECTION_RE.match(line)
        if section_match:
            current_section = section_match.group(1).strip()
            continue

        # Dataset entry
        entry_match = MD_ENTRY_RE.match(line)
        if not entry_match:
            continue

        name = entry_match.group(1).strip()
        url = entry_match.group(2).strip()
        desc = entry_match.group(3).strip()

        if not name or len(name) < 3:
            continue

        desc = clean_description(desc)
        full_section = f"{current_section} ({current_tier})"

        datasets.append({
            "title": name,
            "url": url,
            "description": desc,
            "category": full_section,
            "type": "realtime",
            "status": "ok",
        })

    return datasets


# --- Main ------------------------------------------------------------------

def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    output_path = repo_root / "sources" / "datasets_index.json"

    logger.info("Fetching awesome-public-datasets (RST)...")
    rst_text = fetch_text(RST_URL)
    static_datasets = parse_rst(rst_text)
    logger.info("  -> %d static datasets parsed", len(static_datasets))

    logger.info("Fetching awesome-public-real-time-datasets (MD)...")
    md_text = fetch_text(RT_MD_URL)
    realtime_datasets = parse_realtime_md(md_text)
    logger.info("  -> %d real-time sources parsed", len(realtime_datasets))

    all_datasets = static_datasets + realtime_datasets
    logger.info("Total: %d datasets", len(all_datasets))

    # Stats by category
    categories: dict[str, int] = {}
    for d in all_datasets:
        cat = d["category"]
        categories[cat] = categories.get(cat, 0) + 1
    for cat, count in sorted(categories.items()):
        logger.info("  %s: %d", cat, count)

    # Write JSON
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(all_datasets, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Written to %s (%d entries)", output_path, len(all_datasets))


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as e:
        logger.error("Fetch failed: %s", e)
        sys.exit(1)
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        sys.exit(1)
