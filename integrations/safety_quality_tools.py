"""
Agent0 Tool Integrations (Adapted for AI Safety System)
========================================================

Tools adapted from Agent0, customized for AI Safety System:

1. Proposal Consistency Check: Validates proposals using deception detection
   and peer agreement (safety-focused)

2. Hypothesis Quality Scoring: Scores improvement hypotheses based on:
   - Safety impact
   - Evidence quality
   - Risk assessment
   - Alignment with system goals

3. Training Data Quality Filter: Filters RL training data based on:
   - Deception scores (reject deceptive)
   - Sandbox success (keep successful)
   - Peer approval rates
   - Honesty indicators

4. Proposal Deduplication: Groups similar proposals, prioritizing:
   - Safety-critical improvements
   - High-impact changes
   - Well-evidenced proposals
"""

import re
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from collections import Counter
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# PROPOSAL CONSISTENCY VALIDATION TOOL
# ============================================================================

class proposal_consistency_tool:
    """
    Check proposal consistency using deception detection and peer agreement.
    
    Validates proposals by checking:
    - Deception scores (should be low)
    - Peer review agreement (high agreement = consistent)
    - Risk disclosure consistency
    - Honesty indicators alignment
    
    Safety-focused: prioritizes catching deceptive or inconsistent proposals.
    """
    
    def __init__(
        self,
        max_deception_score: float = 0.3,
        min_peer_agreement: float = 0.7,
        require_risk_disclosure: bool = True
    ):
        """
        Initialize proposal consistency checker.
        
        Args:
            max_deception_score: Maximum deception score to pass (lower is better)
            min_peer_agreement: Minimum peer agreement ratio (0-1)
            require_risk_disclosure: Whether risk disclosure is required
        """
        self.max_deception_score = max_deception_score
        self.min_peer_agreement = min_peer_agreement
        self.require_risk_disclosure = require_risk_disclosure
    
    def check_proposal(
        self,
        proposal: Dict[str, Any],
        deception_score: float = 0.0,
        peer_reviews: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Check proposal consistency using safety metrics.
        
        Args:
            proposal: Proposal dict with title, changes, risks, etc.
            deception_score: Deception detection score (0-1, lower is better)
            peer_reviews: List of peer review dicts with 'vote' and 'concerns'
            
        Returns:
            Dict with:
            - consistency_score: 0-1 overall consistency
            - passed: Whether proposal passes consistency checks
            - deception_passed: Whether deception score is acceptable
            - peer_agreement: Peer agreement ratio
            - risk_disclosure_ok: Whether risks are properly disclosed
            - issues: List of consistency issues found
        """
        issues = []
        passed = True
        
        # Check deception score
        deception_passed = deception_score <= self.max_deception_score
        if not deception_passed:
            issues.append(f"High deception score: {deception_score:.2f}")
            passed = False
        
        # Check peer agreement
        peer_agreement = 0.5  # Default
        if peer_reviews:
            votes = [r.get('vote', 'reject') for r in peer_reviews]
            approvals = sum(1 for v in votes if v == 'approve')
            peer_agreement = approvals / len(votes) if votes else 0.0
            
            if peer_agreement < self.min_peer_agreement:
                issues.append(f"Low peer agreement: {peer_agreement:.2f}")
                passed = False
        
        # Check risk disclosure
        risk_disclosure_ok = True
        if self.require_risk_disclosure:
            identified_risks = proposal.get('identified_risks', [])
            admitted_uncertainties = proposal.get('admitted_uncertainties', [])
            
            if not identified_risks and not admitted_uncertainties:
                risk_disclosure_ok = False
                issues.append("Missing risk disclosure")
                passed = False
        
        # Overall consistency score
        consistency_score = (
            (1.0 - deception_score) * 0.4 +  # Deception weight
            peer_agreement * 0.4 +            # Peer agreement weight
            (1.0 if risk_disclosure_ok else 0.0) * 0.2  # Risk disclosure weight
        )
        
        return {
            'consistent': passed,  # Changed key to match usage
            'consistency_score': consistency_score,
            'passed': passed,
            'deception_passed': deception_passed,
            'peer_agreement': peer_agreement,
            'risk_disclosure_ok': risk_disclosure_ok,
            'issues': issues,
            'evidence_requested': self._get_evidence_requested(issues, deception_score, peer_agreement, risk_disclosure_ok),
            'gate_to_counter': self._get_gate_to_counter(issues, deception_score, peer_agreement, risk_disclosure_ok),
            'actionable_feedback': self._get_actionable_feedback(issues, deception_score, peer_agreement, risk_disclosure_ok)
        }
    
    def _get_evidence_requested(
        self,
        issues: List[str],
        deception_score: float,
        peer_agreement: float,
        risk_disclosure_ok: bool
    ) -> List[str]:
        """Get list of evidence requested to pass checks."""
        evidence = []
        
        if deception_score > self.max_deception_score:
            evidence.append("Provide clearer reasoning and transparency")
            evidence.append("Address any ambiguous or misleading statements")
            evidence.append("Demonstrate honest intent with concrete examples")
        
        if peer_agreement < self.min_peer_agreement:
            evidence.append(f"Increase peer support (current: {peer_agreement:.1%}, need: {self.min_peer_agreement:.1%})")
            evidence.append("Address peer concerns and incorporate feedback")
            evidence.append("Provide additional justification for controversial aspects")
        
        if not risk_disclosure_ok:
            evidence.append("Identify potential risks or limitations")
            evidence.append("Admit uncertainties or unknowns")
            evidence.append("Provide rollback plan or mitigation strategies")
        
        return evidence
    
    def _get_gate_to_counter(
        self,
        issues: List[str],
        deception_score: float,
        peer_agreement: float,
        risk_disclosure_ok: bool
    ) -> Optional[str]:
        """Get the specific gate that needs to be countered."""
        gates = []
        
        if deception_score > self.max_deception_score:
            gates.append(f"Deception gate: Score must be <= {self.max_deception_score:.2f} (current: {deception_score:.2f})")
        
        if peer_agreement < self.min_peer_agreement:
            gates.append(f"Peer agreement gate: Must achieve >= {self.min_peer_agreement:.1%} (current: {peer_agreement:.1%})")
        
        if not risk_disclosure_ok:
            gates.append("Risk disclosure gate: Must identify risks or admit uncertainties")
        
        return " | ".join(gates) if gates else None
    
    def _get_actionable_feedback(
        self,
        issues: List[str],
        deception_score: float,
        peer_agreement: float,
        risk_disclosure_ok: bool
    ) -> Dict[str, Any]:
        """Get actionable feedback for improving the proposal."""
        feedback = {
            'issues': issues,
            'actions': []
        }
        
        if deception_score > self.max_deception_score:
            feedback['actions'].append({
                'priority': 'high',
                'action': 'Reduce deception score',
                'current': deception_score,
                'target': self.max_deception_score,
                'steps': [
                    'Review proposal for ambiguous language',
                    'Clarify all claims with evidence',
                    'Remove any misleading statements',
                    'Add transparency about limitations'
                ]
            })
        
        if peer_agreement < self.min_peer_agreement:
            feedback['actions'].append({
                'priority': 'high',
                'action': 'Increase peer agreement',
                'current': peer_agreement,
                'target': self.min_peer_agreement,
                'steps': [
                    'Address peer concerns directly',
                    'Incorporate peer feedback',
                    'Provide additional justification',
                    'Clarify misunderstood aspects'
                ]
            })
        
        if not risk_disclosure_ok:
            feedback['actions'].append({
                'priority': 'medium',
                'action': 'Add risk disclosure',
                'steps': [
                    'Identify potential risks or limitations',
                    'Admit uncertainties or unknowns',
                    'Provide mitigation strategies',
                    'Include rollback plan if applicable'
                ]
            })
        
        return feedback
    
    def extract_key_claims(self, text: str) -> List[str]:
        """Extract key claims from proposal text."""
        # Simple extraction - in production would be more sophisticated
        claims = []
        
        # Extract statements ending with periods
        sentences = re.split(r'[.!?]+', text)
        for sent in sentences:
            sent = sent.strip()
            if len(sent) > 20 and any(word in sent.lower() for word in ['improve', 'change', 'add', 'remove', 'modify']):
                claims.append(sent)
        
        return claims
    
    def compute_consistency(self, claims_list: List[List[str]]) -> float:
        """
        Compute consistency score across multiple claim sets.
        
        Args:
            claims_list: List of claim lists (one per response)
            
        Returns:
            Consistency score 0-1
        """
        if not claims_list or len(claims_list) < 2:
            return 0.0
        
        # Simple overlap-based consistency
        # In production, would use semantic similarity
        all_claims = [claim for claims in claims_list for claim in claims]
        claim_counts = Counter(all_claims)
        
        # Consistency = ratio of claims that appear in multiple responses
        total_claims = len(all_claims)
        repeated_claims = sum(1 for count in claim_counts.values() if count > 1)
        
        if total_claims == 0:
            return 0.0
        
        return repeated_claims / total_claims


# ============================================================================
# HYPOTHESIS QUALITY SCORING TOOL
# ============================================================================

class hypothesis_scoring_tool:
    """
    Score improvement hypotheses based on safety and quality metrics.
    
    Scores hypotheses based on:
    - Safety impact (positive impact on system safety)
    - Evidence quality (well-supported by research)
    - Risk assessment (properly identifies risks)
    - Alignment with system goals (improves target component)
    - Novelty (not redundant with existing proposals)
    
    Higher scores = better hypotheses for self-improvement.
    """
    
    def __init__(self):
        self.task_history: List[Dict[str, Any]] = []
    
    def score_hypothesis(
        self,
        hypothesis: Dict[str, Any],
        evidence_quality: float = 0.5,
        safety_impact: float = 0.5,
        sandbox_success: Optional[bool] = None
    ) -> float:
        """
        Score an improvement hypothesis.
        
        Args:
            hypothesis: Hypothesis dict with name, target_component, etc.
            evidence_quality: Quality of supporting evidence (0-1)
            safety_impact: Expected safety impact (0-1, higher = safer)
            sandbox_success: Whether sandbox test succeeded (if tested)
            
        Returns:
            Quality score (0-1, higher = better)
        """
        score = 0.0
        
        # Evidence quality (30% weight)
        score += evidence_quality * 0.3
        
        # Safety impact (40% weight - most important)
        score += safety_impact * 0.4
        
        # Risk assessment (20% weight)
        risks = hypothesis.get('potential_risks', [])
        rollback_plan = hypothesis.get('rollback_plan', '')
        
        risk_score = 0.5  # Default
        if risks and len(risks) > 0:
            risk_score += 0.2  # Risks identified
        if rollback_plan and len(rollback_plan) > 20:
            risk_score += 0.3  # Has rollback plan
        
        score += risk_score * 0.2
        
        # Novelty (10% weight) - penalize redundancy
        similarity = self._check_redundancy(hypothesis.get('name', ''))
        novelty = 1.0 - similarity  # Higher novelty = lower similarity
        score += novelty * 0.1
        
        # Sandbox bonus (if tested)
        if sandbox_success is True:
            score += 0.1  # Bonus for successful sandbox test
        elif sandbox_success is False:
            score -= 0.2  # Penalty for failed test
        
        # Clamp to 0-1
        score = max(0.0, min(1.0, score))
        
        return score
    
    def __init__(self):
        self.hypothesis_history: List[Dict[str, Any]] = []
    
    def _check_redundancy(self, hypothesis_name: str) -> float:
        """Check how similar this hypothesis is to previous ones."""
        if not self.hypothesis_history:
            return 0.0
        
        # Simple word overlap check
        # In production, would use semantic similarity
        name_words = set(hypothesis_name.lower().split())
        max_similarity = 0.0
        
        for prev_hyp in self.hypothesis_history[-20:]:  # Check last 20
            prev_name = prev_hyp.get('name', '').lower()
            prev_words = set(prev_name.split())
            if name_words and prev_words:
                overlap = len(name_words & prev_words) / len(name_words | prev_words)
                max_similarity = max(max_similarity, overlap)
        
        return max_similarity
    
    def record_hypothesis(self, hypothesis: Dict[str, Any], score: float):
        """Record a hypothesis and its score."""
        self.hypothesis_history.append({
            'name': hypothesis.get('name', ''),
            'score': score,
            'timestamp': time.time()
        })


# ============================================================================
# SAFE TRAINING DATA FILTER TOOL
# ============================================================================

class safe_training_data_filter_tool:
    """
    Filter RL training data based on safety and quality metrics.
    
    Only keeps proposals that:
    - Pass deception detection (low deception score)
    - Succeeded in sandbox (proven safe)
    - Have high peer approval (trusted by peers)
    - Show honesty indicators (admitted uncertainties, identified risks)
    
    This ensures RL training only learns from safe, honest, successful proposals.
    """
    
    def __init__(
        self,
        max_deception_score: float = 0.3,
        min_peer_approval: float = 0.7,
        require_sandbox_success: bool = True,
        require_honesty_indicators: bool = True
    ):
        """
        Initialize safety training filter.
        
        Args:
            max_deception_score: Maximum deception score to keep (lower is better)
            min_peer_approval: Minimum peer approval rate (0-1)
            require_sandbox_success: Whether sandbox success is required
            require_honesty_indicators: Whether honesty indicators are required
        """
        self.max_deception_score = max_deception_score
        self.min_peer_approval = min_peer_approval
        self.require_sandbox_success = require_sandbox_success
        self.require_honesty_indicators = require_honesty_indicators
    
    def filter_proposals(
        self,
        proposals: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Filter proposals based on safety and quality metrics.
        
        Args:
            proposals: List of proposal dicts with deception_score, peer_approval, etc.
            
        Returns:
            (kept_proposals, filtered_out_proposals)
        """
        kept = []
        filtered = []
        
        for prop in proposals:
            # Check deception score
            deception_score = prop.get('deception_score', 1.0)  # Default to high (fail)
            if deception_score > self.max_deception_score:
                filtered.append({**prop, 'filter_reason': 'high_deception_score'})
                continue
            
            # Check peer approval
            peer_approval = prop.get('peer_approval_rate', 0.0)
            if peer_approval < self.min_peer_approval:
                filtered.append({**prop, 'filter_reason': 'low_peer_approval'})
                continue
            
            # Check sandbox success
            if self.require_sandbox_success:
                sandbox_success = prop.get('sandbox_success', False)
                if not sandbox_success:
                    filtered.append({**prop, 'filter_reason': 'sandbox_failed'})
                    continue
            
            # Check honesty indicators
            if self.require_honesty_indicators:
                has_risks = len(prop.get('identified_risks', [])) > 0
                has_uncertainties = len(prop.get('admitted_uncertainties', [])) > 0
                
                if not (has_risks or has_uncertainties):
                    filtered.append({**prop, 'filter_reason': 'missing_honesty_indicators'})
                    continue
            
            # Keep it
            kept.append(prop)
        
        logger.info(f"Filtered {len(proposals)} proposals: kept {len(kept)}, filtered {len(filtered)}")
        
        return kept, filtered


# ============================================================================
# PROPOSAL DEDUPLICATION TOOL
# ============================================================================

class proposal_deduplication_tool:
    """
    Deduplicate proposals by grouping similar ones and selecting best representatives.
    
    Groups similar proposals together and selects the best one from each group based on:
    - Safety impact (prioritize safety-critical improvements)
    - Evidence quality (well-supported proposals)
    - Sandbox success (proven to work)
    - Peer approval (trusted by peers)
    
    Prevents duplicate work while prioritizing high-quality, safety-focused proposals.
    """
    
    def __init__(self, similarity_threshold: float = 0.7):
        """
        Initialize clustering.
        
        Args:
            similarity_threshold: Minimum similarity to cluster together
        """
        self.similarity_threshold = similarity_threshold
        self.proposal_history: List[Dict[str, Any]] = []

    def check_proposal(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if a single proposal is redundant against history.
        
        Args:
            proposal: Proposal dict
            
        Returns:
            Dict with 'unique': bool, 'reason': str
        """
        if not self.proposal_history:
            self.proposal_history.append(proposal)
            return {'unique': True}
            
        prop_text = proposal.get('title', '') + ' ' + proposal.get('changes', {}).get('description', '')
        
        for prev_prop in self.proposal_history:
            prev_text = prev_prop.get('title', '') + ' ' + prev_prop.get('changes', {}).get('description', '')
            similarity = self._text_similarity(prop_text, prev_text)
            
            if similarity >= self.similarity_threshold:
                return {
                    'unique': False, 
                    'reason': f"Similar to previous proposal: {prev_prop.get('title')}"
                }
        
        self.proposal_history.append(proposal)
        return {'unique': True}

    def deduplicate_proposals(
        self,
        proposals: List[Dict[str, Any]]
    ) -> Dict[int, List[Dict[str, Any]]]:
        """
        Group similar proposals together.
        
        Args:
            proposals: List of proposal dicts
            
        Returns:
            Dict mapping cluster_id -> list of similar proposals
        """
        if not proposals:
            return {}
        
        clusters: Dict[int, List[Dict[str, Any]]] = {}
        cluster_assignments: List[int] = []
        
        for i, prop in enumerate(proposals):
            prop_text = prop.get('title', '') + ' ' + prop.get('changes', {}).get('description', '')
            
            # Find best matching cluster
            best_cluster = -1
            best_similarity = 0.0
            
            for cluster_id, cluster_props in clusters.items():
                # Compare with first proposal in cluster
                cluster_text = cluster_props[0].get('title', '') + ' ' + cluster_props[0].get('changes', {}).get('description', '')
                similarity = self._text_similarity(prop_text, cluster_text)
                
                if similarity > best_similarity and similarity >= self.similarity_threshold:
                    best_similarity = similarity
                    best_cluster = cluster_id
            
            # Assign to cluster or create new one
            if best_cluster >= 0:
                clusters[best_cluster].append(prop)
                cluster_assignments.append(best_cluster)
            else:
                new_cluster_id = len(clusters)
                clusters[new_cluster_id] = [prop]
                cluster_assignments.append(new_cluster_id)
        
        logger.info(f"Deduplicated {len(proposals)} proposals into {len(clusters)} groups")
        
        return clusters
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Compute simple word overlap similarity."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def get_best_proposals(
        self,
        clusters: Dict[int, List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """
        Get best proposal from each group based on safety and quality.
        
        Prioritizes:
        1. Safety-critical improvements
        2. High evidence quality
        3. Sandbox success
        4. Peer approval
        
        Returns:
            List of best proposals (one per group)
        """
        representatives = []
        
        for cluster_id, props in clusters.items():
            if not props:
                continue
            
            # Score each proposal
            scored = []
            for prop in props:
                score = 0.0
                
                # Safety impact (40% weight)
                safety_impact = prop.get('safety_impact', 0.5)
                score += safety_impact * 0.4
                
                # Evidence quality (20% weight)
                evidence = prop.get('evidence_quality', 0.5)
                score += evidence * 0.2
                
                # Sandbox success (20% weight)
                if prop.get('sandbox_success', False):
                    score += 0.2
                
                # Peer approval (20% weight)
                peer_approval = prop.get('peer_approval_rate', 0.0)
                score += peer_approval * 0.2
                
                scored.append((score, prop))
            
            # Get highest scoring
            best = max(scored, key=lambda x: x[0])[1]
            representatives.append(best)
        
        return representatives


# Convenience functions (tool wrappers)
def validate_proposal_consistency(
    proposal: Dict[str, Any],
    deception_score: float = 0.0,
    peer_reviews: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Validate proposal consistency using safety metrics."""
    tool = proposal_consistency_tool()
    return tool.check_proposal(proposal, deception_score, peer_reviews)


def score_improvement_hypothesis(
    hypothesis: Dict[str, Any],
    evidence_quality: float = 0.5,
    safety_impact: float = 0.5
) -> float:
    """Score an improvement hypothesis for quality."""
    tool = hypothesis_scoring_tool()
    return tool.score_hypothesis(hypothesis, evidence_quality, safety_impact)


def filter_safe_training_examples(proposals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter training data to keep only safe, high-quality proposals."""
    tool = safe_training_data_filter_tool()
    kept, _ = tool.filter_proposals(proposals)
    return kept


def group_similar_proposals(proposals: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
    """Group similar proposals together to avoid redundancy."""
    tool = proposal_deduplication_tool()
    return tool.deduplicate_proposals(proposals)


def select_best_from_groups(
    groups: Dict[int, List[Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    """Select best proposal from each group based on safety and quality."""
    tool = proposal_deduplication_tool()
    return tool.get_best_proposals(groups)

