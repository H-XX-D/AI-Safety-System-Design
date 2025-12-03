"""
Session Distiller - Compresses session history into distilled knowledge.

Instead of storing raw session data, we distill:
- Key findings and insights
- Successful patterns
- Failure modes to avoid
- Important decisions and their outcomes

This creates a compact, high-value representation of past sessions.
"""

import json
import time
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
import threading
import logging

logger = logging.getLogger(__name__)


@dataclass
class DistilledInsight:
    """A single distilled insight from a session."""
    id: str
    insight_type: str  # 'finding', 'pattern', 'failure_mode', 'decision', 'technique'
    title: str
    summary: str  # Compressed version
    evidence_ids: List[str]  # Original proposal/note IDs that support this
    confidence: float
    domain: str
    tags: List[str]
    created_at: float
    source_session: str
    usage_count: int = 0  # How often this insight has been retrieved
    last_used: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DistilledInsight':
        return cls(**data)


@dataclass
class DistilledSession:
    """Compressed representation of an entire session."""
    session_id: str
    agent_id: str
    started_at: float
    ended_at: float
    
    # Distilled content
    insights: List[DistilledInsight]
    key_decisions: List[Dict[str, Any]]
    
    # Statistics
    proposals_submitted: int
    proposals_approved: int
    proposals_rejected: int
    total_reward: float
    
    # Session summary
    summary: str
    main_topics: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'session_id': self.session_id,
            'agent_id': self.agent_id,
            'started_at': self.started_at,
            'ended_at': self.ended_at,
            'insights': [i.to_dict() for i in self.insights],
            'key_decisions': self.key_decisions,
            'proposals_submitted': self.proposals_submitted,
            'proposals_approved': self.proposals_approved,
            'proposals_rejected': self.proposals_rejected,
            'total_reward': self.total_reward,
            'summary': self.summary,
            'main_topics': self.main_topics
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DistilledSession':
        data['insights'] = [DistilledInsight.from_dict(i) for i in data.get('insights', [])]
        return cls(**data)


