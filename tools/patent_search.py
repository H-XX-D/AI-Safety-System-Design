#!/usr/bin/env python3
"""
Patent Search for AI Safety Architecture

Searches patent databases for prior art related to the AI Safety System Design.
Uses local llama.cpp server for processing (no external LLM APIs).
"""

import asyncio
import os
import sys
import json
from pathlib import Path
from datetime import datetime

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Patent search queries for the architecture
PATENT_QUERIES = [
    # Core architecture concepts
    "multi-agent AI system recursive self-improvement safety validation",
    "artificial intelligence deception detection peer review verification",
    "game theoretic incentive alignment AI safety penalty reward",
    "immutable audit log AI decision verification merkle tree",
    "air-gapped hardware translator AI communication security",
    
    # Specific mechanisms
    "dual penalty system AI alignment multiplicative additive",
    "write-once read-many storage AI audit trail WORM",
    "multi-tier validation AI proposal sandbox execution",
    "AI debate engine consensus verification claims",
    "interpretability monitoring AI drift detection",
    
    # Self-improvement concepts
    "safe recursive self-improvement artificial intelligence constraints",
    "AI agent orchestration coordination multi-model system",
    "reinforcement learning self-improvement safety bounds",
]

def search_uspto_patentsview(query: str, limit: int = 10) -> list:
    """Search USPTO via PatentsView API (free, no key needed)."""
    import urllib.request
    import urllib.parse
    
    base_url = "https://api.patentsview.org/patents/query"
    
    # Build query
    params = {
        "q": json.dumps({
            "_text_any": {"patent_abstract": query}
        }),
        "f": json.dumps([
            "patent_number", 
            "patent_title", 
            "patent_abstract",
            "patent_date",
            "inventor_first_name",
            "inventor_last_name"
        ]),
        "o": json.dumps({"per_page": limit})
    }
    
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
            
        results = []
        if data.get("patents"):
            for patent in data["patents"]:
                results.append({
                    "number": patent.get("patent_number"),
                    "title": patent.get("patent_title"),
                    "abstract": patent.get("patent_abstract", "")[:500],
                    "date": patent.get("patent_date"),
                    "source": "USPTO PatentsView"
                })
        return results
    except Exception as e:
        print(f"  USPTO search error: {e}")
        return []


def search_google_patents_via_serpapi(query: str, limit: int = 5) -> list:
    """
    Note: This requires SERPAPI_KEY for Google Patents.
    Falls back to USPTO if not available.
    """
    api_key = os.environ.get("SERPAPI_KEY")
    if not api_key:
        return []  # Skip if no API key
    
    import urllib.request
    import urllib.parse
    
    params = {
        "engine": "google_patents",
        "q": query,
        "api_key": api_key,
        "num": limit
    }
    
    url = f"https://serpapi.com/search?{urllib.parse.urlencode(params)}"
    
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            data = json.loads(response.read().decode())
        
        results = []
        for result in data.get("organic_results", [])[:limit]:
            results.append({
                "number": result.get("patent_id", "N/A"),
                "title": result.get("title", ""),
                "abstract": result.get("snippet", "")[:500],
                "date": result.get("filing_date", ""),
                "source": "Google Patents"
            })
        return results
    except Exception as e:
        print(f"  Google Patents error: {e}")
        return []


def format_results(all_results: dict) -> str:
    """Format all patent search results for display."""
    output = []
    output.append("=" * 80)
    output.append("PATENT SEARCH RESULTS - AI Safety Architecture Prior Art")
    output.append(f"Search Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    output.append("=" * 80)
    
    for query, results in all_results.items():
        output.append(f"\n{'─' * 80}")
        output.append(f"Query: {query}")
        output.append(f"{'─' * 80}")
        
        if not results:
            output.append("  No results found")
            continue
            
        for i, patent in enumerate(results, 1):
            output.append(f"\n  [{i}] {patent['title']}")
            output.append(f"      Patent: {patent['number']}")
            output.append(f"      Date: {patent['date']}")
            output.append(f"      Source: {patent['source']}")
            if patent['abstract']:
                # Truncate abstract for display
                abstract = patent['abstract'][:300]
                if len(patent['abstract']) > 300:
                    abstract += "..."
                output.append(f"      Abstract: {abstract}")
    
    return "\n".join(output)


def main():
    print("\n🔍 Searching Patent Databases for AI Safety Architecture Prior Art...")
    print("   Using: USPTO PatentsView (free API)")
    print("   Queries:", len(PATENT_QUERIES))
    print()
    
    all_results = {}
    
    for i, query in enumerate(PATENT_QUERIES, 1):
        print(f"[{i}/{len(PATENT_QUERIES)}] Searching: {query[:50]}...")
        
        # Search USPTO (free, always available)
        results = search_uspto_patentsview(query, limit=5)
        
        # Also try Google Patents if API key available
        google_results = search_google_patents_via_serpapi(query, limit=3)
        results.extend(google_results)
        
        all_results[query] = results
        print(f"         Found: {len(results)} patents")
    
    # Format and display results
    formatted = format_results(all_results)
    print(formatted)
    
    # Save to file
    output_file = PROJECT_ROOT / "patent_search_results.txt"
    with open(output_file, "w") as f:
        f.write(formatted)
    print(f"\n📁 Results saved to: {output_file}")
    
    # Summary
    total = sum(len(r) for r in all_results.values())
    print(f"\n📊 Summary: Found {total} potentially relevant patents across {len(PATENT_QUERIES)} queries")


if __name__ == "__main__":
    main()





