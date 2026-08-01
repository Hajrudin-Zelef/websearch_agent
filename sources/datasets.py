"""
Source Datasets — recherche dans un index local de ~1000 datasets publics.
Les datasets sont indexes depuis deux annuaires GitHub :
  - awesome-public-datasets (datasets statiques : climat, sante, economie...)
  - awesome-public-real-time-datasets (flux temps reel : finance, transport...)

Format de l'index : sources/datasets_index.json
Genere par : python scripts/build_datasets_index.py
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("websearch-agent.datasets")

_INDEX_PATH = Path(__file__).resolve().parent / "datasets_index.json"
_index: list[dict[str, str]] | None = None


def _load_index() -> list[dict[str, str]]:
    """Charge l'index JSON (avec cache en memoire)."""
    global _index
    if _index is not None:
        return _index
    try:
        data = _INDEX_PATH.read_text(encoding="utf-8")
        _index = json.loads(data)
        logger.info("Index datasets charge : %d entrees", len(_index))
        return _index
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning("Impossible de charger l'index datasets : %s", e)
        _index = []
        return _index


def datasets_search(
    query: str = "", max_results: int = 10
) -> list[dict[str, str]]:
    """
    Recherche des datasets publics par mots-cles.

    Cherche dans le titre, la description et la categorie.
    Si query est vide, retourne un echantillon representatif par categorie.

    Args:
        query: Mots-cles de recherche (ex: "climat", "NLP francais").
        max_results: Nombre max de resultats.

    Returns:
        Liste de {title, url, snippet} (format standard des sources).
    """
    entries = _load_index()
    query_lower = query.lower().strip() if query else ""

    if not query_lower:
        # Sans query : retourne 1 dataset par categorie
        seen: set[str] = set()
        results: list[dict[str, str]] = []
        for entry in entries:
            cat = entry.get("category", "")
            if cat not in seen:
                seen.add(cat)
                results.append(_format_entry(entry))
                if len(results) >= max_results:
                    break
        return results

    # Recherche par mots-cles (chaque mot doit matcher)
    keywords = query_lower.split()
    scored: list[tuple[int, dict[str, str]]] = []

    for entry in entries:
        title = entry.get("title", "").lower()
        desc = entry.get("description", "").lower()
        cat = entry.get("category", "").lower()
        searchable = f"{title} {desc} {cat}"

        # Score = nombre de mots-cles qui matchent
        score = sum(1 for kw in keywords if kw in searchable)
        if score > 0:
            # Bonus pour match dans le titre
            title_score = sum(1 for kw in keywords if kw in title)
            scored.append((score + title_score, entry))

    # Trier par score decroissant
    scored.sort(key=lambda x: x[0], reverse=True)

    return [_format_entry(entry) for _, entry in scored[:max_results]]


def _format_entry(entry: dict[str, Any]) -> dict[str, str]:
    """Formate une entree de l'index en {title, url, snippet}."""
    cat = entry.get("category", "")
    dtype = entry.get("type", "")
    desc = entry.get("description", "")

    # Snippet : [categorie] [type] description
    tags = []
    if cat:
        tags.append(cat)
    if dtype == "realtime":
        tags.append("temps reel")
    tag_str = f"[{' | '.join(tags)}] " if tags else ""

    return {
        "title": entry.get("title", ""),
        "url": entry.get("url", ""),
        "snippet": f"{tag_str}{desc}",
    }


if __name__ == "__main__":
    import sys
    import json as _json

    query = sys.argv[1] if len(sys.argv) > 1 else ""
    results = datasets_search(query)
    print(_json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n-> {len(results)} resultat(s)")
