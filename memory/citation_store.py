"""
Citation Store - Lightweight storage for research references.

Since PaperQA handles full document retrieval, we only store:
- Citation metadata (paper ID, title, authors, source)
- Relevant page/section references
- Key quotes or findings (snippets, not full text)
- Query context (why this was retrieved)
- Usage tracking (which proposals used this citation)

PaperQA can retrieve full content on demand using stored citation IDs.
"""

import json
import time
import hashlib
import sqlite3
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
import threading
import logging

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    """A lightweight citation reference."""
    id: str                          # Unique ID for this citation record
    
    # Source identification (for PaperQA retrieval)
    source_type: str                 # 'arxiv', 'semantic_scholar', 'pubmed', 'cve', 'ietf', etc.
    source_id: str                   # arXiv ID, DOI, CVE number, etc.
    
    # Metadata (cached from PaperQA)
    title: str
    authors: List[str]
    year: Optional[int] = None
    venue: Optional[str] = None      # Journal/conference
    url: Optional[str] = None
    
    # Relevant sections (not full text)
    relevant_pages: List[int] = field(default_factory=list)
    relevant_sections: List[str] = field(default_factory=list)  # e.g., ["Abstract", "3.2 Methods"]
    
    # Key snippets (short quotes, not full paragraphs)
    key_quotes: List[Dict[str, Any]] = field(default_factory=list)
    # Each quote: {"text": "...", "page": 5, "section": "Results", "relevance": 0.9}
    
    # Context
    original_query: str = ""         # What query retrieved this
    relevance_score: float = 0.0     # How relevant to the query
    retrieved_at: float = field(default_factory=time.time)
    
    # Usage tracking
    used_in_proposals: List[str] = field(default_factory=list)
    usage_count: int = 0
    last_used: float = 0.0
    
    # Tags for organization
    tags: List[str] = field(default_factory=list)
    domain: str = "general"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Citation':
        return cls(**data)
    
    def to_bibtex(self) -> str:
        """Generate BibTeX entry for this citation."""
        entry_type = "article"
        key = f"{self.authors[0].split()[-1] if self.authors else 'unknown'}{self.year or 'nd'}"
        
        lines = [f"@{entry_type}{{{key},"]
        lines.append(f"  title = {{{self.title}}},")
        if self.authors:
            lines.append(f"  author = {{{' and '.join(self.authors)}}},")
        if self.year:
            lines.append(f"  year = {{{self.year}}},")
        if self.venue:
            lines.append(f"  journal = {{{self.venue}}},")
        if self.url:
            lines.append(f"  url = {{{self.url}}},")
        lines.append("}")
        
        return "\n".join(lines)
    
    def to_apa(self) -> str:
        """Generate APA-style citation string."""
        author_str = ", ".join(self.authors[:3]) if self.authors else "Unknown"
        if len(self.authors) > 3:
            author_str += " et al."
        
        year_str = f"({self.year})" if self.year else "(n.d.)"
        
        return f"{author_str} {year_str}. {self.title}."
    
    def get_retrieval_key(self) -> str:
        """Get the key for retrieving full content from PaperQA."""
        return f"{self.source_type}:{self.source_id}"


@dataclass
class CitationBundle:
    """A bundle of related citations for a specific topic/proposal."""
    id: str
    topic: str
    query: str
    citations: List[str]  # Citation IDs
    created_at: float
    proposal_id: Optional[str] = None
    summary: str = ""  # Brief summary of what these citations support
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CitationBundle':
        return cls(**data)


