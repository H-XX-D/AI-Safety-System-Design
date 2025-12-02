# Research Browser CLI

## Overview

A command-line interface for accessing research resources through your default web browser. This CLI only opens URLs - it does NOT provide API or CLI access to external sites. All navigation is restricted to whitelisted research resource domains.

## Installation

No installation required - it's a standalone Python script. Requires Python 3.6+.

## Usage

### Quick Start

```bash
# Open a resource using shortcut
python3 ui/research_browser_cli.py open arxiv

# Open a resource using full URL (if whitelisted)
python3 ui/research_browser_cli.py open https://arxiv.org/list/cs.AI/recent

# List all available resources
python3 ui/research_browser_cli.py list

# Check if a URL is allowed
python3 ui/research_browser_cli.py check https://example.com
```

### Available Shortcuts

**Academic:**
- `arxiv` - arXiv AI Papers
- `scholar` - Google Scholar
- `semantic` - Semantic Scholar
- `papers` - Papers with Code

**Security:**
- `cve` - CVE Database
- `nvd` - NVD (National Vulnerability Database)
- `attack` - MITRE ATT&CK Framework

**Electronics:**
- `digikey` - Digi-Key Electronics
- `octopart` - Octopart Component Search

**Standards:**
- `ieee` - IEEE
- `ietf` - IETF RFCs
- `iso` - ISO/IEC Standards

**Developer:**
- `nvidia` - NVIDIA Documentation
- `github` - GitHub
- `stackoverflow` - Stack Overflow

**Tools:**
- `wolfram` - Wolfram Alpha
- `kaggle` - Kaggle

### Examples

```bash
# Open arXiv
python3 ui/research_browser_cli.py open arxiv

# Open Google Scholar
python3 ui/research_browser_cli.py open scholar

# Open a specific URL (must be whitelisted)
python3 ui/research_browser_cli.py open https://cve.mitre.org

# Check if a URL is allowed
python3 ui/research_browser_cli.py check https://github.com

# Dry run (see what would be opened without opening)
python3 ui/research_browser_cli.py open arxiv --dry-run
```

## Security

- **Whitelist Only**: Only domains in the approved research resources list can be accessed
- **No API Access**: This CLI does NOT provide programmatic API access to sites
- **No CLI Access**: This CLI does NOT provide command-line access to external services
- **Browser Only**: URLs are opened in your default web browser only

## Adding to PATH (Optional)

To use `research-browser` command directly:

```bash
# Add to ~/.bashrc or ~/.zshrc
alias research-browser='python3 /path/to/AI-Safety-System-Design/ui/research_browser_cli.py'

# Then use:
research-browser open arxiv
```

## Integration with System

This CLI complements the web-based Research Browser (`/browser`) by providing command-line access to the same whitelisted resources. Both interfaces enforce the same security restrictions.


