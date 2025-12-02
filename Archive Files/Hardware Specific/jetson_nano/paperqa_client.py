#!/usr/bin/env python3
"""
Lightweight PaperQA Client for Jetson Nano
===========================================

IMPORTANT: This is a CLIENT-ONLY implementation.
- Jetson Nanos do NOT have PaperQA installed
- Jetson Nanos do NOT have access to the PaperQA program
- This client only makes HTTP requests to ORKASTRATOR server
- All evidence search happens on the main ORKASTRATOR server
- Only dependency: requests library (no ML/AI libraries)

Usage:
    from paperqa_client import PaperQAClient
    
    client = PaperQAClient(server_url='http://orka-host:5001')
    result = client.search("What is machine learning?")
    print(result['answer'])
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


def main():
    """CLI interface for PaperQA client."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Lightweight PaperQA client for Jetson Nano',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Search for information
  python3 paperqa_client.py search "What is machine learning?"
  
  # Get evidence for a claim
  python3 paperqa_client.py evidence "Machine learning improves accuracy"
  
  # Use specific sources
  python3 paperqa_client.py search "neural networks" --sources arxiv semantic_scholar
  
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
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search for evidence')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--sources', nargs='+', help='Sources to use (arxiv, semantic_scholar, etc.)')
    
    # Evidence command
    evidence_parser = subparsers.add_parser('evidence', help='Get evidence for a claim')
    evidence_parser.add_argument('claim', help='Claim to find evidence for')
    evidence_parser.add_argument('--proposal-id', help='Proposal ID for context')
    evidence_parser.add_argument('--sources', nargs='+', help='Sources to use')
    
    # Health command
    health_parser = subparsers.add_parser('health', help='Check server health')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    client = PaperQAClient(server_url=args.server, api_key=args.api_key)
    
    if args.command == 'search':
        result = client.search(args.query, sources=args.sources)
        if result.get('success'):
            print("\n" + "="*60)
            print("ANSWER:")
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
    
    elif args.command == 'health':
        if client.check_health():
            print("✓ ORKASTRATOR server is accessible")
            return 0
        else:
            print("✗ Cannot connect to ORKASTRATOR server")
            print(f"  Server URL: {client.server_url}")
            return 1
    
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())

