#!/usr/bin/env python3
"""
Lightweight PaperQA & Research API Client for Jetson Nano
==========================================================

IMPORTANT: This is a CLIENT-ONLY implementation.
- Jetson Nanos do NOT have PaperQA installed
- Jetson Nanos do NOT have access to the PaperQA program
- This client only makes HTTP requests to ORKASTRATOR server
- All evidence search happens on the main ORKASTRATOR server
- Only dependency: requests library (no ML/AI libraries)

ACCESS RULES:
┌─────────────────────┬─────────────────────┬─────────────────────────────┐
│ Phase               │ Access Method       │ Purpose                     │
├─────────────────────┼─────────────────────┼─────────────────────────────┤
│ Proposal Building   │ Direct Research API │ Freely query databases      │
│ Proposal Submission │ PaperQA Only        │ Evidence must be validated  │
└─────────────────────┴─────────────────────┴─────────────────────────────┘

TWO ACCESS MODES:
1. Direct Research API Mode (research_*): For proposal building - raw database queries
2. PaperQA Mode (search/get_evidence): For proposal submission - validated evidence

Usage:
    from paperqa_client import PaperQAClient
    
    client = PaperQAClient(server_url='http://orka-host:5001')
    
    # =========================================
    # PROPOSAL BUILDING PHASE - Direct access
    # =========================================
    # Researcher AI can freely query databases
    papers = client.research_arxiv("transformer attention mechanism")
    cves = client.research_cve("buffer overflow")
    rfcs = client.research_ietf("TLS 1.3")
    
    # =========================================
    # PROPOSAL SUBMISSION PHASE - Via PaperQA
    # =========================================
    # Evidence claims MUST go through PaperQA for validation
    evidence = client.get_evidence(
        claim="This optimization improves performance by 20%",
        sources=['arxiv', 'semantic_scholar']
    )
    # Include validated evidence in proposal
    proposal['evidence'] = evidence
"""

import requests
import json
from typing import Dict, List, Optional, Any
import os


