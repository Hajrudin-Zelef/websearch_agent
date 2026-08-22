"""
Tests unitaires pour sources/router.py.

Basé sur les 11 requêtes du bloc `if __name__ == "__main__":` de router.py,
plus un test structurel vérifiant que toute source dans SOURCES apparaît
dans au moins un niveau de TOOL_LEVELS.
"""

import unittest
import sys
import os

# Ajouter le répertoire parent au path pour importer les sources
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sources.router import route_query, TOOL_LEVELS, _detect_temporal_query, _boost_fresh_sources, _FRESH_SOURCES
from sources import SOURCES


class TestRouterQueries(unittest.TestCase):
    """Tests des 11 requêtes de démonstration de router.py."""

    def test_python(self):
        """Requête simple 'python' → niveau 1, domaine tech."""
        r = route_query("python")
        self.assertEqual(r["level"], 1)
        self.assertIn("tech", r["domains"])
        self.assertIn("github_search", r["tools"])

    def test_w3c_definition(self):
        """Question de définition → niveau 1, intention definition."""
        r = route_query("qu'est-ce que le W3C")
        self.assertEqual(r["level"], 1)
        self.assertIn("definition", r["intents"])
        self.assertIn("wikipedia_search", r["tools"])

    def test_comparaison_react_vue(self):
        """Comparaison technique → score modéré, domaine tech."""
        r = route_query("comparaison entre React et Vue.js pour un projet SPA")
        self.assertGreater(r["complexity_score"], 25)
        self.assertIn("tech", r["domains"])

    def test_meilleur_framework_ai(self):
        """Requête complexe multi-intentions → niveau 3, intentions multiples."""
        r = route_query("quel est le meilleur framework AI en 2026 et pourquoi")
        self.assertEqual(r["level"], 3)
        self.assertIn("compare", r["intents"])
        self.assertIn("recommend", r["intents"])
        self.assertIn("github_search", r["tools"])

    def test_github_langchain(self):
        """Requête code → intention code, domaine tech."""
        r = route_query("github langchain")
        self.assertEqual(r["level"], 1)
        self.assertIn("code", r["intents"])
        self.assertIn("tech", r["domains"])
        self.assertIn("github_search", r["tools"])

    def test_actualites_ia(self):
        """Requête actualités → intention news."""
        r = route_query("actualites IA")
        self.assertEqual(r["level"], 1)
        self.assertIn("news", r["intents"])
        self.assertIn("news_search", r["tools"])

    def test_dataset_climat(self):
        """Requête données → intention data, domaine science."""
        r = route_query("dataset climat")
        self.assertEqual(r["level"], 1)
        self.assertIn("data", r["intents"])
        self.assertIn("science", r["domains"])
        self.assertIn("datasets_search", r["tools"])

    def test_sql_vs_nosql(self):
        """Comparaison technique → niveau 2, intention compare."""
        r = route_query("difference entre SQL et NoSQL")
        self.assertEqual(r["level"], 2)
        self.assertIn("compare", r["intents"])
        self.assertIn("tech", r["domains"])

    def test_installer_docker(self):
        """Tutorial technique → niveau 3, intentions code + howto."""
        r = route_query("comment installer Docker sur Ubuntu")
        self.assertEqual(r["level"], 3)
        self.assertIn("code", r["intents"])
        self.assertIn("howto", r["intents"])
        self.assertIn("tech", r["domains"])

    def test_histoire_philosophie(self):
        """Requête historique → niveau 2, intentions history + domaines multiple."""
        r = route_query("histoire de la philosophie grecque")
        self.assertEqual(r["level"], 2)
        self.assertIn("history", r["intents"])
        self.assertIn("history", r["domains"])
        self.assertIn("philosophy", r["domains"])
        self.assertIn("wikipedia_search", r["tools"])

    def test_securite_apis(self):
        """Requête technique complexe → niveau 2, intention technical."""
        r = route_query("recherche sur la securite des APIs REST")
        self.assertEqual(r["level"], 2)
        self.assertIn("technical", r["intents"])

    def test_bonjour(self):
        """Salutation simple → score très bas, niveau 1, pas d'intention."""
        r = route_query("bonjour")
        self.assertEqual(r["level"], 1)
        self.assertEqual(r["complexity_score"], 0)
        self.assertEqual(r["intents"], [])


