#!/usr/bin/env python3
"""
Dependency Analysis Script
Analyzes all Python files in the project and creates a comprehensive dependency map.
"""

import os
import re
import ast
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple

# Project root
PROJECT_ROOT = Path(__file__).parent

def find_python_files() -> List[Path]:
    """Find all Python files in project, excluding venv and cache directories."""
    python_files = []
    exclude_dirs = {'.venv', 'venv', '__pycache__', '.git', 'node_modules'}

    for root, dirs, files in os.walk(PROJECT_ROOT):
        # Remove excluded directories from search
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        for file in files:
            if file.endswith('.py'):
                python_files.append(Path(root) / file)

    return sorted(python_files)

def extract_imports(file_path: Path) -> Tuple[Set[str], Set[str], List[str]]:
    """
    Extract imports from a Python file.
    Returns: (stdlib_imports, external_imports, local_imports)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast.parse(content)

        stdlib_imports = set()
        external_imports = set()
        local_imports = []

        stdlib_modules = {
            'hashlib', 'json', 'datetime', 'typing', 'dataclasses', 'enum', 'logging',
            'os', 're', 'sys', 'time', 'collections', 'math', 'pathlib', 'tempfile',
            'shutil', 'subprocess', 'io', 'copy', 'itertools', 'functools', 'asyncio',
            'unittest', 'random', 'struct', 'binascii', 'base64', 'hmac', 'secrets',
            'contextlib', 'warnings', 'abc', 'configparser'
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.split('.')[0]
                    if module in stdlib_modules:
                        stdlib_imports.add(module)
                    else:
                        external_imports.add(module)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module = node.module.split('.')[0]
                    if module in stdlib_modules:
                        stdlib_imports.add(module)
                    else:
                        # Check if it's a local import
                        if node.level == 0:  # Absolute import
                            local_imports.append(node.module)
                        else:  # Relative import
                            local_imports.append(node.module if node.module else '.')

        return stdlib_imports, external_imports, local_imports

    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return set(), set(), []

def get_file_type(file_path: Path, content_preview: str = "") -> str:
    """Categorize file by its role in the project."""
    path_str = str(file_path)
    name = file_path.name

    if '/tests/' in path_str or name.startswith('test_'):
        return 'test'
    elif '/examples/' in path_str or 'demo' in name or 'example' in name:
        return 'example'
    elif '/tools/' in path_str:
        return 'tool'
    elif '/ui/' in path_str:
        return 'ui'
    elif name == '__init__.py':
        return 'init'
    elif 'orchestrator' in name:
        return 'core-orchestrator'
    elif any(x in name for x in ['memory', 'merkle', 'audit']):
        return 'core-storage'
    elif any(x in name for x in ['translator', 'hardware', 'codec']):
        return 'core-hardware'
    elif any(x in name for x in ['alignment', 'deception', 'semantic']):
        return 'core-safety'
    elif any(x in name for x in ['reputation', 'reward', 'incentive']):
        return 'core-economics'
    elif any(x in name for x in ['worm', 'usb', 'security']):
        return 'core-security'
    elif any(x in name for x in ['llm', 'adapter']):
        return 'core-llm'
    else:
        return 'utility'

def analyze_file_content(file_path: Path) -> Dict:
    """Analyze file content to extract metadata."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast.parse(content)

        classes = []
        functions = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append(node.name)
            elif isinstance(node, ast.FunctionDef):
                # Only top-level functions
                if isinstance(node, ast.FunctionDef) and node.col_offset == 0:
                    functions.append(node.name)

        # Get docstring
        docstring = ast.get_docstring(tree)

        return {
            'classes': classes,
            'functions': functions,
            'docstring': docstring[:200] if docstring else None,
            'lines': len(content.split('\n'))
        }
    except Exception as e:
        return {
            'classes': [],
            'functions': [],
            'docstring': None,
            'lines': 0
        }

