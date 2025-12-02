"""
Research API Integrations
==========================

Integrates external research databases and APIs with PaperQA.
"""

import os
import json
import requests
from typing import List, Dict, Optional, Any
from pathlib import Path
import tempfile
import logging

logger = logging.getLogger(__name__)


class ArxivAPI:
    """arXiv API integration"""
    
    @staticmethod
    def search(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search arXiv for papers."""
        try:
            import arxiv
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance
            )
            results = []
            for paper in search.results():
                results.append({
                    'title': paper.title,
                    'authors': [str(a) for a in paper.authors],
                    'summary': paper.summary,
                    'published': str(paper.published),
                    'pdf_url': paper.pdf_url,
                    'entry_id': paper.entry_id,
                    'source': 'arXiv'
                })
            return results
        except ImportError:
            logger.warning("arxiv package not installed. Install with: pip install arxiv")
            return []
        except Exception as e:
            logger.error(f"arXiv search error: {e}")
            return []


class SemanticScholarAPI:
    """Semantic Scholar API integration"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('SEMANTIC_SCHOLAR_API_KEY')
        self.base_url = "https://api.semanticscholar.org/graph/v1"
    
    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search Semantic Scholar."""
        try:
            headers = {}
            if self.api_key:
                headers['x-api-key'] = self.api_key
            
            params = {
                'query': query,
                'limit': limit,
                'fields': 'title,authors,abstract,url,year,citationCount'
            }
            
            response = requests.get(
                f"{self.base_url}/paper/search",
                params=params,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                results = []
                for paper in data.get('data', []):
                    results.append({
                        'title': paper.get('title', ''),
                        'authors': [a.get('name', '') for a in paper.get('authors', [])],
                        'abstract': paper.get('abstract', ''),
                        'url': paper.get('url', ''),
                        'year': paper.get('year'),
                        'citations': paper.get('citationCount', 0),
                        'source': 'Semantic Scholar'
                    })
                return results
            else:
                logger.warning(f"Semantic Scholar API error: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Semantic Scholar search error: {e}")
            return []


class CVEAPI:
    """CVE/NVD API integration"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('NVD_API_KEY')
        self.base_url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    
    def search(self, keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search CVE database."""
        try:
            headers = {}
            if self.api_key:
                headers['apiKey'] = self.api_key
            
            # NVD API uses keyword search
            params = {
                'keywordSearch': keyword,
                'resultsPerPage': min(limit, 20)  # NVD limit
            }
            
            response = requests.get(
                self.base_url,
                params=params,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                results = []
                for vuln in data.get('vulnerabilities', [])[:limit]:
                    cve_data = vuln.get('cve', {})
                    results.append({
                        'id': cve_data.get('id', ''),
                        'description': cve_data.get('descriptions', [{}])[0].get('value', ''),
                        'published': cve_data.get('published', ''),
                        'severity': self._extract_severity(cve_data),
                        'source': 'NVD/CVE'
                    })
                return results
            else:
                logger.warning(f"NVD API error: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"CVE search error: {e}")
            return []
    
    def _extract_severity(self, cve_data: Dict) -> str:
        """Extract CVSS severity."""
        metrics = cve_data.get('metrics', {})
        if 'cvssMetricV31' in metrics:
            return metrics['cvssMetricV31'][0].get('cvssData', {}).get('baseSeverity', 'UNKNOWN')
        elif 'cvssMetricV30' in metrics:
            return metrics['cvssMetricV30'][0].get('cvssData', {}).get('baseSeverity', 'UNKNOWN')
        elif 'cvssMetricV2' in metrics:
            return metrics['cvssMetricV2'][0].get('baseSeverity', 'UNKNOWN')
        return 'UNKNOWN'


class PapersWithCodeAPI:
    """Papers with Code API integration"""
    
    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search Papers with Code."""
        try:
            # Papers with Code has a public API
            params = {
                'q': query,
                'items_per_page': limit
            }
            
            response = requests.get(
                "https://paperswithcode.com/api/v1/papers/",
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                results = []
                for paper in data.get('results', [])[:limit]:
                    results.append({
                        'title': paper.get('title', ''),
                        'authors': paper.get('authors', []),
                        'abstract': paper.get('abstract', ''),
                        'url': paper.get('url', ''),
                        'arxiv_id': paper.get('arxiv_id'),
                        'source': 'Papers with Code'
                    })
                return results
            else:
                logger.warning(f"Papers with Code API error: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Papers with Code search error: {e}")
            return []


class IETFAPI:
    """IETF RFC/Datatracker API integration"""
    
    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search IETF RFCs and internet drafts."""
        try:
            # IETF Datatracker API
            params = {
                'name': query,
                'limit': limit,
                'format': 'json'
            }
            
            response = requests.get(
                "https://datatracker.ietf.org/api/v1/doc/document/",
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                results = []
                for doc in data.get('objects', [])[:limit]:
                    results.append({
                        'title': doc.get('title', ''),
                        'rfc_number': doc.get('rfc', ''),
                        'authors': [a.get('name', '') for a in doc.get('authors', [])],
                        'abstract': doc.get('abstract', '')[:500],
                        'url': f"https://datatracker.ietf.org/doc/html/{doc.get('name', '')}",
                        'published': doc.get('time', ''),
                        'source': 'IETF RFC'
                    })
                return results
            else:
                logger.warning(f"IETF API error: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"IETF search error: {e}")
            return []


class DigiKeyAPI:
    """Digi-Key Electronics API integration"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('DIGIKEY_API_KEY')
        self.base_url = "https://api.digikey.com"
    
    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search Digi-Key component database."""
        try:
            if not self.api_key:
                logger.warning("Digi-Key API key not configured")
                return []
            
            headers = {
                'X-DIGIKEY-Client-Id': self.api_key,
                'Content-Type': 'application/json'
            }
            
            params = {
                'Keywords': query,
                'RecordCount': min(limit, 20)
            }
            
            response = requests.get(
                f"{self.base_url}/Search/v3/Products/Keyword",
                params=params,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                results = []
                for product in data.get('Products', [])[:limit]:
                    results.append({
                        'title': product.get('ProductDescription', ''),
                        'part_number': product.get('DigiKeyPartNumber', ''),
                        'manufacturer': product.get('Manufacturer', ''),
                        'category': product.get('ProductCategory', {}).get('Value', ''),
                        'url': product.get('ProductUrl', ''),
                        'source': 'Digi-Key'
                    })
                return results
            else:
                logger.warning(f"Digi-Key API error: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Digi-Key search error: {e}")
            return []


class OctopartAPI:
    """Octopart component search API integration"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('OCTOPART_API_KEY')
        self.base_url = "https://octopart.com/api/v4"
    
    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search Octopart component database."""
        try:
            if not self.api_key:
                logger.warning("Octopart API key not configured")
                return []
            
            params = {
                'apikey': self.api_key,
                'q': query,
                'limit': min(limit, 20)
            }
            
            response = requests.get(
                f"{self.base_url}/parts/search",
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                results = []
                for part in data.get('results', [])[:limit]:
                    results.append({
                        'title': part.get('item', {}).get('mpn', ''),
                        'part_number': part.get('item', {}).get('mpn', ''),
                        'manufacturer': part.get('item', {}).get('manufacturer', {}).get('name', ''),
                        'description': part.get('snippet', ''),
                        'url': part.get('item', {}).get('octopart_url', ''),
                        'source': 'Octopart'
                    })
                return results
            else:
                logger.warning(f"Octopart API error: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Octopart search error: {e}")
            return []


class IEEEAPI:
    """IEEE Xplore API integration"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('IEEE_API_KEY')
        self.base_url = "http://ieeexploreapi.ieee.org/api/v1"
    
    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search IEEE Xplore database."""
        try:
            if not self.api_key:
                logger.warning("IEEE API key not configured (subscription required)")
                return []
            
            params = {
                'apikey': self.api_key,
                'querytext': query,
                'max_records': min(limit, 25),
                'format': 'json'
            }
            
            response = requests.get(
                f"{self.base_url}/search/articles",
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                results = []
                for article in data.get('articles', [])[:limit]:
                    results.append({
                        'title': article.get('title', ''),
                        'authors': [a.get('full_name', '') for a in article.get('authors', {}).get('authors', [])],
                        'abstract': article.get('abstract', ''),
                        'publication': article.get('publication_title', ''),
                        'year': article.get('publication_year', ''),
                        'url': article.get('html_url', ''),
                        'source': 'IEEE Xplore'
                    })
                return results
            else:
                logger.warning(f"IEEE API error: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"IEEE search error: {e}")
            return []


class USPTOAPI:
    """Placeholder USPTO patent search API integration."""

    def __init__(self):
        self.base_url = os.environ.get('USPTO_API_URL', 'https://developer.uspto.gov/ds-api')

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Return empty results with a warning until USPTO integration is configured."""
        logger.warning("USPTO API integration not configured; returning no results.")
        return []


class GooglePatentsAPI:
    """Placeholder Google Patents integration."""

    def __init__(self):
        self.base_url = os.environ.get('GOOGLE_PATENTS_API_URL', 'https://patents.google.com')

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        logger.warning("Google Patents API integration not configured; returning no results.")
        return []


class EPOAPI:
    """Placeholder European Patent Office search integration."""

    def __init__(self):
        self.base_url = os.environ.get('EPO_API_URL', 'https://ops.epo.org')

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        logger.warning("EPO API integration not configured; returning no results.")
        return []


class WIPOAPI:
    """Placeholder World Intellectual Property Organization search integration."""

    def __init__(self):
        self.base_url = os.environ.get('WIPO_API_URL', 'https://patentscope.wipo.int')

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        logger.warning("WIPO API integration not configured; returning no results.")
        return []


class ResearchAPIManager:
    """Manages multiple research API integrations"""
    
    def __init__(self):
        self.arxiv = ArxivAPI()
        self.semantic_scholar = SemanticScholarAPI()
        self.cve = CVEAPI()
        self.papers_with_code = PapersWithCodeAPI()
        self.ietf = IETFAPI()
        self.digikey = DigiKeyAPI()
        self.octopart = OctopartAPI()
        self.ieee = IEEEAPI()
        self.uspto = USPTOAPI()
        self.google_patents = GooglePatentsAPI()
        self.epo = EPOAPI()
        self.wipo = WIPOAPI()
    
    def search_all(self, query: str, sources: Optional[List[str]] = None, limit_per_source: int = 5) -> List[Dict[str, Any]]:
        """Search across all enabled APIs."""
        if sources is None:
            sources = ['arxiv', 'semantic_scholar', 'papers_with_code']
        
        all_results = []
        
        if 'arxiv' in sources:
            arxiv_results = self.arxiv.search(query, limit_per_source)
            all_results.extend(arxiv_results)
        
        if 'semantic_scholar' in sources:
            scholar_results = self.semantic_scholar.search(query, limit_per_source)
            all_results.extend(scholar_results)
        
        if 'papers_with_code' in sources:
            pwc_results = self.papers_with_code.search(query, limit_per_source)
            all_results.extend(pwc_results)
        
        if 'cve' in sources:
            cve_results = self.cve.search(query, limit_per_source)
            all_results.extend(cve_results)
        
        if 'ietf' in sources:
            ietf_results = self.ietf.search(query, limit_per_source)
            all_results.extend(ietf_results)
        
        if 'digikey' in sources:
            digikey_results = self.digikey.search(query, limit_per_source)
            all_results.extend(digikey_results)
        
        if 'octopart' in sources:
            octopart_results = self.octopart.search(query, limit_per_source)
            all_results.extend(octopart_results)
        
        if 'ieee' in sources:
            ieee_results = self.ieee.search(query, limit_per_source)
            all_results.extend(ieee_results)
        
        if 'uspto' in sources:
            uspto_results = self.uspto.search(query, limit_per_source)
            all_results.extend(uspto_results)
        
        if 'google_patents' in sources:
            google_patents_results = self.google_patents.search(query, limit_per_source)
            all_results.extend(google_patents_results)
        
        if 'epo' in sources:
            epo_results = self.epo.search(query, limit_per_source)
            all_results.extend(epo_results)
        
        if 'wipo' in sources:
            wipo_results = self.wipo.search(query, limit_per_source)
            all_results.extend(wipo_results)
        
        return all_results
    
    def format_for_paperqa(self, results: List[Dict[str, Any]]) -> List[str]:
        """Format API results as text documents for PaperQA."""
        formatted = []
        for result in results:
            doc_parts = []
            
            # Title or ID
            if result.get('title'):
                doc_parts.append(f"Title: {result['title']}")
            elif result.get('id'):
                doc_parts.append(f"ID: {result['id']}")
            elif result.get('part_number'):
                doc_parts.append(f"Part Number: {result['part_number']}")
            
            # Authors
            if result.get('authors'):
                authors = ', '.join(result['authors'][:5])  # Limit authors
                doc_parts.append(f"Authors: {authors}")
            
            # Inventors (for patents)
            if result.get('inventors'):
                inventors = ', '.join(result['inventors'][:5])
                doc_parts.append(f"Inventors: {inventors}")
            
            # Assignees (for patents)
            if result.get('assignees'):
                assignees = ', '.join(result['assignees'][:3])
                doc_parts.append(f"Assignees: {assignees}")
            
            # Patent Number
            if result.get('patent_number'):
                doc_parts.append(f"Patent Number: {result['patent_number']}")
            
            # Manufacturer (for electronics)
            if result.get('manufacturer'):
                doc_parts.append(f"Manufacturer: {result['manufacturer']}")
            
            # Abstract/Summary/Description
            if result.get('abstract'):
                doc_parts.append(f"Abstract: {result['abstract']}")
            elif result.get('summary'):
                doc_parts.append(f"Summary: {result['summary']}")
            elif result.get('description'):
                doc_parts.append(f"Description: {result['description']}")
            
            # Additional fields
            if result.get('severity'):
                doc_parts.append(f"Severity: {result['severity']}")
            
            if result.get('category'):
                doc_parts.append(f"Category: {result['category']}")
            
            if result.get('publication'):
                doc_parts.append(f"Publication: {result['publication']}")
            
            if result.get('rfc_number'):
                doc_parts.append(f"RFC Number: {result['rfc_number']}")
            
            if result.get('citations'):
                doc_parts.append(f"Citations: {result['citations']}")
            
            if result.get('published') or result.get('year'):
                pub_date = result.get('published') or result.get('year')
                doc_parts.append(f"Published: {pub_date}")
            
            if result.get('source'):
                doc_parts.append(f"Source: {result['source']}")
            
            if result.get('url'):
                doc_parts.append(f"URL: {result['url']}")
            
            if doc_parts:
                formatted.append('\n\n'.join(doc_parts))
        
        return formatted
    
    async def add_to_paperqa(self, docs, query: str, sources: Optional[List[str]] = None):
        """Search APIs and add results to PaperQA Docs object."""
        try:
            results = self.search_all(query, sources=sources)
            formatted_docs = self.format_for_paperqa(results)
            
            # Create temporary files for PaperQA
            temp_dir = Path(tempfile.gettempdir()) / 'paperqa_research'
            temp_dir.mkdir(exist_ok=True)
            
            for i, doc_text in enumerate(formatted_docs):
                if doc_text.strip():
                    temp_file = temp_dir / f"research_{i}_{hash(query) % 10000}.txt"
                    temp_file.write_text(doc_text, encoding='utf-8')
                    try:
                        await docs.aadd(str(temp_file))
                    except Exception as e:
                        logger.warning(f"Failed to add research doc to PaperQA: {e}")
            
            return len(formatted_docs)
        except Exception as e:
            logger.error(f"Error adding research to PaperQA: {e}")
            return 0