class TestStructuralCoverage(unittest.TestCase):
    """Test structurel : toute source doit apparaître dans au moins un niveau."""

    def test_all_sources_in_tool_levels(self):
        """Vérifie que chaque source non-optionnelle de SOURCES a un tool dans TOOL_LEVELS."""
        # Construire la map source -> tool_name attendu
        source_to_tool = {}
        for name, meta in SOURCES.items():
            if meta.get("optional"):
                continue
            if name == "datasets":
                source_to_tool[name] = "datasets_search"
            else:
                source_to_tool[name] = f"{name}_search"

        # Collecter tous les tools de TOOL_LEVELS
        all_level_tools = set()
        for tools in TOOL_LEVELS.values():
            all_level_tools.update(tools)

        # Vérifier chaque source
        missing = []
        for source_name, tool_name in source_to_tool.items():
            if tool_name not in all_level_tools:
                missing.append(f"{source_name} -> {tool_name}")

        self.assertEqual(
            missing, [],
            f"Sources absentes de TOOL_LEVELS : {missing}"
        )

    def test_levels_are_non_empty(self):
        """Chaque niveau de TOOL_LEVELS contient au moins un outil."""
        for level, tools in TOOL_LEVELS.items():
            self.assertGreater(len(tools), 0, f"Niveau {level} est vide")

    def test_level1_smaller_than_level3(self):
        """Le niveau 1 a moins d'outils que le niveau 3."""
        self.assertLess(
            len(TOOL_LEVELS[1]),
            len(TOOL_LEVELS[3]),
            "Le niveau 1 devrait avoir moins d'outils que le niveau 3"
        )


class TestSelectTopSources(unittest.TestCase):
    """Tests pour _select_top_sources — routage intelligent."""

    def test_basic_selection(self):
        """Sélectionne 4 sources pour niveau 1."""
        from sources.router import _select_top_sources
        tools = ["searxng_search", "research_search", "wikipedia_search", "tavily_search"]
        result = _select_top_sources(tools, level=1)
        self.assertEqual(len(result), 4)

    def test_excludes_broken_circuit(self):
        """Exclut les sources avec circuit breaker ouvert."""
        from sources.router import _select_top_sources
        from core.circuit_breaker import circuit_breaker

        # Ouvrir le circuit pour une source
        for _ in range(3):
            circuit_breaker.record_failure("searxng_search")

        tools = ["searxng_search", "research_search", "wikipedia_search"]
        result = _select_top_sources(tools, level=1)
        self.assertNotIn("searxng_search", result)
        self.assertIn("research_search", result)

        # Nettoyer
        circuit_breaker._failures.clear()
        circuit_breaker._circuit_open.clear()

    def test_fallback_to_no_key_sources(self):
        """Palier 3: si toutes les sources candidates ont des clés manquantes,
        le fallback doit trouver des sources sans clé depuis SOURCES."""
        from sources.router import _select_top_sources, _has_valid_key
        from unittest.mock import patch

        # Simuler: toutes les sources candidates nécessitent une clé absente
        tools_with_missing_keys = ["perplexity_search", "brave_search", "firecrawl_search"]

        # Mock _has_valid_key pour retourner False pour toutes les sources candidates
        with patch("sources.router._has_valid_key", return_value=False):
            result = _select_top_sources(tools_with_missing_keys, level=1)

        # Le résultat doit contenir des sources SANS clé (depuis SOURCES)
        self.assertGreater(len(result), 0)
        for tool in result:
            # Vérifier que c'est une source sans clé requise
            source_name = tool.replace("_search", "") if tool != "datasets_search" else "datasets"
            if source_name in SOURCES:
                self.assertFalse(
                    SOURCES[source_name].get("requires_key", False),
                    f"{tool} a requires_key=True mais est dans le fallback"
                )


