"""
PaperQA Feedback System
=======================

Handles PaperQA feedback and rewards:
- If PaperQA says "won't work" → tiny reward (0.00001) + cooldown
- If PaperQA provides research but hypothesis contradicts evidence → note in disk
- If agent tries anyway and succeeds → big reward multiplier proportional to improvement

This encourages agents to:
- Try even when PaperQA says no (tiny reward)
- Respect evidence (note contradictions)
- But still attempt if they believe it will work (huge reward if right)
"""

import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class PaperQAFeedback:
    """Feedback from PaperQA on a query."""
    query: str
    response: str  # "won't work" or research findings
    contradicts_evidence: bool = False
    evidence_provided: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class HypothesisNote:
    """Note about a hypothesis that contradicts evidence."""
    hypothesis: str
    evidence_contradiction: str
    noted_at: str
    tried_anyway: bool = False
    succeeded: bool = False


class PaperQAFeedbackSystem:
    """
    Manages PaperQA feedback, cooldowns, and reward computation.
    """
    
    def __init__(self, cooldown_seconds: int = 300):  # 5 minute cooldown
        self.cooldown_seconds = cooldown_seconds
        self.query_history: Dict[str, List[float]] = defaultdict(list)  # agent_id -> [timestamps]
        self.feedback_history: List[PaperQAFeedback] = []
        self.hypothesis_notes: Dict[str, HypothesisNote] = {}  # hypothesis_id -> note
        self._disk_path = "hypothesis_notes.json"
    
    def query_paperqa_with_feedback(
        self,
        agent_id: str,
        query: str
    ) -> Dict[str, Any]:
        """
        Query PaperQA and get feedback.
        
        Returns:
            Dict with:
            - response: PaperQA response
            - says_wont_work: bool - Whether PaperQA said it won't work
            - contradicts_evidence: bool - Whether hypothesis contradicts evidence
            - evidence: List of evidence provided
            - reward: float - Tiny reward if PaperQA says won't work
            - cooldown_active: bool - Whether agent is in cooldown
        """
        # Check cooldown
        if self._is_in_cooldown(agent_id):
            return {
                'response': 'Cooldown active - please wait before querying again',
                'says_wont_work': False,
                'contradicts_evidence': False,
                'evidence': [],
                'reward': 0.0,
                'cooldown_active': True
            }
        
        # Query PaperQA
        try:
            from integrations.agent0_tool_servers import query_paperqa
            
            paperqa_response = query_paperqa(query)
            response_text = paperqa_response.get('observation', '')
            
            # Check if PaperQA says "won't work"
            says_wont_work = any(phrase in response_text.lower() for phrase in [
                "won't work", "will not work", "doesn't work", "failed",
                "not supported", "contradicts", "against evidence"
            ])
            
            # Check if contradicts evidence
            contradicts_evidence = any(phrase in response_text.lower() for phrase in [
                "contradicts", "against evidence", "not supported by",
                "evidence suggests otherwise", "research shows"
            ])
            
            # Extract evidence
            evidence = paperqa_response.get('extra_field', {}).get('sources', [])
            
            # Record query
            self.query_history[agent_id].append(time.time())
            
            # Create feedback
            feedback = PaperQAFeedback(
                query=query,
                response=response_text,
                contradicts_evidence=contradicts_evidence,
                evidence_provided=evidence
            )
            self.feedback_history.append(feedback)
            
            # Tiny reward if PaperQA says won't work
            reward = 0.00001 if says_wont_work else 0.0
            
            # Activate cooldown if PaperQA says won't work
            if says_wont_work:
                # Cooldown already activated by recording query timestamp
                pass
            
            return {
                'response': response_text,
                'says_wont_work': says_wont_work,
                'contradicts_evidence': contradicts_evidence,
                'evidence': evidence,
                'reward': reward,
                'cooldown_active': False,
                'feedback': feedback
            }
            
        except Exception as e:
            logger.error(f"PaperQA query failed: {e}")
            return {
                'response': f'Error: {str(e)}',
                'says_wont_work': False,
                'contradicts_evidence': False,
                'evidence': [],
                'reward': 0.0,
                'cooldown_active': False
            }
    
    def _is_in_cooldown(self, agent_id: str) -> bool:
        """Check if agent is in cooldown period."""
        if agent_id not in self.query_history:
            return False
        
        timestamps = self.query_history[agent_id]
        if not timestamps:
            return False
        
        # Check if last query was within cooldown period
        last_query_time = timestamps[-1]
        time_since_last = time.time() - last_query_time
        
        return time_since_last < self.cooldown_seconds
    
    def note_hypothesis_contradiction(
        self,
        hypothesis_id: str,
        hypothesis: str,
        evidence_contradiction: str,
        agent_memory: Optional[Any] = None
    ) -> None:
        """
        Note that a hypothesis contradicts evidence.
        
        Agent can note this in its "disk" (memory) for future reference.
        If agent_memory is provided (AIMemorySystem), stores in long-term memory.
        """
        note = HypothesisNote(
            hypothesis=hypothesis,
            evidence_contradiction=evidence_contradiction,
            noted_at=datetime.now().isoformat(),
            tried_anyway=False,
            succeeded=False
        )
        self.hypothesis_notes[hypothesis_id] = note
        
        # Also store in agent's long-term memory if available
        if agent_memory and hasattr(agent_memory, 'note_hypothesis_contradiction'):
            agent_memory.note_hypothesis_contradiction(
                hypothesis_id=hypothesis_id,
                hypothesis=hypothesis,
                evidence=evidence_contradiction
            )
        
        logger.info(f"Noted hypothesis contradiction: {hypothesis_id}")
    
    def record_hypothesis_attempt(
        self,
        hypothesis_id: str,
        succeeded: bool,
        improvement_metrics: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Record that agent tried hypothesis despite evidence contradiction.
        
        If it succeeded, compute big reward multiplier.
        
        Returns:
            Dict with reward multiplier if succeeded
        """
        if hypothesis_id not in self.hypothesis_notes:
            return {'multiplier': 1.0, 'reward_bonus': 0.0}
        
        note = self.hypothesis_notes[hypothesis_id]
        note.tried_anyway = True
        note.succeeded = succeeded
        
        if succeeded:
            # BIG REWARD MULTIPLIER proportional to improvement
            # If agent proved evidence wrong or found edge case
            
            # Compute multiplier based on improvement
            performance_gain = improvement_metrics.get('performance_gain', 0.0) if improvement_metrics else 0.0
            accuracy_change = improvement_metrics.get('accuracy_change', 0.0) if improvement_metrics else 0.0
            
            # Base multiplier for succeeding despite evidence
            base_multiplier = 2.0
            
            # Additional multiplier proportional to improvement
            # 10% improvement = +0.5x, 20% = +1.0x, etc.
            improvement_multiplier = 1.0 + (performance_gain / 100.0) * 5.0
            improvement_multiplier += accuracy_change * 25.0  # 0.05 accuracy = +1.25x
            
            total_multiplier = base_multiplier * improvement_multiplier
            
            logger.info(
                f"Hypothesis succeeded despite evidence! "
                f"Multiplier: {total_multiplier:.2f}x "
                f"(performance: {performance_gain:.1f}%, accuracy: {accuracy_change:.3f})"
            )
            
            return {
                'multiplier': total_multiplier,
                'reward_bonus': 5.0,  # Additional bonus
                'reason': 'Succeeded despite evidence contradiction'
            }
        else:
            # Failed - no multiplier
            return {
                'multiplier': 1.0,
                'reward_bonus': 0.0,
                'reason': 'Tried despite evidence but failed'
            }
    
    def get_hypothesis_note(self, hypothesis_id: str) -> Optional[HypothesisNote]:
        """Get note about a hypothesis."""
        return self.hypothesis_notes.get(hypothesis_id)


# Global feedback system
_feedback_system: Optional[PaperQAFeedbackSystem] = None

def get_feedback_system() -> PaperQAFeedbackSystem:
    """Get or create the global feedback system."""
    global _feedback_system
    if _feedback_system is None:
        _feedback_system = PaperQAFeedbackSystem()
    return _feedback_system


# Convenience functions
def query_paperqa_with_feedback(agent_id: str, query: str) -> Dict[str, Any]:
    """Query PaperQA and get feedback with reward/cooldown."""
    system = get_feedback_system()
    return system.query_paperqa_with_feedback(agent_id, query)


def note_hypothesis_contradiction(hypothesis_id: str, hypothesis: str, evidence: str) -> None:
    """Note that hypothesis contradicts evidence."""
    system = get_feedback_system()
    system.note_hypothesis_contradiction(hypothesis_id, hypothesis, evidence)


def record_hypothesis_attempt(hypothesis_id: str, succeeded: bool, improvement_metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Record hypothesis attempt and get reward multiplier if succeeded."""
    system = get_feedback_system()
    return system.record_hypothesis_attempt(hypothesis_id, succeeded, improvement_metrics)

