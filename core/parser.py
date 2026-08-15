"""
Parsing des tool calls — DSML et JSON brut.
Extrait de agent.py lors du refactoring.
"""

import re
import json
import uuid


def _parse_dsml_tool_calls(text: str) -> list[dict]:
    """Parse les tool calls au format DSML."""
    if not text or "DSML" not in text:
        return []

    tool_calls: list[dict] = []

    invoke_pattern = re.compile(
        r"<.DSML..>invoke\s+name=\"(\w+)\">(.*?)</.DSML..>invoke>",
        re.DOTALL,
    )
    param_pattern = re.compile(
        r"<.DSML..>parameter\s+name=\"(\w+)\"[^>]*>(.*?)</.DSML..>parameter>",
        re.DOTALL,
    )

    for invoke_match in invoke_pattern.finditer(text):
        func_name = invoke_match.group(1)
        params_block = invoke_match.group(2)

        arguments: dict[str, str] = {}
        for param_match in param_pattern.finditer(params_block):
            param_name = param_match.group(1)
            param_value = param_match.group(2).strip()
            arguments[param_name] = param_value

        tool_calls.append({
            "id": f"dsml_{uuid.uuid4().hex[:8]}",
            "type": "function",
            "function": {
                "name": func_name,
                "arguments": json.dumps(arguments, ensure_ascii=False),
            },
        })

    return tool_calls


def _parse_json_tool_calls(text: str, known_tools: set[str] = None) -> list[dict]:
    """Detecte les tool-calls emis en JSON brut par un modele
    qui ne supporte pas le function-calling natif.

    Ex: {"name": "perplexity_search", "arguments": {"query": "taux euro FCFA"}}
    """
    if not text:
        return []

    tool_calls: list[dict] = []
    decoder = json.JSONDecoder()

    idx = 0
    while idx < len(text):
        brace_idx = text.find("{", idx)
        if brace_idx == -1:
            break

        try:
            obj, end = decoder.raw_decode(text[brace_idx:])
        except json.JSONDecodeError:
            idx = brace_idx + 1
            continue

        if (
            isinstance(obj, dict)
            and "name" in obj
            and "arguments" in obj
            and (known_tools is None or obj["name"] in known_tools)
        ):
            func_name = obj["name"]
            args = obj["arguments"]
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"query": args}
            if not isinstance(args, dict):
                args = {"query": str(args)}

            tool_calls.append({
                "id": f"json_{uuid.uuid4().hex[:8]}",
                "type": "function",
                "function": {
                    "name": func_name,
                    "arguments": json.dumps(args, ensure_ascii=False),
                },
            })

        idx = brace_idx + end

    return tool_calls
