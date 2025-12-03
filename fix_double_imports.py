#!/usr/bin/env python3
"""
Fix double module imports created by the import fix script.
"""

import os
import re
from pathlib import Path

def fix_double_imports_in_file(file_path: Path) -> bool:
    """Fix double imports in a single file. Returns True if file was modified."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # Fix double module imports
        content = re.sub(
            r'from (\w+\.\w+) import \1\.(\w+)',
            r'from \1 import \2',
            content
        )

        # Only write if content changed
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True

    except Exception as e:
        print(f"Error processing {file_path}: {e}")

    return False

def main():
    """Fix double imports in all Python files."""
    repo_root = Path(__file__).parent

    # Find all Python files excluding archived and venv
    exclude_patterns = [
        'Archive Files',
        'venv',
        '__pycache__',
        '.git',
        'node_modules'
    ]

    modified_files = []

    for py_file in repo_root.rglob('*.py'):
        # Skip excluded directories
        if any(excl in str(py_file) for excl in exclude_patterns):
            continue

        if fix_double_imports_in_file(py_file):
            modified_files.append(py_file)
            print(f"Fixed double imports in: {py_file}")

    print(f"\nDouble import fixes completed. Modified {len(modified_files)} files.")

if __name__ == '__main__':
    main()

