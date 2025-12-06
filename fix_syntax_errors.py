import os
import re

def fix_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Fix: import security.worm_manifest as worm_manifest
    # Pattern: import A.B as B -> import A.B as B
    # But we need to be careful about "from . import X"
    
    # Case 1: Absolute imports
    # import security.worm_manifest as worm_manifest
    # -> import security.worm_manifest as worm_manifest
    def replace_absolute(match):
        full_module = match.group(1)
        last_part = full_module.split('.')[-1]
        return f"import {full_module} as {last_part}"
    
    content = re.sub(r'from ([\w\.]+) import \1(?!\s*,)', replace_absolute, content)
    
    # Case 2: Relative imports in __init__.py
    # from . import worm_manifest
    # -> from . import worm_manifest
    # We assume the last part of the dotted name matches the module name
    def replace_relative(match):
        module_file = match.group(1)
        full_imported = match.group(2)
        last_part = full_imported.split('.')[-1]
        if module_file == last_part:
             return f"from . import {last_part}"
        return match.group(0) # No change if mismatch

    content = re.sub(r'from \.([\w_]+) import ([\w\.]+)', replace_relative, content)

    # Case 3: Mixed imports in __init__.py (e.g. from . import worm_manifest, verify_integrity)
    # This is harder to regex cleanly if we want to split it.
    # Let's handle specific known broken files manually or with specific regexes if the above didn't catch them.
    
    # Specific fix for security/__init__.py
    if 'security/__init__.py' in filepath:
        content = content.replace('from . import worm_manifest, verify_integrity', 
                                  'from . import worm_manifest\nfrom .worm_manifest import verify_integrity')
    
    # Specific fix for ai_safety/__init__.py
    if 'ai_safety/__init__.py' in filepath:
        content = content.replace('from . import interpretability_monitor',
                                  'from . import interpretability_monitor')

    # Specific fix for core/orchestrator.py and others where "import A.B as A.B" might have happened or similar?
    # The regex Case 1 should handle "import security.worm_manifest as worm_manifest"
    
    # Another pattern seen in grep:
    # import security.worm_manifest as worm_manifest as _wm
    # -> import security.worm_manifest as _wm
    content = re.sub(r'from ([\w\.]+) import \1 as ([\w_]+)', r'import \1 as \2', content)

    if content != original_content:
        print(f"Fixing {filepath}")
        with open(filepath, 'w') as f:
            f.write(content)

def main():
    for root, dirs, files in os.walk('.'):
        if '.venv' in root:
            continue
        for file in files:
            if file.endswith('.py'):
                fix_file(os.path.join(root, file))

if __name__ == '__main__':
    main()
