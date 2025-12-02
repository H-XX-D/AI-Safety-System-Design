#!/usr/bin/env python3
"""
Research Browser CLI
====================

Command-line interface for accessing research resources.
Only allows navigation to whitelisted domains - no API/CLI connections.
"""

import sys
import webbrowser
import argparse
from typing import List, Optional
from urllib.parse import urlparse

# Whitelist of allowed domains (same as browser.html)
ALLOWED_DOMAINS = [
    'arxiv.org',
    'scholar.google.com',
    'semanticscholar.org',
    'paperswithcode.com',
    'cve.mitre.org',
    'nvd.nist.gov',
    'attack.mitre.org',
    'cwe.mitre.org',
    'exploit-db.com',
    'owasp.org',
    'vulners.com',
    'digikey.com',
    'octopart.com',
    'mouser.com',
    'allaboutcircuits.com',
    'electronics-tutorials.ws',
    'analog.com',
    'ti.com',
    'maximintegrated.com',
    'st.com',
    'nxp.com',
    'microchip.com',
    'arm.com',
    'intel.com',
    'raspberrypi.org',
    'arduino.cc',
    'sparkfun.com',
    'kicad.org',
    'altium.com',
    'cadence.com',
    'synopsys.com',
    'mentor.com',
    'docs.nvidia.com',
    'developer.nvidia.com',
    'github.com',
    'stackoverflow.com',
    'ieee.org',
    'ieeexplore.ieee.org',
    'ietf.org',
    'datatracker.ietf.org',
    'iso.org',
    'itu.int',
    '3gpp.org',
    'ansi.org',
    'nist.gov',
    'sei.cmu.edu',
    'archimate.org',
    'opengroup.org',
    'omg.org',
    'isa.org',
    'incose.org',
    'wolframalpha.com',
    'wolfram.com',
    'colab.research.google.com',
    'kaggle.com',
    'lesswrong.com',
    'alignmentforum.org',
    'distill.pub',
    'researchgate.net',
    'academia.edu',
    'pubmed.ncbi.nlm.nih.gov',
    'dl.acm.org',
    'computer.org',
    'deepmind.com',
    'openai.com',
    'anthropic.com'
]

# Quick access shortcuts
SHORTCUTS = {
    'arxiv': 'https://arxiv.org/list/cs.AI/recent',
    'scholar': 'https://scholar.google.com',
    'semantic': 'https://www.semanticscholar.org',
    'papers': 'https://paperswithcode.com',
    'cve': 'https://cve.mitre.org',
    'nvd': 'https://nvd.nist.gov',
    'attack': 'https://attack.mitre.org',
    'digikey': 'https://www.digikey.com',
    'octopart': 'https://www.octopart.com',
    'ieee': 'https://www.ieee.org',
    'ietf': 'https://www.ietf.org',
    'iso': 'https://www.iso.org',
    'nvidia': 'https://docs.nvidia.com',
    'github': 'https://github.com',
    'stackoverflow': 'https://stackoverflow.com',
    'wolfram': 'https://www.wolframalpha.com',
    'kaggle': 'https://www.kaggle.com',
}


