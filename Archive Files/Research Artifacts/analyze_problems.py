"""Analyze common code issues that might show up in VS Code Problems pane."""

import ast
import os
from pathlib import Path
from collections import defaultdict

def analyze_file(filepath):
    """Analyze a Python file for common issues."""
    issues = []

    try:
        with open(filepath, 'r') as f:
            source = f.read()
            tree = ast.parse(source, filename=str(filepath))
    except SyntaxError as e:
        issues.append(f"SYNTAX_ERROR: {e}")
        return issues
    except Exception as e:
        issues.append(f"PARSE_ERROR: {e}")
        return issues

    # Check for missing type hints on functions
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Check if return type is missing
            if node.returns is None and node.name != '__init__':
                issues.append(f"MISSING_RETURN_TYPE: {node.name} (line {node.lineno})")

            # Check if argument types are missing
            for arg in node.args.args:
                if arg.annotation is None and arg.arg != 'self' and arg.arg != 'cls':
                    issues.append(f"MISSING_ARG_TYPE: {node.name}.{arg.arg} (line {node.lineno})")

        # Check for bare except
        elif isinstance(node, ast.ExceptHandler):
            if node.type is None:
                issues.append(f"BARE_EXCEPT: line {node.lineno}")

        # Check for `Any` type usage
        elif isinstance(node, ast.Name) and node.id == 'Any':
            issues.append(f"ANY_TYPE_USED: line {node.lineno}")

    return issues

def main():
    """Analyze all Python files in project."""
    project_root = Path('.')
    issue_counts = defaultdict(int)
    file_issues = {}

    for py_file in project_root.rglob('*.py'):
        # Skip venv and hidden directories
        if any(part.startswith('.') or part == 'venv' for part in py_file.parts):
            continue

        issues = analyze_file(py_file)
        if issues:
            file_issues[str(py_file)] = issues
            for issue in issues:
                issue_type = issue.split(':')[0]
                issue_counts[issue_type] += 1

    # Print summary
    print("=" * 80)
    print("CODE ANALYSIS SUMMARY")
    print("=" * 80)
    print(f"\nTotal files analyzed: {len(list(project_root.rglob('*.py')))}")
    print(f"Files with issues: {len(file_issues)}")
    print(f"\nIssue breakdown:")
    for issue_type, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {issue_type}: {count}")

    # Print top 10 files with most issues
    print(f"\n\nTop 10 files with most issues:")
    sorted_files = sorted(file_issues.items(), key=lambda x: len(x[1]), reverse=True)[:10]
    for filepath, issues in sorted_files:
        print(f"\n{filepath} ({len(issues)} issues):")
        for issue in issues[:5]:  # Show first 5 issues
            print(f"  - {issue}")
        if len(issues) > 5:
            print(f"  ... and {len(issues) - 5} more")

if __name__ == '__main__':
    main()