class CitationStore:
    """
    Lightweight citation storage with PaperQA integration.
    
    Stores only metadata and references - full content retrieved via PaperQA.
    
    Features:
    - Deduplication by source ID
    - Usage tracking across proposals
    - Quick lookup by source, topic, or query
    - Citation bundles for proposals
    - Export to BibTeX/APA
    """
    
    def __init__(
        self,
        data_dir: str = "./data/citations",
        paperqa_client=None,  # Optional PaperQA client for on-demand retrieval
        max_quote_length: int = 500,  # Max chars per quote
        max_quotes_per_citation: int = 5
    ):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = self.data_dir / "citations.db"
        self.paperqa = paperqa_client
        self.max_quote_length = max_quote_length
        self.max_quotes_per_citation = max_quotes_per_citation
        
        self._lock = threading.RLock()
        self._init_database()
        
        # In-memory cache for frequent lookups
        self._source_to_id: Dict[str, str] = {}  # "arxiv:2301.00001" -> citation_id
        self._load_source_index()
    
    def _init_database(self) -> None:
        """Initialize SQLite database."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executescript("""
                -- Citations table
                CREATE TABLE IF NOT EXISTS citations (
                    id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    authors TEXT DEFAULT '[]',
                    year INTEGER,
                    venue TEXT,
                    url TEXT,
                    relevant_pages TEXT DEFAULT '[]',
                    relevant_sections TEXT DEFAULT '[]',
                    key_quotes TEXT DEFAULT '[]',
                    original_query TEXT,
                    relevance_score REAL DEFAULT 0.0,
                    retrieved_at REAL NOT NULL,
                    used_in_proposals TEXT DEFAULT '[]',
                    usage_count INTEGER DEFAULT 0,
                    last_used REAL DEFAULT 0.0,
                    tags TEXT DEFAULT '[]',
                    domain TEXT DEFAULT 'general',
                    UNIQUE(source_type, source_id)
                );
                
                -- Citation bundles
                CREATE TABLE IF NOT EXISTS bundles (
                    id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    query TEXT NOT NULL,
                    citations TEXT DEFAULT '[]',
                    created_at REAL NOT NULL,
                    proposal_id TEXT,
                    summary TEXT DEFAULT ''
                );
                
                -- Indexes
                CREATE INDEX IF NOT EXISTS idx_citations_source ON citations(source_type, source_id);
                CREATE INDEX IF NOT EXISTS idx_citations_domain ON citations(domain);
                CREATE INDEX IF NOT EXISTS idx_citations_usage ON citations(usage_count DESC);
                CREATE INDEX IF NOT EXISTS idx_bundles_proposal ON bundles(proposal_id);
            """)
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _load_source_index(self) -> None:
        """Load source -> ID mapping into memory."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT id, source_type, source_id FROM citations").fetchall()
            for row in rows:
                key = f"{row['source_type']}:{row['source_id']}"
                self._source_to_id[key] = row['id']
    
    def _generate_id(self, source_type: str, source_id: str) -> str:
        """Generate unique citation ID."""
        return hashlib.sha256(f"{source_type}:{source_id}".encode()).hexdigest()[:16]
    
    # ========== Citation Operations ==========
    
    def add_citation(
        self,
        source_type: str,
        source_id: str,
        title: str,
        authors: List[str],
        year: Optional[int] = None,
        venue: Optional[str] = None,
        url: Optional[str] = None,
        relevant_pages: Optional[List[int]] = None,
        relevant_sections: Optional[List[str]] = None,
        key_quotes: Optional[List[Dict[str, Any]]] = None,
        original_query: str = "",
        relevance_score: float = 0.0,
        tags: Optional[List[str]] = None,
        domain: str = "general"
    ) -> Tuple[str, bool]:
        """
        Add a citation. Returns (citation_id, is_new).
        
        If citation already exists (same source), updates relevance info
        but doesn't duplicate.
        """
        with self._lock:
            source_key = f"{source_type}:{source_id}"
            
            # Check for existing
            if source_key in self._source_to_id:
                existing_id = self._source_to_id[source_key]
                # Update with new relevant info if provided
                self._update_citation_relevance(
                    existing_id,
                    relevant_pages or [],
                    relevant_sections or [],
                    key_quotes or [],
                    original_query,
                    relevance_score
                )
                return existing_id, False
            
            # Create new citation
            citation_id = self._generate_id(source_type, source_id)
            
            # Truncate quotes if needed
            if key_quotes:
                key_quotes = [
                    {**q, 'text': q['text'][:self.max_quote_length]}
                    for q in key_quotes[:self.max_quotes_per_citation]
                ]
            
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO citations 
                    (id, source_type, source_id, title, authors, year, venue, url,
                     relevant_pages, relevant_sections, key_quotes, original_query,
                     relevance_score, retrieved_at, tags, domain)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    citation_id, source_type, source_id, title,
                    json.dumps(authors), year, venue, url,
                    json.dumps(relevant_pages or []),
                    json.dumps(relevant_sections or []),
                    json.dumps(key_quotes or []),
                    original_query, relevance_score, time.time(),
                    json.dumps(tags or []), domain
                ))
            
            self._source_to_id[source_key] = citation_id
            return citation_id, True
    
    def _update_citation_relevance(
        self,
        citation_id: str,
        new_pages: List[int],
        new_sections: List[str],
        new_quotes: List[Dict[str, Any]],
        query: str,
        relevance: float
    ) -> None:
        """Update citation with additional relevance info from new query."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT relevant_pages, relevant_sections, key_quotes FROM citations WHERE id = ?",
                (citation_id,)
            ).fetchone()
            
            if row:
                # Merge pages
                existing_pages = set(json.loads(row['relevant_pages']))
                existing_pages.update(new_pages)
                
                # Merge sections
                existing_sections = set(json.loads(row['relevant_sections']))
                existing_sections.update(new_sections)
                
                # Merge quotes (deduplicate by text hash)
                existing_quotes = json.loads(row['key_quotes'])
                existing_quote_hashes = {
                    hashlib.md5(q['text'].encode()).hexdigest()
                    for q in existing_quotes
                }
                
                for quote in new_quotes:
                    quote_hash = hashlib.md5(quote['text'].encode()).hexdigest()
                    if quote_hash not in existing_quote_hashes:
                        existing_quotes.append(quote)
                        if len(existing_quotes) >= self.max_quotes_per_citation:
                            break
                
                conn.execute("""
                    UPDATE citations 
                    SET relevant_pages = ?, relevant_sections = ?, key_quotes = ?
                    WHERE id = ?
                """, (
                    json.dumps(list(existing_pages)),
                    json.dumps(list(existing_sections)),
                    json.dumps(existing_quotes),
                    citation_id
                ))
    
    def get_citation(self, citation_id: str) -> Optional[Citation]:
        """Get a citation by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM citations WHERE id = ?", (citation_id,)
            ).fetchone()
            
            if row:
                return self._row_to_citation(row)
            return None
    
    def get_by_source(self, source_type: str, source_id: str) -> Optional[Citation]:
        """Get citation by source identifier."""
        source_key = f"{source_type}:{source_id}"
        if source_key in self._source_to_id:
            return self.get_citation(self._source_to_id[source_key])
        return None
    
    def _row_to_citation(self, row: sqlite3.Row) -> Citation:
        """Convert database row to Citation object."""
        return Citation(
            id=row['id'],
            source_type=row['source_type'],
            source_id=row['source_id'],
            title=row['title'],
            authors=json.loads(row['authors']),
            year=row['year'],
            venue=row['venue'],
            url=row['url'],
            relevant_pages=json.loads(row['relevant_pages']),
            relevant_sections=json.loads(row['relevant_sections']),
            key_quotes=json.loads(row['key_quotes']),
            original_query=row['original_query'],
            relevance_score=row['relevance_score'],
            retrieved_at=row['retrieved_at'],
            used_in_proposals=json.loads(row['used_in_proposals']),
            usage_count=row['usage_count'],
            last_used=row['last_used'],
            tags=json.loads(row['tags']),
            domain=row['domain']
        )
    
    # ========== Usage Tracking ==========
    
    def record_usage(self, citation_id: str, proposal_id: str) -> None:
        """Record that a citation was used in a proposal."""
        with self._lock:
            with self._get_connection() as conn:
                row = conn.execute(
                    "SELECT used_in_proposals FROM citations WHERE id = ?",
                    (citation_id,)
                ).fetchone()
                
                if row:
                    proposals = json.loads(row['used_in_proposals'])
                    if proposal_id not in proposals:
                        proposals.append(proposal_id)
                    
                    conn.execute("""
                        UPDATE citations 
                        SET used_in_proposals = ?, usage_count = usage_count + 1, last_used = ?
                        WHERE id = ?
                    """, (json.dumps(proposals), time.time(), citation_id))
    
    def get_most_used(self, limit: int = 20, domain: Optional[str] = None) -> List[Citation]:
        """Get most frequently used citations."""
        with self._get_connection() as conn:
            if domain:
                rows = conn.execute("""
                    SELECT * FROM citations 
                    WHERE domain = ? 
                    ORDER BY usage_count DESC 
                    LIMIT ?
                """, (domain, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM citations 
                    ORDER BY usage_count DESC 
                    LIMIT ?
                """, (limit,)).fetchall()
            
            return [self._row_to_citation(row) for row in rows]
    
    # ========== Search ==========
    
    def search(
        self,
        query: str,
        domain: Optional[str] = None,
        source_type: Optional[str] = None,
        limit: int = 20
    ) -> List[Citation]:
        """Search citations by title/query keywords."""
        with self._get_connection() as conn:
            sql = "SELECT * FROM citations WHERE (title LIKE ? OR original_query LIKE ?)"
            params = [f"%{query}%", f"%{query}%"]
            
            if domain:
                sql += " AND domain = ?"
                params.append(domain)
            
            if source_type:
                sql += " AND source_type = ?"
                params.append(source_type)
            
            sql += " ORDER BY relevance_score DESC, usage_count DESC LIMIT ?"
            params.append(limit)
            
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_citation(row) for row in rows]
    
    def get_by_domain(self, domain: str, limit: int = 50) -> List[Citation]:
        """Get citations by domain."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM citations 
                WHERE domain = ? 
                ORDER BY relevance_score DESC 
                LIMIT ?
            """, (domain, limit)).fetchall()
            
            return [self._row_to_citation(row) for row in rows]
    
    # ========== Citation Bundles ==========
    
    def create_bundle(
        self,
        topic: str,
        query: str,
        citation_ids: List[str],
        proposal_id: Optional[str] = None,
        summary: str = ""
    ) -> str:
        """Create a bundle of related citations."""
        bundle_id = hashlib.sha256(f"{topic}{time.time()}".encode()).hexdigest()[:16]
        
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO bundles (id, topic, query, citations, created_at, proposal_id, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                bundle_id, topic, query, json.dumps(citation_ids),
                time.time(), proposal_id, summary
            ))
        
        return bundle_id
    
    def get_bundle(self, bundle_id: str) -> Optional[CitationBundle]:
        """Get a citation bundle."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM bundles WHERE id = ?", (bundle_id,)
            ).fetchone()
            
            if row:
                return CitationBundle(
                    id=row['id'],
                    topic=row['topic'],
                    query=row['query'],
                    citations=json.loads(row['citations']),
                    created_at=row['created_at'],
                    proposal_id=row['proposal_id'],
                    summary=row['summary']
                )
            return None
    
    def get_bundles_for_proposal(self, proposal_id: str) -> List[CitationBundle]:
        """Get all citation bundles for a proposal."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM bundles WHERE proposal_id = ?", (proposal_id,)
            ).fetchall()
            
            return [
                CitationBundle(
                    id=row['id'],
                    topic=row['topic'],
                    query=row['query'],
                    citations=json.loads(row['citations']),
                    created_at=row['created_at'],
                    proposal_id=row['proposal_id'],
                    summary=row['summary']
                )
                for row in rows
            ]
    
    # ========== PaperQA Integration ==========
    
    def retrieve_full_content(self, citation_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve full content from PaperQA using stored citation reference.
        
        Returns full paper content if PaperQA client is configured.
        """
        if not self.paperqa:
            logger.warning("PaperQA client not configured")
            return None
        
        citation = self.get_citation(citation_id)
        if not citation:
            return None
        
        try:
            # Use PaperQA to retrieve full content
            retrieval_key = citation.get_retrieval_key()
            
            # This would call your PaperQA client
            # result = self.paperqa.retrieve(retrieval_key)
            # return result
            
            # Placeholder - implement based on your PaperQA API
            return {
                'source': retrieval_key,
                'status': 'paperqa_retrieval_needed',
                'citation': citation.to_dict()
            }
        except Exception as e:
            logger.error(f"Failed to retrieve from PaperQA: {e}")
            return None
    
    # ========== Export ==========
    
    def export_bibtex(self, citation_ids: Optional[List[str]] = None) -> str:
        """Export citations as BibTeX."""
        if citation_ids:
            citations = [self.get_citation(cid) for cid in citation_ids]
            citations = [c for c in citations if c]
        else:
            with self._get_connection() as conn:
                rows = conn.execute("SELECT * FROM citations").fetchall()
                citations = [self._row_to_citation(row) for row in rows]
        
        return "\n\n".join(c.to_bibtex() for c in citations)
    
    def export_apa(self, citation_ids: Optional[List[str]] = None) -> List[str]:
        """Export citations as APA strings."""
        if citation_ids:
            citations = [self.get_citation(cid) for cid in citation_ids]
            citations = [c for c in citations if c]
        else:
            with self._get_connection() as conn:
                rows = conn.execute("SELECT * FROM citations").fetchall()
                citations = [self._row_to_citation(row) for row in rows]
        
        return [c.to_apa() for c in citations]
    
    # ========== Stats ==========
    
    def get_stats(self) -> Dict[str, Any]:
        """Get citation store statistics."""
        with self._get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM citations").fetchone()[0]
            bundles = conn.execute("SELECT COUNT(*) FROM bundles").fetchone()[0]
            
            by_source = conn.execute("""
                SELECT source_type, COUNT(*) as count 
                FROM citations GROUP BY source_type
            """).fetchall()
            
            by_domain = conn.execute("""
                SELECT domain, COUNT(*) as count 
                FROM citations GROUP BY domain
            """).fetchall()
            
            most_used = conn.execute("""
                SELECT title, usage_count FROM citations 
                ORDER BY usage_count DESC LIMIT 5
            """).fetchall()
            
            return {
                'total_citations': total,
                'total_bundles': bundles,
                'by_source': {row['source_type']: row['count'] for row in by_source},
                'by_domain': {row['domain']: row['count'] for row in by_domain},
                'most_used': [{'title': row['title'], 'count': row['usage_count']} for row in most_used]
            }