def build_dependency_graph():
    """Build complete dependency graph of the project."""
    files = find_python_files()

    file_info = {}
    local_dependency_graph = defaultdict(set)
    reverse_dependencies = defaultdict(set)

    # First pass: collect all file info
    for file_path in files:
        rel_path = file_path.relative_to(PROJECT_ROOT)

        stdlib_imports, external_imports, local_imports = extract_imports(file_path)
        content_info = analyze_file_content(file_path)
        file_type = get_file_type(file_path)

        # Convert local imports to file paths
        local_files = []
        for imp in local_imports:
            # Try to resolve import to actual file
            imp_parts = imp.split('.')

            # Check if it's a module in the project
            possible_files = [
                PROJECT_ROOT / f"{imp_parts[0]}.py",
                PROJECT_ROOT / imp_parts[0] / "__init__.py",
            ]

            if len(imp_parts) > 1:
                possible_files.append(PROJECT_ROOT / imp_parts[0] / f"{imp_parts[1]}.py")

            for pf in possible_files:
                if pf.exists():
                    local_files.append(pf.relative_to(PROJECT_ROOT))
                    break

        file_info[str(rel_path)] = {
            'path': rel_path,
            'type': file_type,
            'stdlib_imports': sorted(stdlib_imports),
            'external_imports': sorted(external_imports),
            'local_imports': local_imports,
            'local_files': [str(f) for f in local_files],
            'classes': content_info['classes'],
            'functions': content_info['functions'],
            'docstring': content_info['docstring'],
            'lines': content_info['lines']
        }

        # Build dependency graph
        for local_file in local_files:
            local_dependency_graph[str(rel_path)].add(str(local_file))
            reverse_dependencies[str(local_file)].add(str(rel_path))

    return file_info, dict(local_dependency_graph), dict(reverse_dependencies)

