#!/usr/bin/env bash
set -euo pipefail
# Organize all markdown files into docs/ directory
# Preserves git history by using git mv when possible
# Run with: bash organize_docs.sh

set -e

echo "=== AI Safety System Design - Documentation Organization ==="
echo ""
echo "This will move all root-level .md files into organized docs/ subdirectories:"
echo "  - Assessment files → docs/assessments/"
echo "  - Status/Progress files → docs/status/"
echo "  - Patent files → docs/patent/"
echo "  - Architecture files → docs/architecture/"
echo "  - Guide/Tutorial files → docs/guides/"
echo "  - Main README stays in root"
echo ""
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 1
fi

echo ""
echo "Starting organization..."

# Check if we're in a git repo
IN_GIT=false
if git rev-parse --git-dir > /dev/null 2>&1; then
    IN_GIT=true
    echo "Git repository detected - will use 'git mv' to preserve history"
else
    echo "Not a git repository - will use regular 'mv'"
fi

# Function to move files (git mv if in git, regular mv otherwise)
move_file() {
    local src="$1"
    local dest="$2"

    if [ -f "$src" ]; then
        echo "  Moving: $src → $dest"
        mkdir -p "$(dirname "$dest")"
        if [ "$IN_GIT" = true ]; then
            git mv "$src" "$dest" 2>/dev/null || mv "$src" "$dest"
        else
            mv "$src" "$dest"
        fi
    fi
}

# Create directory structure
echo ""
echo "[1/6] Creating directory structure..."
mkdir -p docs/assessments
mkdir -p docs/status
mkdir -p docs/patent
mkdir -p docs/architecture
mkdir -p docs/guides
mkdir -p docs/misc

# [2/6] Move assessment files
echo "[2/6] Moving assessment files..."
move_file "HONEST_ASSESSMENT.md" "docs/assessments/HONEST_ASSESSMENT.md"
move_file "ANALYSIS_SUMMARY.txt" "docs/assessments/ANALYSIS_SUMMARY.txt"

# [3/6] Move status/progress files
echo "[3/6] Moving status and progress files..."
move_file "SYSTEM_COMPLETION_STATUS.md" "docs/status/SYSTEM_COMPLETION_STATUS.md"
move_file "WEB_UI_COMPLETION_REPORT.md" "docs/status/WEB_UI_COMPLETION_REPORT.md"
move_file "WORM_USB_COMPLETE_SUMMARY.md" "docs/status/WORM_USB_COMPLETE_SUMMARY.md"
move_file "DASHBOARD_TAB_INTERCONNECTION.md" "docs/status/DASHBOARD_TAB_INTERCONNECTION.md"
move_file "GUI_INTERCONNECTION_PROGRESS.md" "docs/status/GUI_INTERCONNECTION_PROGRESS.md"
move_file "INTERACTIVE_NAVIGATION_UPDATE.md" "docs/status/INTERACTIVE_NAVIGATION_UPDATE.md"
move_file "PENALTIES_DETECTION_TABS_COMPLETE.md" "docs/status/PENALTIES_DETECTION_TABS_COMPLETE.md"

# [4/6] Move patent files
echo "[4/6] Moving patent files..."
move_file "PATENT_FILING_CHECKLIST_2025-11-11.md" "docs/patent/PATENT_FILING_CHECKLIST_2025-11-11.md"
move_file "PATENT_UPDATE_COMPLETE.md" "docs/patent/PATENT_UPDATE_COMPLETE.md"
move_file "PATENT_UPDATE_SUMMARY_2025-11-11.md" "docs/patent/PATENT_UPDATE_SUMMARY_2025-11-11.md"
move_file "PATENT_VERIFICATION_REPORT.md" "docs/patent/PATENT_VERIFICATION_REPORT.md"
move_file "PROVISIONAL_PATENT_APPLICATION_UPDATED_2025-11-11.md" "docs/patent/PROVISIONAL_PATENT_APPLICATION_UPDATED_2025-11-11.md"

# [5/6] Move architecture files
echo "[5/6] Moving architecture files..."
move_file "ARCHITECTURE_DIAGRAM.txt" "docs/architecture/ARCHITECTURE_DIAGRAM.txt"
move_file "DEPENDENCY_SUMMARY.txt" "docs/architecture/DEPENDENCY_SUMMARY.txt"

# [6/6] Move miscellaneous docs
echo "[6/6] Moving miscellaneous documentation..."
move_file "README_NEW.md" "docs/misc/README_NEW.md"
move_file "README_COMPARISON.md" "docs/misc/README_COMPARISON.md"

# Move any other root-level .md files (except README.md and CHANGELOG.md)
echo ""
echo "Checking for other root-level .md files..."
for file in *.md; do
    if [ -f "$file" ] && [ "$file" != "README.md" ] && [ "$file" != "CHANGELOG.md" ]; then
        echo "  Found: $file"
        move_file "$file" "docs/misc/$file"
    fi
done

echo ""
echo "✓ Documentation organization complete!"
echo ""
echo "Summary of new structure:"
echo "  📁 docs/"
echo "     ├── assessments/    (assessment and analysis files)"
echo "     ├── status/         (progress and completion reports)"
echo "     ├── patent/         (patent-related documentation)"
echo "     ├── architecture/   (system architecture docs)"
echo "     ├── guides/         (tutorials and guides)"
echo "     └── misc/           (other documentation)"
echo ""
echo "Main README.md and CHANGELOG.md remain in root directory."
echo ""

if [ "$IN_GIT" = true ]; then
    echo "Changes have been staged with 'git mv'."
    echo "Review with: git status"
    echo "Commit with: git commit -m 'Organize documentation into docs/ subdirectories'"
fi
