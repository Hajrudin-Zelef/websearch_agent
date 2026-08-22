"""
Tests unitaires pour core/parser.py.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.parser import _parse_dsml_tool_calls, _parse_json_tool_calls


class TestParser(unittest.TestCase):

    def test_parse_dsml_empty(self):
        """Retourne [] pour texte vide."""
        self.assertEqual(_parse_dsml_tool_calls(""), [])

    def test_parse_dsml_no_dsml(self):
        """Retourne [] si pas de DSML."""
        self.assertEqual(_parse_dsml_tool_calls("Juste du texte"), [])

    def test_parse_dsml_valid(self):
        """Parse un tool call DSML valide."""
        text = '<.DSML..>invoke name="perplexity_search"><.DSML..>parameter name="query">test query</.DSML..></.DSML..>invoke>'
        result = _parse_dsml_tool_calls(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["function"]["name"], "perplexity_search")

    def test_parse_json_empty(self):
        """Retourne [] pour texte vide."""
        self.assertEqual(_parse_json_tool_calls(""), [])

    def test_parse_json_no_tool(self):
        """Retourne [] si pas de tool call."""
        self.assertEqual(_parse_json_tool_calls("Juste du texte"), [])

    def test_parse_json_valid(self):
        """Parse un tool call JSON valide."""
        text = '{"name": "perplexity_search", "arguments": {"query": "test"}}'
        result = _parse_json_tool_calls(text, known_tools={"perplexity_search"})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["function"]["name"], "perplexity_search")

    def test_parse_json_unknown_tool(self):
        """Ignore les outils inconnus."""
        text = '{"name": "unknown_tool", "arguments": {"query": "test"}}'
        result = _parse_json_tool_calls(text, known_tools={"perplexity_search"})
        self.assertEqual(len(result), 0)

    def test_parse_json_string_args(self):
        """Parse les arguments en string."""
        text = '{"name": "perplexity_search", "arguments": "test query"}'
        result = _parse_json_tool_calls(text, known_tools={"perplexity_search"})
        self.assertEqual(len(result), 1)
        args = json.loads(result[0]["function"]["arguments"])
        self.assertIn("query", args)


if __name__ == "__main__":
    unittest.main()
