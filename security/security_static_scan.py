"""
Shared AST-based static scanner for risky imports and calls.

Provides a single source of truth for lightweight static analysis used by
the sandbox policy and deception detector.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set
import ast
import re


def analyze_code_ast(code: str, *, allowed_modules: Optional[Set[str]] = None) -> Dict[str, Any]:
    """Analyze Python code for risky constructs.

    Returns dict with keys:
      - banned_imports: list[str]
      - disallowed_imports: list[str]
      - dangerous_calls: list[str]
      - dangerous_attributes: list[str] (currently unused)
      - node_count, loop_count, function_defs
      - file_write_possible: bool
      - network_endpoint_literal: bool
    """
    result = {
        'banned_imports': [],
        'disallowed_imports': [],
        'dangerous_calls': [],
        'dangerous_attributes': [],
        'node_count': 0,
        'loop_count': 0,
        'function_defs': 0,
        'file_write_possible': False,
        'network_endpoint_literal': False,
    }
    if not code:
        return result
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return result

    banned_modules = {'os', 'sys', 'subprocess', 'socket', 'requests', 'urllib', 'pathlib', 'shutil'}
    dangerous_calls_set = {'os.system', 'subprocess.Popen', 'subprocess.run', 'subprocess.call', 'socket.socket'}
    banned_functions = {'eval', 'exec', 'open', 'compile', 'globals', 'locals'}

    def _resolve_name(node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parts: List[str] = []
            cur: ast.AST = node
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value  # type: ignore[assignment]
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
                return '.'.join(reversed(parts))
        return None

    banned_imports: List[str] = []
    disallowed_imports: List[str] = []
    dangerous_calls: List[str] = []
    dangerous_attrs: List[str] = []
    loop_count = 0
    function_defs = 0
    node_count = 0
    file_write_possible = False

    for node in ast.walk(tree):
        node_count += 1
        if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            loop_count += 1
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            function_defs += 1
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split('.')[0]
                if root in banned_modules and root not in banned_imports:
                    banned_imports.append(root)
                if allowed_modules is not None and root not in allowed_modules and root not in disallowed_imports:
                    disallowed_imports.append(root)
        if isinstance(node, ast.ImportFrom):
            root = (node.module or '').split('.')[0]
            if root in banned_modules and root not in banned_imports:
                banned_imports.append(root)
            if allowed_modules is not None and root not in allowed_modules and root not in disallowed_imports:
                disallowed_imports.append(root)
        if isinstance(node, ast.Call):
            resolved = _resolve_name(node.func)
            if resolved is None:
                continue
            if resolved.split('.')[0] in banned_functions and resolved not in dangerous_calls:
                dangerous_calls.append(resolved)
            if resolved in dangerous_calls_set and resolved not in dangerous_attrs:
                dangerous_attrs.append(resolved)
            # detect write modes in open()
            if resolved == 'open' and len(getattr(node, 'args', [])) >= 2:
                mode_node = node.args[1]
                if isinstance(mode_node, ast.Constant) and isinstance(mode_node.value, str):
                    m = mode_node.value.lower()
                    if 'w' in m or 'a' in m:
                        file_write_possible = True

    low = code.lower()
    network_literal = bool(re.search(r'https?://', low))

    result.update({
        'banned_imports': banned_imports,
        'disallowed_imports': disallowed_imports,
        'dangerous_calls': dangerous_calls,
        'dangerous_attributes': dangerous_attrs,
        'node_count': node_count,
        'loop_count': loop_count,
        'function_defs': function_defs,
        'file_write_possible': file_write_possible,
        'network_endpoint_literal': network_literal,
    })
    return result