def generate_report(file_info, dependency_graph, reverse_dependencies):
    """Generate comprehensive dependency report."""
    report = []

    report.append("# AI Safety System - Project Dependency Map")
    report.append("")
    report.append("Generated: " + str(Path(__file__).parent))
    report.append("")
    report.append("## Table of Contents")
    report.append("1. [Project Overview](#project-overview)")
    report.append("2. [File Inventory](#file-inventory)")
    report.append("3. [Dependency Matrix](#dependency-matrix)")
    report.append("4. [Reverse Dependencies](#reverse-dependencies)")
    report.append("5. [Core Module Analysis](#core-module-analysis)")
    report.append("6. [Orphaned Files](#orphaned-files)")
    report.append("7. [Recommendations](#recommendations)")
    report.append("")

    # Overview
    report.append("## Project Overview")
    report.append("")
    report.append(f"**Total Python Files:** {len(file_info)}")
    report.append(f"**Total Lines of Code:** {sum(info['lines'] for info in file_info.values())}")
    report.append("")

    # Categorize files
    by_type = defaultdict(list)
    for path, info in file_info.items():
        by_type[info['type']].append(path)

    report.append("**Files by Category:**")
    for ftype, files in sorted(by_type.items()):
        report.append(f"- {ftype}: {len(files)} files")
    report.append("")

    # File Inventory
    report.append("## File Inventory")
    report.append("")

    for ftype in sorted(by_type.keys()):
        report.append(f"### {ftype.upper()}")
        report.append("")

        for path in sorted(by_type[ftype]):
            info = file_info[path]
            report.append(f"#### `{path}`")
            if info['docstring']:
                report.append(f"*{info['docstring']}*")
            report.append(f"- **Lines:** {info['lines']}")
            if info['classes']:
                report.append(f"- **Classes:** {', '.join(info['classes'][:5])}")
            if info['functions']:
                report.append(f"- **Functions:** {', '.join(info['functions'][:5])}")
            if info['local_files']:
                report.append(f"- **Depends on:** {', '.join(info['local_files'])}")
            report.append("")

    # Dependency Matrix
    report.append("## Dependency Matrix")
    report.append("")
    report.append("Files and their direct dependencies:")
    report.append("")

    for path in sorted(dependency_graph.keys()):
        deps = dependency_graph[path]
        if deps:
            report.append(f"- **{path}**")
            for dep in sorted(deps):
                report.append(f"  - → {dep}")
            report.append("")

    # Reverse Dependencies
    report.append("## Reverse Dependencies")
    report.append("")
    report.append("Files and what depends on them (most depended-on first):")
    report.append("")

    sorted_reverse = sorted(reverse_dependencies.items(),
                           key=lambda x: len(x[1]), reverse=True)

    for path, dependents in sorted_reverse:
        if dependents:
            report.append(f"- **{path}** (used by {len(dependents)} files)")
            for dep in sorted(list(dependents)[:10]):
                report.append(f"  - ← {dep}")
            if len(dependents) > 10:
                report.append(f"  - ... and {len(dependents) - 10} more")
            report.append("")

    # Core Module Analysis
    report.append("## Core Module Analysis")
    report.append("")

    core_modules = {k: v for k, v in reverse_dependencies.items() if len(v) >= 3}
    report.append(f"**Core modules** (used by 3+ files): {len(core_modules)}")
    report.append("")

    for path, dependents in sorted(core_modules.items(),
                                   key=lambda x: len(x[1]), reverse=True):
        report.append(f"### `{path}` ({len(dependents)} dependents)")
        info = file_info[path]
        if info['docstring']:
            report.append(f"*{info['docstring']}*")
        report.append("")
        report.append(f"**Key exports:**")
        if info['classes']:
            report.append(f"- Classes: {', '.join(info['classes'])}")
        if info['functions']:
            report.append(f"- Functions: {', '.join(info['functions'])}")
        report.append("")

    # Orphaned Files
    report.append("## Orphaned Files")
    report.append("")

    orphaned = []
    for path, info in file_info.items():
        # Not imported by anyone and not a test/example/tool
        if path not in reverse_dependencies and info['type'] not in ['test', 'example', 'tool', 'init']:
            # Also not a main script (doesn't import anything local)
            if not dependency_graph.get(path):
                orphaned.append(path)

    if orphaned:
        report.append("Files not connected to the main system:")
        report.append("")
        for path in sorted(orphaned):
            info = file_info[path]
            report.append(f"- **{path}** ({info['lines']} lines, type: {info['type']})")
            if info['docstring']:
                report.append(f"  - {info['docstring'][:100]}")
        report.append("")
    else:
        report.append("No orphaned files found.")
        report.append("")

    # Recommendations
    report.append("## Recommendations")
    report.append("")

    # Find duplicate implementations
    report.append("### Potential Duplicates")
    report.append("")

    similar_files = defaultdict(list)
    for path, info in file_info.items():
        base_name = Path(path).stem
        if any(x in base_name for x in ['_alt', '_v2', '_optimized', '_enhanced']):
            base = base_name.replace('_alt', '').replace('_v2', '').replace('_optimized', '').replace('_enhanced', '')
            similar_files[base].append(path)

    for base, files in similar_files.items():
        if len(files) > 1:
            report.append(f"**{base}** variants:")
            for f in files:
                report.append(f"- {f}")
            report.append("")

    # Find files with no classes or functions
    report.append("### Empty or Minimal Files")
    report.append("")
    empty_files = [path for path, info in file_info.items()
                   if not info['classes'] and not info['functions'] and info['type'] != 'init']
    if empty_files:
        for path in empty_files:
            report.append(f"- {path}")
        report.append("")

    return '\n'.join(report)

if __name__ == '__main__':
    print("Analyzing project dependencies...")
    file_info, dep_graph, rev_deps = build_dependency_graph()

    print(f"Found {len(file_info)} Python files")
    print(f"Generating report...")

    report = generate_report(file_info, dep_graph, rev_deps)

    output_file = PROJECT_ROOT / 'PROJECT_DEPENDENCY_MAP.md'
    with open(output_file, 'w') as f:
        f.write(report)

    print(f"Report saved to: {output_file}")
