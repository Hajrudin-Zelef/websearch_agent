"""
Source YouTube — recherche video via yt-dlp.
Retourne [{"title", "url", "snippet"}].

Pas de cle API requise. Utilise yt-dlp pour la recherche YouTube.
"""

import json
import logging
import subprocess

logger = logging.getLogger("websearch-agent.youtube")


def youtube_search(query: str, max_results: int = 5, time_range: str | None = None) -> list[dict[str, str]]:
    """Recherche YouTube via yt-dlp et retourne des resultats structures."""
    results = []

    try:
        cmd = [
            "yt-dlp",
            f"ytsearch{min(max_results, 10)}:{query}",
            "--dump-json",
            "--flat-playlist",
            "--no-warnings",
            "--quiet",
        ]

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if proc.returncode != 0:
            logger.warning("yt-dlp search echoue: %s", proc.stderr[:200])
            return results

        for line in proc.stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                results.append({
                    "title": data.get("title", ""),
                    "url": data.get("url", f"https://www.youtube.com/watch?v={data.get('id', '')}"),
                    "snippet": data.get("description", "")[:300] if data.get("description") else "",
                })
            except json.JSONDecodeError:
                continue

    except FileNotFoundError:
        logger.warning("yt-dlp non installe")
    except subprocess.TimeoutExpired:
        logger.warning("yt-dlp search timeout")
    except Exception as e:
        logger.warning("youtube_search echoue: %s", e)

    return results[:max_results]


if __name__ == "__main__":
    import sys

    query = sys.argv[1] if len(sys.argv) > 1 else "latest AI news"
    results = youtube_search(query)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n-> {len(results)} resultat(s)")
