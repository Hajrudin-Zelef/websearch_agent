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

from sources.router import route_query, TOOL_LEVELS
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
        """Vérifie que chaque source de SOURCES a un tool dans TOOL_LEVELS."""
        # Construire la map source -> tool_name attendu
        source_to_tool = {}
        for name in SOURCES:
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


if __name__ == "__main__":
    unittest.main()