class PaperQAClient:
    """
    Lightweight HTTP client for ORKASTRATOR's PaperQA evidence search.
    
    SECURITY NOTE: This is a CLIENT-ONLY implementation.
    - Does NOT contain PaperQA code or dependencies
    - Does NOT have access to evidence documents
    - Only makes HTTP requests to ORKASTRATOR server
    - All processing happens on the main server
    - Jetson Nano only receives formatted results
    
    This client connects to the main ORKASTRATOR server to perform
    evidence searches without requiring PaperQA or heavy dependencies
    on the Jetson Nano device.
    """
    
    def __init__(
        self,
        server_url: str = None,
        api_key: Optional[str] = None,
        timeout: float = 30.0
    ):
        """
        Initialize PaperQA client.
        
        Args:
            server_url: ORKASTRATOR server URL (defaults to ORKASTRATOR_URL env var)
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
        """
        self.server_url = server_url or os.environ.get('ORKASTRATOR_URL', 'http://localhost:5001')
        self.api_key = api_key or os.environ.get('ORKASTRATOR_API_KEY')
        self.timeout = timeout
        
        # Ensure server URL doesn't end with /
        if self.server_url.endswith('/'):
            self.server_url = self.server_url[:-1]
    
    def _make_request(
        self,
        endpoint: str,
        method: str = 'POST',
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to ORKASTRATOR server."""
        url = f"{self.server_url}{endpoint}"
        headers = {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        
        try:
            if method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=self.timeout)
            else:
                response = requests.get(url, headers=headers, timeout=self.timeout)
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'Request failed: {str(e)}'
            }
    
    def search(
        self,
        query: str,
        sources: Optional[List[str]] = None,
        max_sources: int = 5
    ) -> Dict[str, Any]:
        """
        Search for evidence using PaperQA.
        
        Args:
            query: Search query string
            sources: Optional list of sources to use (arxiv, semantic_scholar, etc.)
            max_sources: Maximum number of sources to return
        
        Returns:
            Dictionary with 'answer', 'sources', 'success', etc.
        """
        data = {
            'query': query,
            'sources': sources
        }
        
        result = self._make_request('/api/evidence/search', data=data)
        return result
    
    def get_evidence(
        self,
        claim: str,
        proposal_id: Optional[str] = None,
        sources: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get evidence for a specific claim.
        
        Args:
            claim: The claim to find evidence for
            proposal_id: Optional proposal ID for context
            sources: Optional list of sources to use
        
        Returns:
            Dictionary with 'evidence', 'supporting', 'contradicting', 'sources', etc.
        """
        data = {
            'claim': claim,
            'proposal_id': proposal_id,
            'sources': sources
        }
        
        result = self._make_request('/api/evidence/claim', data=data)
        return result
    
    def check_health(self) -> bool:
        """Check if ORKASTRATOR server is accessible."""
        try:
            response = requests.get(
                f"{self.server_url}/api/health",
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
    
    # =========================================================================
    # DIRECT RESEARCH API ACCESS
    # =========================================================================
    # These methods bypass PaperQA and directly query research databases.
    # Use these when you need raw data without AI processing.
    # =========================================================================
    
    def research_status(self) -> Dict[str, Any]:
        """
        Check which research APIs are available on the server.
        
        Returns:
            Dictionary with available sources and their status
        """
        return self._make_request('/api/research/status', method='GET')
    
    def research_search(
        self,
        query: str,
        sources: Optional[List[str]] = None,
        limit_per_source: int = 5
    ) -> Dict[str, Any]:
        """
        Search multiple research APIs simultaneously.
        
        Args:
            query: Search query string
            sources: List of sources to query (arxiv, semantic_scholar, etc.)
                     If None, searches all available sources
            limit_per_source: Maximum results per source (default 5)
        
        Returns:
            Dictionary with results from each source
        """
        params = {'q': query, 'limit': limit_per_source}
        if sources:
            params['sources'] = ','.join(sources)
        
        url = f"{self.server_url}/api/research/search"
        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': f'Request failed: {str(e)}'}
    
    def research_arxiv(
        self,
        query: str,
        limit: int = 10,
        sort_by: str = 'relevance'
    ) -> List[Dict[str, Any]]:
        """
        Search arXiv papers directly.
        
        Args:
            query: Search query
            limit: Maximum number of results
            sort_by: Sort order (relevance, lastUpdatedDate, submittedDate)
        
        Returns:
            List of paper dictionaries with title, abstract, authors, url, etc.
        """
        url = f"{self.server_url}/api/research/arxiv"
        params = {'q': query, 'limit': limit, 'sort_by': sort_by}
        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return data.get('results', [])
        except requests.exceptions.RequestException as e:
            return []
    
    def research_semantic_scholar(
        self,
        query: str,
        limit: int = 10,
        fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search Semantic Scholar papers directly.
        
        Args:
            query: Search query
            limit: Maximum number of results
            fields: Optional list of fields to return
        
        Returns:
            List of paper dictionaries
        """
        url = f"{self.server_url}/api/research/semantic-scholar"
        params = {'q': query, 'limit': limit}
        if fields:
            params['fields'] = ','.join(fields)
        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return data.get('results', [])
        except requests.exceptions.RequestException as e:
            return []
    
    def research_papers_with_code(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search Papers with Code directly.
        
        Args:
            query: Search query
            limit: Maximum number of results
        
        Returns:
            List of paper dictionaries with code repository links
        """
        url = f"{self.server_url}/api/research/papers-with-code"
        params = {'q': query, 'limit': limit}
        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return data.get('results', [])
        except requests.exceptions.RequestException as e:
            return []
    
    def research_cve(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search CVE/NVD vulnerability database directly.
        
        Args:
            query: Search query (CVE ID or keywords)
            limit: Maximum number of results
        
        Returns:
            List of CVE entries with id, description, severity, etc.
        """
        url = f"{self.server_url}/api/research/cve"
        params = {'q': query, 'limit': limit}
        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return data.get('results', [])
        except requests.exceptions.RequestException as e:
            return []
    
    def research_ietf(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search IETF RFCs directly.
        
        Args:
            query: Search query (RFC number or keywords)
            limit: Maximum number of results
        
        Returns:
            List of RFC entries with number, title, abstract, etc.
        """
        url = f"{self.server_url}/api/research/ietf"
        params = {'q': query, 'limit': limit}
        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return data.get('results', [])
        except requests.exceptions.RequestException as e:
            return []
    
    def research_ieee(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search IEEE Xplore directly (requires API key on server).
        
        Args:
            query: Search query
            limit: Maximum number of results
        
        Returns:
            List of IEEE paper entries
        """
        url = f"{self.server_url}/api/research/ieee"
        params = {'q': query, 'limit': limit}
        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return data.get('results', [])
        except requests.exceptions.RequestException as e:
            return []


def main():
    """CLI interface for PaperQA and Research API client."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Lightweight PaperQA & Research API client for Jetson Nano',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
PAPERQA MODE (AI-processed evidence):
  # Search for information with AI processing
  python3 paperqa_client.py search "What is machine learning?"
  
  # Get evidence for a claim
  python3 paperqa_client.py evidence "Machine learning improves accuracy"
  
  # Use specific sources
  python3 paperqa_client.py search "neural networks" --sources arxiv semantic_scholar

DIRECT RESEARCH API MODE (raw database access):
  # Check available research APIs
  python3 paperqa_client.py research-status
  
  # Search multiple databases at once
  python3 paperqa_client.py research "transformer attention" --sources arxiv,semantic_scholar
  
  # Search arXiv directly
  python3 paperqa_client.py arxiv "neural network optimization"
  
  # Search Semantic Scholar directly  
  python3 paperqa_client.py semantic-scholar "deep learning safety"
  
  # Search Papers with Code
  python3 paperqa_client.py papers-with-code "reinforcement learning"
  
  # Search CVE vulnerabilities
  python3 paperqa_client.py cve "buffer overflow"
  
  # Search IETF RFCs
  python3 paperqa_client.py ietf "TLS 1.3"
  
  # Search IEEE Xplore
  python3 paperqa_client.py ieee "quantum computing"

OTHER:
  # Check server health
  python3 paperqa_client.py health
        """
    )
    
    parser.add_argument(
        '--server',
        default=os.environ.get('ORKASTRATOR_URL', 'http://localhost:5001'),
        help='ORKASTRATOR server URL (default: ORKASTRATOR_URL env var)'
    )
    parser.add_argument(
        '--api-key',
        default=os.environ.get('ORKASTRATOR_API_KEY'),
        help='API key for authentication (default: ORKASTRATOR_API_KEY env var)'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # =========================================================================
    # PaperQA Mode Commands (AI-processed)
    # =========================================================================
    
    # Search command (PaperQA)
    search_parser = subparsers.add_parser('search', help='Search with AI processing (PaperQA)')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--sources', nargs='+', help='Sources to use (arxiv, semantic_scholar, etc.)')
    
    # Evidence command (PaperQA)
    evidence_parser = subparsers.add_parser('evidence', help='Get evidence for a claim (PaperQA)')
    evidence_parser.add_argument('claim', help='Claim to find evidence for')
    evidence_parser.add_argument('--proposal-id', help='Proposal ID for context')
    evidence_parser.add_argument('--sources', nargs='+', help='Sources to use')
    
    # =========================================================================
    # Direct Research API Commands (raw database access)
    # =========================================================================
    
    # Research status
    status_parser = subparsers.add_parser('research-status', help='Check available research APIs')
    
    # Multi-source research search
    research_parser = subparsers.add_parser('research', help='Search multiple databases directly')
    research_parser.add_argument('query', help='Search query')
    research_parser.add_argument('--sources', help='Comma-separated sources (arxiv,semantic_scholar,cve,etc.)')
    research_parser.add_argument('--limit', type=int, default=5, help='Results per source (default: 5)')
    
    # arXiv
    arxiv_parser = subparsers.add_parser('arxiv', help='Search arXiv papers directly')
    arxiv_parser.add_argument('query', help='Search query')
    arxiv_parser.add_argument('--limit', type=int, default=10, help='Max results (default: 10)')
    arxiv_parser.add_argument('--sort', choices=['relevance', 'lastUpdatedDate', 'submittedDate'], 
                              default='relevance', help='Sort order')
    
    # Semantic Scholar
    ss_parser = subparsers.add_parser('semantic-scholar', help='Search Semantic Scholar directly')
    ss_parser.add_argument('query', help='Search query')
    ss_parser.add_argument('--limit', type=int, default=10, help='Max results (default: 10)')
    
    # Papers with Code
    pwc_parser = subparsers.add_parser('papers-with-code', help='Search Papers with Code directly')
    pwc_parser.add_argument('query', help='Search query')
    pwc_parser.add_argument('--limit', type=int, default=10, help='Max results (default: 10)')
    
    # CVE
    cve_parser = subparsers.add_parser('cve', help='Search CVE/NVD vulnerabilities directly')
    cve_parser.add_argument('query', help='CVE ID or keywords')
    cve_parser.add_argument('--limit', type=int, default=10, help='Max results (default: 10)')
    
    # IETF
    ietf_parser = subparsers.add_parser('ietf', help='Search IETF RFCs directly')
    ietf_parser.add_argument('query', help='RFC number or keywords')
    ietf_parser.add_argument('--limit', type=int, default=10, help='Max results (default: 10)')
    
    # IEEE
    ieee_parser = subparsers.add_parser('ieee', help='Search IEEE Xplore directly')
    ieee_parser.add_argument('query', help='Search query')
    ieee_parser.add_argument('--limit', type=int, default=10, help='Max results (default: 10)')
    
    # =========================================================================
    # Other Commands
    # =========================================================================
    
    # Health command
    health_parser = subparsers.add_parser('health', help='Check server health')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    client = PaperQAClient(server_url=args.server, api_key=args.api_key)
    
    # =========================================================================
    # PaperQA Mode Handlers
    # =========================================================================
    
    if args.command == 'search':
        result = client.search(args.query, sources=args.sources)
        if result.get('success'):
            print("\n" + "="*60)
            print("ANSWER (AI-processed):")
            print("="*60)
            print(result.get('formatted_answer', result.get('answer', 'No answer')))
            
            if result.get('sources'):
                print("\n" + "="*60)
                print(f"SOURCES ({len(result['sources'])}):")
                print("="*60)
                for i, source in enumerate(result['sources'], 1):
                    print(f"\n{i}. {source.get('name', 'Unknown')}")
                    print(f"   {source.get('text', '')[:200]}...")
                    if source.get('score'):
                        print(f"   Relevance: {source['score']*100:.1f}%")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
            return 1
    
    elif args.command == 'evidence':
        result = client.get_evidence(
            args.claim,
            proposal_id=args.proposal_id,
            sources=args.sources
        )
        if result.get('success'):
            print("\n" + "="*60)
            print(f"EVIDENCE FOR: {result.get('claim', args.claim)}")
            print("="*60)
            
            if result.get('supporting'):
                print("✓ Supporting evidence found")
            if result.get('contradicting'):
                print("✗ Contradicting evidence found")
            
            print("\n" + result.get('evidence', 'No evidence found'))
            
            if result.get('sources'):
                print("\n" + "="*60)
                print(f"SOURCES ({len(result['sources'])}):")
                print("="*60)
                for i, source in enumerate(result['sources'], 1):
                    print(f"\n{i}. {source.get('name', 'Unknown')}")
                    print(f"   {source.get('text', '')[:200]}...")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
            return 1
    
    # =========================================================================
    # Direct Research API Handlers
    # =========================================================================
    
    elif args.command == 'research-status':
        result = client.research_status()
        if result.get('error'):
            print(f"Error: {result.get('error')}")
            return 1
        print("\n" + "="*60)
        print("AVAILABLE RESEARCH APIs:")
        print("="*60)
        for source, status in result.items():
            if source != 'error':
                icon = "✓" if status else "✗"
                print(f"  {icon} {source}")
    
    elif args.command == 'research':
        sources = args.sources.split(',') if args.sources else None
        result = client.research_search(args.query, sources=sources, limit_per_source=args.limit)
        if result.get('error'):
            print(f"Error: {result.get('error')}")
            return 1
        print("\n" + "="*60)
        print(f"MULTI-SOURCE SEARCH: {args.query}")
        print("="*60)
        for source, items in result.items():
            if source not in ['error', 'success'] and items:
                print(f"\n--- {source.upper()} ({len(items)} results) ---")
                for i, item in enumerate(items[:5], 1):
                    title = item.get('title', item.get('name', 'Unknown'))
                    print(f"  {i}. {title[:70]}...")
    
    elif args.command == 'arxiv':
        results = client.research_arxiv(args.query, limit=args.limit, sort_by=args.sort)
        _print_research_results('arXiv', results, args.query)
    
    elif args.command == 'semantic-scholar':
        results = client.research_semantic_scholar(args.query, limit=args.limit)
        _print_research_results('Semantic Scholar', results, args.query)
    
    elif args.command == 'papers-with-code':
        results = client.research_papers_with_code(args.query, limit=args.limit)
        _print_research_results('Papers with Code', results, args.query)
    
    elif args.command == 'cve':
        results = client.research_cve(args.query, limit=args.limit)
        _print_research_results('CVE/NVD', results, args.query, is_cve=True)
    
    elif args.command == 'ietf':
        results = client.research_ietf(args.query, limit=args.limit)
        _print_research_results('IETF RFCs', results, args.query)
    
    elif args.command == 'ieee':
        results = client.research_ieee(args.query, limit=args.limit)
        _print_research_results('IEEE Xplore', results, args.query)
    
    # =========================================================================
    # Other Handlers
    # =========================================================================
    
    elif args.command == 'health':
        if client.check_health():
            print("✓ ORKASTRATOR server is accessible")
            return 0
        else:
            print("✗ Cannot connect to ORKASTRATOR server")
            print(f"  Server URL: {client.server_url}")
            return 1
    
    return 0


def _print_research_results(source_name: str, results: List[Dict], query: str, is_cve: bool = False):
    """Helper to print research results in a consistent format."""
    print("\n" + "="*60)
    print(f"{source_name.upper()} RESULTS: {query}")
    print("="*60)
    
    if not results:
        print("  No results found.")
        return
    
    for i, item in enumerate(results, 1):
        if is_cve:
            cve_id = item.get('id', item.get('cve_id', 'Unknown'))
            desc = item.get('description', '')[:100]
            severity = item.get('severity', item.get('cvss_score', 'N/A'))
            print(f"\n{i}. {cve_id}")
            print(f"   Severity: {severity}")
            print(f"   {desc}...")
        else:
            title = item.get('title', item.get('name', 'Unknown'))
            authors = item.get('authors', [])
            if isinstance(authors, list):
                authors = ', '.join(authors[:3])
                if len(item.get('authors', [])) > 3:
                    authors += ' et al.'
            url = item.get('url', item.get('link', ''))
            abstract = item.get('abstract', item.get('summary', ''))[:150]
            
            print(f"\n{i}. {title}")
            if authors:
                print(f"   Authors: {authors}")
            if url:
                print(f"   URL: {url}")
            if abstract:
                print(f"   {abstract}...")


if __name__ == '__main__':
    import sys
    sys.exit(main())