class SessionDistiller:
    """
    Distills raw session data into compact, high-value knowledge.
    
    Process:
    1. Analyze session notes and proposals
    2. Extract key insights and patterns
    3. Compress into distilled form
    4. Deduplicate against existing knowledge
    5. Store in persistent memory
    """
    
    def __init__(self, llm_client=None):
        """
        Args:
            llm_client: Optional LLM client for intelligent summarization.
                       If None, uses rule-based extraction.
        """
        self.llm_client = llm_client
    
    def distill_session(
        self,
        session_id: str,
        agent_id: str,
        notes: List[Dict[str, Any]],
        proposals: List[Dict[str, Any]],
        feedback: List[Dict[str, Any]],
        started_at: float,
        ended_at: float
    ) -> DistilledSession:
        """
        Distill a complete session into compressed knowledge.
        """
        insights = []
        
        # Extract insights from notes
        for note in notes:
            if note.get('priority', 0) >= 3:  # Only high-priority notes
                insight = self._note_to_insight(note, session_id)
                if insight:
                    insights.append(insight)
        
        # Extract patterns from proposals
        approved = [p for p in proposals if p.get('outcome') == 'approved']
        rejected = [p for p in proposals if p.get('outcome') == 'rejected']
        
        # Success patterns
        if approved:
            success_insights = self._extract_success_patterns(approved, session_id)
            insights.extend(success_insights)
        
        # Failure patterns
        if rejected:
            failure_insights = self._extract_failure_patterns(rejected, feedback, session_id)
            insights.extend(failure_insights)
        
        # Key decisions
        key_decisions = self._extract_key_decisions(proposals, feedback)
        
        # Generate summary
        summary = self._generate_session_summary(notes, proposals, feedback)
        
        # Extract main topics
        main_topics = self._extract_main_topics(proposals, notes)
        
        return DistilledSession(
            session_id=session_id,
            agent_id=agent_id,
            started_at=started_at,
            ended_at=ended_at,
            insights=insights,
            key_decisions=key_decisions,
            proposals_submitted=len(proposals),
            proposals_approved=len(approved),
            proposals_rejected=len(rejected),
            total_reward=sum(p.get('reward', 0) for p in proposals),
            summary=summary,
            main_topics=main_topics
        )
    
    def _note_to_insight(self, note: Dict[str, Any], session_id: str) -> Optional[DistilledInsight]:
        """Convert a high-priority note to a distilled insight."""
        note_type = note.get('note_type', 'finding')
        
        # Map note types to insight types
        type_map = {
            'finding': 'finding',
            'question': 'finding',  # Resolved questions become findings
            'todo': 'technique',    # Completed todos become techniques
            'reference': 'finding',
            'insight': 'pattern'
        }
        
        return DistilledInsight(
            id=f"insight_{hashlib.md5(note.get('content', '').encode()).hexdigest()[:12]}",
            insight_type=type_map.get(note_type, 'finding'),
            title=note.get('title', 'Untitled'),
            summary=self._compress_text(note.get('content', ''), max_len=200),
            evidence_ids=[note.get('id', '')],
            confidence=min(note.get('priority', 3) / 5.0, 1.0),
            domain=self._infer_domain(note.get('content', '')),
            tags=note.get('tags', []),
            created_at=note.get('created_at', time.time()),
            source_session=session_id
        )
    
    def _extract_success_patterns(
        self,
        approved_proposals: List[Dict[str, Any]],
        session_id: str
    ) -> List[DistilledInsight]:
        """Extract patterns from successful proposals."""
        insights = []
        
        # Group by domain/topic
        by_domain = {}
        for p in approved_proposals:
            domain = p.get('domain', 'general')
            if domain not in by_domain:
                by_domain[domain] = []
            by_domain[domain].append(p)
        
        for domain, proposals in by_domain.items():
            if len(proposals) >= 1:
                # Extract common elements
                high_reward = [p for p in proposals if p.get('reward', 0) > 0.5]
                
                if high_reward:
                    insight = DistilledInsight(
                        id=f"success_{domain}_{session_id[:8]}",
                        insight_type='pattern',
                        title=f"Successful approach in {domain}",
                        summary=self._summarize_proposals(high_reward),
                        evidence_ids=[p.get('id', '') for p in high_reward],
                        confidence=sum(p.get('reward', 0) for p in high_reward) / len(high_reward),
                        domain=domain,
                        tags=['success', 'pattern', domain],
                        created_at=time.time(),
                        source_session=session_id
                    )
                    insights.append(insight)
        
        return insights
    
    def _extract_failure_patterns(
        self,
        rejected_proposals: List[Dict[str, Any]],
        feedback: List[Dict[str, Any]],
        session_id: str
    ) -> List[DistilledInsight]:
        """Extract failure modes from rejected proposals."""
        insights = []
        
        # Group feedback by rejection reason
        rejection_reasons = {}
        for f in feedback:
            if f.get('feedback_type') == 'rejection':
                reason = self._categorize_rejection(f.get('content', ''))
                if reason not in rejection_reasons:
                    rejection_reasons[reason] = []
                rejection_reasons[reason].append(f)
        
        for reason, feedbacks in rejection_reasons.items():
            if len(feedbacks) >= 1:
                insight = DistilledInsight(
                    id=f"failure_{reason}_{session_id[:8]}",
                    insight_type='failure_mode',
                    title=f"Failure mode: {reason}",
                    summary=self._summarize_feedback(feedbacks),
                    evidence_ids=[f.get('proposal_id', '') for f in feedbacks],
                    confidence=len(feedbacks) / max(len(rejected_proposals), 1),
                    domain='general',
                    tags=['failure', 'avoid', reason],
                    created_at=time.time(),
                    source_session=session_id
                )
                insights.append(insight)
        
        return insights
    
    def _extract_key_decisions(
        self,
        proposals: List[Dict[str, Any]],
        feedback: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract key decisions made during the session."""
        decisions = []
        
        for p in proposals:
            if p.get('outcome') in ('approved', 'rejected'):
                decision = {
                    'proposal_id': p.get('id'),
                    'title': p.get('title'),
                    'outcome': p.get('outcome'),
                    'confidence_change': p.get('confidence_final', 0) - p.get('confidence_initial', 0),
                    'reward': p.get('reward', 0),
                    'key_feedback': self._get_key_feedback(p.get('id'), feedback)
                }
                decisions.append(decision)
        
        # Sort by importance (high reward or significant confidence change)
        decisions.sort(key=lambda d: abs(d.get('reward', 0)) + abs(d.get('confidence_change', 0)), reverse=True)
        
        return decisions[:10]  # Top 10 decisions
    
    def _generate_session_summary(
        self,
        notes: List[Dict[str, Any]],
        proposals: List[Dict[str, Any]],
        feedback: List[Dict[str, Any]]
    ) -> str:
        """Generate a brief summary of the session."""
        approved = len([p for p in proposals if p.get('outcome') == 'approved'])
        rejected = len([p for p in proposals if p.get('outcome') == 'rejected'])
        total_reward = sum(p.get('reward', 0) for p in proposals)
        
        summary_parts = [
            f"Session: {len(proposals)} proposals ({approved} approved, {rejected} rejected)",
            f"Total reward: {total_reward:.2f}",
            f"Notes recorded: {len(notes)}"
        ]
        
        # Add key topics
        topics = self._extract_main_topics(proposals, notes)
        if topics:
            summary_parts.append(f"Main topics: {', '.join(topics[:3])}")
        
        return ". ".join(summary_parts)
    
    def _extract_main_topics(
        self,
        proposals: List[Dict[str, Any]],
        notes: List[Dict[str, Any]]
    ) -> List[str]:
        """Extract main topics from session content."""
        # Simple keyword extraction
        all_text = " ".join([
            p.get('title', '') + " " + p.get('content', '')[:200]
            for p in proposals
        ])
        all_text += " ".join([n.get('title', '') for n in notes])
        
        # Count significant words
        words = all_text.lower().split()
        word_counts = {}
        stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 
                     'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                     'would', 'could', 'should', 'may', 'might', 'must', 'shall',
                     'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
                     'this', 'that', 'these', 'those', 'and', 'or', 'but', 'if'}
        
        for word in words:
            if len(word) > 3 and word not in stopwords:
                word_counts[word] = word_counts.get(word, 0) + 1
        
        # Return top topics
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        return [w for w, c in sorted_words[:5]]
    
    def _compress_text(self, text: str, max_len: int = 200) -> str:
        """Compress text to max length while preserving meaning."""
        if len(text) <= max_len:
            return text
        
        # Simple truncation with ellipsis
        # Could use LLM for smarter summarization
        return text[:max_len-3] + "..."
    
    def _summarize_proposals(self, proposals: List[Dict[str, Any]]) -> str:
        """Summarize a list of proposals."""
        if not proposals:
            return ""
        
        titles = [p.get('title', 'Untitled') for p in proposals[:3]]
        avg_reward = sum(p.get('reward', 0) for p in proposals) / len(proposals)
        
        return f"Approaches: {', '.join(titles)}. Avg reward: {avg_reward:.2f}"
    
    def _summarize_feedback(self, feedbacks: List[Dict[str, Any]]) -> str:
        """Summarize feedback items."""
        if not feedbacks:
            return ""
        
        contents = [f.get('content', '')[:100] for f in feedbacks[:3]]
        return " | ".join(contents)
    
    def _categorize_rejection(self, feedback_content: str) -> str:
        """Categorize rejection reason from feedback."""
        content_lower = feedback_content.lower()
        
        categories = {
            'code_quality': ['bug', 'error', 'syntax', 'broken', 'crash'],
            'overconfidence': ['overconfident', 'too confident', 'confidence'],
            'missing_evidence': ['evidence', 'citation', 'source', 'proof'],
            'scope': ['scope', 'too broad', 'too narrow', 'unfocused'],
            'feasibility': ['feasible', 'practical', 'realistic', 'impossible'],
            'safety': ['unsafe', 'dangerous', 'risk', 'harm']
        }
        
        for category, keywords in categories.items():
            if any(kw in content_lower for kw in keywords):
                return category
        
        return 'other'
    
    def _get_key_feedback(self, proposal_id: str, feedback: List[Dict[str, Any]]) -> str:
        """Get key feedback for a proposal."""
        relevant = [f for f in feedback if f.get('proposal_id') == proposal_id]
        if relevant:
            return relevant[0].get('content', '')[:100]
        return ""
    
    def _infer_domain(self, text: str) -> str:
        """Infer domain from text content."""
        text_lower = text.lower()
        
        domains = {
            'safety': ['safe', 'harm', 'risk', 'protect', 'security'],
            'performance': ['fast', 'efficient', 'optimize', 'speed', 'latency'],
            'accuracy': ['accurate', 'correct', 'precision', 'error rate'],
            'usability': ['user', 'interface', 'experience', 'easy'],
            'reliability': ['reliable', 'stable', 'robust', 'fault']
        }
        
        for domain, keywords in domains.items():
            if any(kw in text_lower for kw in keywords):
                return domain
        
        return 'general'