class TestTemporalFreshness(unittest.TestCase):
    """Tests pour la détection temporelle et le boost de fraîcheur."""

    def test_detect_temporal_event_year(self):
        """Détecte 'coupe du monde 2026' comme requête temporelle."""
        signals = _detect_temporal_query("qui a gagner la coupe du monde 2026")
        self.assertIn("event_year", signals)

    def test_detect_temporal_who_won(self):
        """Détecte 'qui a gagné' comme signal temporel."""
        signals = _detect_temporal_query("qui a gagné l'election 2024")
        self.assertIn("event_year", signals)  # année + événement

    def test_detect_temporal_latest(self):
        """Détecte 'dernière nouvelle' comme signal temporel."""
        signals = _detect_temporal_query("dernière nouvelle sur le climat")
        self.assertIn("latest", signals)

    def test_detect_temporal_brief_news(self):
        """Détecte 'breaking news' comme signal temporel."""
        signals = _detect_temporal_query("breaking news tech")
        self.assertIn("breaking", signals)

    def test_detect_temporal_current_leader(self):
        """Détecte 'champion actuel' comme signal temporel."""
        signals = _detect_temporal_query("qui est le champion actuel du monde")
        self.assertIn("current_leader", signals)

    def test_detect_non_temporal_history(self):
        """Une requête historique ne déclenche pas les signaux temporels."""
        signals = _detect_temporal_query("histoire de la philosophie grecque")
        self.assertEqual(signals, [])

    def test_detect_non_tempal_generic_question(self):
        """Une question générique ne déclenche pas les signaux temporels."""
        signals = _detect_temporal_query("comment fonctionne un moteur de recherche")
        self.assertEqual(signals, [])

    def test_boost_fresh_sources_order(self):
        """Les fresh sources sont déplacées en tête de liste."""
        tools = [
            "perplexity_search", "wikipedia_search", "duckduckgo_search",
            "searxng_search", "research_search", "news_search", "youtube_search",
        ]
        boosted = _boost_fresh_sources(tools)
        
        # Vérifier qu'aucune source non-fraîche n'apparaît AVANT une source fraîche
        seen_fresh = False
        non_fresh_before_fresh = []
        for t in boosted:
            if t in _FRESH_SOURCES:
                seen_fresh = True
            elif not seen_fresh:
                non_fresh_before_fresh.append(t)
        
        self.assertEqual(
            non_fresh_before_fresh, [],
            f"Sources non-fraîches détectées avant les sources fraîches: {non_fresh_before_fresh}"
        )

    def test_route_temporal_prioritizes_fresh(self):
        """Une requête temporelle place duckduckgo/searxng/news en tête."""
        r = route_query("qui a gagner la coupe du monde 2026")
        
        fresh_in_tools = [t for t in r["tools"] if t in _FRESH_SOURCES]
        self.assertGreater(len(fresh_in_tools), 0, 
                          "Aucune source fraîche détectée dans les outils")
        
        # DuckDuckGo ou SearXNG doivent être parmi les premiers
        top_5 = r["tools"][:5]
        has_fresh_in_top5 = any(t in top_5 for t in _FRESH_SOURCES)
        self.assertTrue(has_fresh_in_top5, 
                       f"Les sources fraîches ne sont pas dans le top 5: {top_5}")

    def test_route_non_temporal_unchanged(self):
        """Une requête non-temporelle n'a pas ses sources réordonnées."""
        r_normal = route_query("histoire de la philosophie grecque")
        
        # Pour une req normale, wikipedia devrait être avant duckduckgo
        wiki_idx = r_normal["tools"].index("wikipedia_search") if "wikipedia_search" in r_normal["tools"] else -1
        ddg_idx = r_normal["tools"].index("duckduckgo_search") if "duckduckgo_search" in r_normal["tools"] else -1
        
        # Si les deux sont présents, wikipedia doit être avant duckduckgo
        if wiki_idx >= 0 and ddg_idx >= 0:
            self.assertLess(wiki_idx, ddg_idx,
                           "Pour une req non-temporelle, wikipedia devrait être avant duckduckgo")


if __name__ == "__main__":
    unittest.main()