def is_url_allowed(url: str) -> bool:
    """Check if URL is in the whitelist."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ''
        hostname = hostname.replace('www.', '')
        
        # Check if domain is in whitelist
        for allowed in ALLOWED_DOMAINS:
            if hostname == allowed or hostname.endswith('.' + allowed):
                return True
        
        return False
    except Exception:
        return False


def normalize_url(url: str) -> str:
    """Normalize URL - add protocol if missing."""
    if not url.startswith('http://') and not url.startswith('https://'):
        url = 'https://' + url
    return url


def open_url(url: str, dry_run: bool = False) -> bool:
    """Open URL in default browser if allowed."""
    url = normalize_url(url)
    
    if not is_url_allowed(url):
        print(f"❌ ERROR: URL '{url}' is not in the allowed research resources whitelist.")
        print("   Only research database sites can be accessed.")
        print("   Use 'research-browser list' to see available sites.")
        return False
    
    if dry_run:
        print(f"✓ Would open: {url}")
        return True
    
    print(f"🌐 Opening: {url}")
    webbrowser.open(url)
    return True


def list_resources():
    """List all available research resources."""
    print("\n📚 Available Research Resources\n")
    print("=" * 60)
    
    categories = {
        'Academic': [
            ('arxiv', 'arXiv AI Papers'),
            ('scholar', 'Google Scholar'),
            ('semantic', 'Semantic Scholar'),
            ('papers', 'Papers with Code'),
        ],
        'Security': [
            ('cve', 'CVE Database'),
            ('nvd', 'NVD (National Vulnerability Database)'),
            ('attack', 'MITRE ATT&CK Framework'),
        ],
        'Electronics': [
            ('digikey', 'Digi-Key Electronics'),
            ('octopart', 'Octopart Component Search'),
        ],
        'Standards': [
            ('ieee', 'IEEE'),
            ('ietf', 'IETF RFCs'),
            ('iso', 'ISO/IEC Standards'),
        ],
        'Developer': [
            ('nvidia', 'NVIDIA Documentation'),
            ('github', 'GitHub'),
            ('stackoverflow', 'Stack Overflow'),
        ],
        'Tools': [
            ('wolfram', 'Wolfram Alpha'),
            ('kaggle', 'Kaggle'),
        ],
    }
    
    for category, resources in categories.items():
        print(f"\n{category}:")
        print("-" * 60)
        for shortcut, description in resources:
            print(f"  {shortcut:15} - {description}")
    
    print("\n" + "=" * 60)
    print("\nUsage:")
    print("  research-browser open <shortcut>  - Open a resource")
    print("  research-browser open <url>        - Open a URL (if whitelisted)")
    print("  research-browser list             - List all resources")
    print("  research-browser check <url>      - Check if URL is allowed")


def check_url(url: str):
    """Check if a URL is allowed."""
    url = normalize_url(url)
    allowed = is_url_allowed(url)
    
    if allowed:
        print(f"✓ URL '{url}' is ALLOWED")
        print("  This URL is in the research resources whitelist.")
    else:
        print(f"❌ URL '{url}' is NOT ALLOWED")
        print("  This URL is not in the research resources whitelist.")
        print("  Only research database sites can be accessed.")


def main():
    parser = argparse.ArgumentParser(
        description='Restricted Research Browser CLI - Only allows whitelisted research resource sites',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  research-browser open arxiv          # Open arXiv using shortcut
  research-browser open scholar        # Open Google Scholar
  research-browser open https://arxiv.org/list/cs.AI/recent  # Open full URL
  research-browser list                # List all available resources
  research-browser check https://example.com  # Check if URL is allowed

Note: This CLI only opens URLs in your default browser. It does NOT provide
API or CLI access to these sites. All navigation is restricted to whitelisted
research resource domains only.
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Open command
    open_parser = subparsers.add_parser('open', help='Open a research resource')
    open_parser.add_argument('target', help='Shortcut name or URL to open')
    open_parser.add_argument('--dry-run', action='store_true', help='Show what would be opened without opening')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List all available research resources')
    
    # Check command
    check_parser = subparsers.add_parser('check', help='Check if a URL is allowed')
    check_parser.add_argument('url', help='URL to check')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    if args.command == 'open':
        target = args.target
        
        # Check if it's a shortcut
        if target in SHORTCUTS:
            url = SHORTCUTS[target]
            success = open_url(url, dry_run=args.dry_run)
            return 0 if success else 1
        else:
            # Treat as URL
            success = open_url(target, dry_run=args.dry_run)
            return 0 if success else 1
    
    elif args.command == 'list':
        list_resources()
        return 0
    
    elif args.command == 'check':
        check_url(args.url)
        return 0
    
    return 1


if __name__ == '__main__':
    sys.exit(main())


