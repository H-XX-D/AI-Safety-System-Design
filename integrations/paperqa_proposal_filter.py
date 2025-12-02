"""
PaperQA Proposal Filter
=======================

Uses PaperQA AI to filter out useless proposals before they reach the orchestrator.

PaperQA acts as an intelligent gatekeeper that can:
- Detect redundant proposals
- Evaluate proposal usefulness
- Check evidence quality
- Short-circuit proposals that don't add value

This saves computational resources by filtering proposals early.
"""

import asyncio
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class PaperQAProposalFilter:
    """
    Filter proposals using PaperQA AI evaluation.
    
    PaperQA evaluates proposals and can short-circuit useless ones
    before they go through expensive orchestrator processing.
    """
    
    def __init__(self):
        self._paperqa = None
    
    def _get_paperqa(self):
        """Lazy load PaperQA."""
        if self._paperqa is None:
            try:
                from integrations.paperqa_rag import PaperQAIntegration, get_rag
                # Use the integration class which has the evaluation methods
                self._paperqa = None  # Will use get_rag() async
            except ImportError:
                logger.warning("PaperQAIntegration not available")
                return None
        return self._paperqa
    
    async def _get_paperqa_async(self):
        """Get PaperQA integration asynchronously."""
        try:
            from integrations.paperqa_rag import get_rag
            return await get_rag()
        except ImportError:
            logger.warning("PaperQAIntegration not available")
            return None
    
    async def filter_proposal(
        self,
        proposal: Dict[str, Any],
        filter_redundant: bool = True,
        filter_low_evidence: bool = False,  # Default: Don't filter low evidence (allow innovation)
        min_evidence_quality: float = 0.3,  # Lower threshold (allow more through)
        strict_mode: bool = False  # Strict mode for production, lenient for experimentation
    ) -> Dict[str, Any]:
        """
        Filter a proposal using PaperQA evaluation.
        
        Args:
            proposal: Proposal dict to evaluate
            filter_redundant: Whether to filter redundant proposals
            filter_low_evidence: Whether to filter low-evidence proposals
            min_evidence_quality: Minimum evidence quality score (0-1)
            
        Returns:
            Dict with:
            - passed: bool - Whether proposal passed filter
            - filtered: bool - Whether proposal was filtered out
            - reason: str - Why it was filtered (if filtered)
            - evaluation: Dict - Full PaperQA evaluation
            - evidence_requested: List[str] - What evidence would make it pass
            - gate_to_counter: str - Specific barrier that needs addressing
            - actionable_feedback: Dict - How to improve the proposal
        """
        paperqa = await self._get_paperqa_async()
        if not paperqa:
            # If PaperQA not available, allow proposal through
            return {
                'passed': True,
                'filtered': False,
                'reason': 'PaperQA not available',
                'evaluation': {},
                'evidence_requested': [],
                'gate_to_counter': None,
                'actionable_feedback': {'status': 'bypassed', 'reason': 'PaperQA unavailable'}
            }
        
        # Evaluate proposal usefulness
        evaluation = await paperqa.evaluate_proposal_usefulness(proposal)
        
        # Check redundancy if enabled
        # Only filter if highly redundant (similarity > 0.8) to allow variations
        if filter_redundant:
            redundancy_check = await paperqa.check_proposal_redundancy(proposal)
            similarity = redundancy_check.get('similarity_score', 0.0)
            is_redundant = redundancy_check.get('is_redundant', False)
            
            # Only filter if highly redundant (similarity > 0.8)
            # This allows variations and improvements on existing ideas
            if is_redundant and similarity > 0.8:
                similar_proposals = redundancy_check.get('similar_proposals', [])
                return {
                    'passed': False,
                    'filtered': True,
                    'reason': f"Highly redundant proposal (similarity: {similarity:.2f}): {redundancy_check.get('reasoning', 'Very similar proposals exist')}",
                    'evaluation': evaluation,
                    'redundancy': redundancy_check,
                    'evidence_requested': [
                        f"Explain how this differs from: {', '.join(similar_proposals[:3])}",
                        "Provide specific improvements over existing approaches",
                        "Demonstrate unique value proposition"
                    ],
                    'gate_to_counter': f"Redundancy gate: Must show differentiation from existing proposals (similarity threshold: 0.8, current: {similarity:.2f})",
                    'actionable_feedback': {
                        'issue': 'high_redundancy',
                        'current_similarity': similarity,
                        'required_similarity': 0.8,
                        'action': 'Modify proposal to show clear differentiation from existing approaches',
                        'examples': similar_proposals[:3]
                    }
                }
            elif is_redundant:
                # Low similarity redundancy - allow through with warning
                logger.info(f"Proposal has some redundancy (similarity: {similarity:.2f}) but allowing through")
        
        # Check evidence quality if enabled (only in strict mode)
        if filter_low_evidence and strict_mode:
            evidence_quality = evaluation.get('evidence_quality', 0.0)
            if evidence_quality < min_evidence_quality:
                return {
                    'passed': False,
                    'filtered': True,
                    'reason': f"Low evidence quality: {evidence_quality:.2f} < {min_evidence_quality:.2f}",
                    'evaluation': evaluation,
                    'evidence_requested': [
                        "Provide research citations supporting the approach",
                        "Include testable predictions or hypotheses",
                        "Reference similar successful implementations",
                        "Add quantitative metrics or benchmarks"
                    ],
                    'gate_to_counter': f"Evidence gate: Must achieve evidence quality >= {min_evidence_quality:.2f} (current: {evidence_quality:.2f})",
                    'actionable_feedback': {
                        'issue': 'low_evidence',
                        'current_quality': evidence_quality,
                        'required_quality': min_evidence_quality,
                        'action': 'Add supporting research, citations, or testable predictions',
                        'suggestions': [
                            'Search PaperQA for related research',
                            'Cite relevant papers or implementations',
                            'Provide experimental results or benchmarks'
                        ]
                    }
                }
        
        # Check overall usefulness (only filter if clearly not useful AND strict mode)
        # In lenient mode, allow proposals through even if usefulness is unclear
        if strict_mode and not evaluation.get('useful', True):
            # Only filter if confidence is high that it's not useful
            confidence = evaluation.get('confidence', 0.5)
            if confidence > 0.7:  # High confidence it's not useful
                reasoning = evaluation.get('reasoning', 'No clear value')
                return {
                    'passed': False,
                    'filtered': True,
                    'reason': f"Proposal not useful (high confidence): {reasoning}",
                    'evaluation': evaluation,
                    'evidence_requested': [
                        "Demonstrate clear value proposition",
                        "Show measurable improvements",
                        "Explain why this is better than alternatives",
                        "Provide use cases or examples"
                    ],
                    'gate_to_counter': f"Usefulness gate: Must demonstrate clear value (confidence threshold: 0.7, current evaluation confidence: {confidence:.2f})",
                    'actionable_feedback': {
                        'issue': 'low_usefulness',
                        'current_confidence': confidence,
                        'required_confidence': 0.7,
                        'action': 'Clarify value proposition and provide concrete benefits',
                        'suggestions': [
                            'Quantify expected improvements',
                            'Compare with existing solutions',
                            'Provide specific use cases',
                            'Explain unique advantages'
                        ],
                        'paperqa_reasoning': reasoning
                    }
                }
        
        # Proposal passed filter
        # Check if proposal was inventive (not redundant, novel approach)
        redundancy_score = evaluation.get('redundancy_score', 0.0)
        is_inventive = redundancy_score < 0.3  # Low redundancy = inventive
        
        return {
            'passed': True,
            'filtered': False,
            'reason': 'Proposal passed PaperQA filter',
            'evaluation': evaluation,
            'evidence_requested': [],  # No additional evidence needed
            'gate_to_counter': None,  # No gates to counter
            'paperqa_not_countered': True,  # Idea is good enough - on the right track
            'is_inventive': is_inventive,
            # NOTE: Removed 'solves_research_problem' - can be gamed, not verifiable
            'actionable_feedback': {
                'status': 'approved',
                'suggestions': [
                    'Consider adding more evidence to strengthen the proposal',
                    'Review similar proposals for additional insights'
                ] if evaluation.get('evidence_quality', 0.5) < 0.7 else []
            }
        }
    
    def filter_proposal_sync(
        self,
        proposal: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """Synchronous wrapper."""
        return asyncio.run(self.filter_proposal(proposal, **kwargs))


# Global filter instance
_filter_instance: Optional[PaperQAProposalFilter] = None

def get_proposal_filter() -> PaperQAProposalFilter:
    """Get or create the global proposal filter."""
    global _filter_instance
    if _filter_instance is None:
        _filter_instance = PaperQAProposalFilter()
    return _filter_instance


async def filter_proposal_with_paperqa(
    proposal: Dict[str, Any],
    filter_redundant: bool = True,
    filter_low_evidence: bool = True
) -> Dict[str, Any]:
    """
    Filter a proposal using PaperQA AI.
    
    This is the main function agents/orchestrator should call.
    
    Args:
        proposal: Proposal to filter
        filter_redundant: Filter redundant proposals
        filter_low_evidence: Filter low-evidence proposals
        
    Returns:
        Filter result dict
    """
    filter_tool = get_proposal_filter()
    return await filter_tool.filter_proposal(
        proposal,
        filter_redundant=filter_redundant,
        filter_low_evidence=filter_low_evidence
    )


def filter_proposal_sync(proposal: Dict[str, Any]) -> Dict[str, Any]:
    """Synchronous wrapper for filtering."""
    return asyncio.run(filter_proposal_with_paperqa(proposal))

