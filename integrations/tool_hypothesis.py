"""
Hypothesis Generation Tool
==========================

A tool that AI agents can call to generate improvement hypotheses.

Usage by agent:
    result = hypothesis_tool.generate(
        target="deception_detector",
        goal="improve detection accuracy"
    )
"""

import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class HypothesisResult:
    """Result from hypothesis generation tool."""
    name: str
    target_component: str
    proposed_change: str
    expected_outcome: str
    testable_prediction: str
    confidence: float
    evidence_summary: str
    risks: List[str]
    rollback_plan: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class HypothesisTool:
    """
    Tool for AI agents to generate improvement hypotheses.
    
    This is called by agents when they want to propose improvements.
    The tool:
    1. Takes a target component and improvement goal
    2. Searches for relevant evidence (via RAG)
    3. Generates structured hypothesis
    4. Returns actionable proposal
    
    Example:
        tool = HypothesisTool()
        result = await tool.generate(
            target="alignment_filter",
            goal="reduce false positives"
        )
    """
    
    name = "hypothesis_generator"
    description = """Generate an improvement hypothesis for a system component.
    
    Input:
    - target: Which component to improve (e.g., "deception_detector", "alignment_filter")
    - goal: What improvement to achieve (e.g., "improve accuracy", "reduce latency")
    - context: Optional additional context
    
    Output:
    - Structured hypothesis with proposed change, expected outcome, and testable prediction
    """
    
    def __init__(self):
        self._rag = None
        self._initialized = False
    
    async def _ensure_initialized(self):
        """Lazy initialization of RAG."""
        if not self._initialized:
            try:
                from integrations.paperqa_rag import PaperQAIntegration
                self._rag = PaperQAIntegration()
                await self._rag.initialize()
            except ImportError:
                pass  # RAG not available
            self._initialized = True
    
    async def generate(
        self,
        target: str,
        goal: str,
        context: Optional[str] = None,
        num_hypotheses: int = 1
    ) -> List[HypothesisResult]:
        """
        Generate improvement hypothesis(es).
        
        Args:
            target: Component to improve
            goal: What to achieve
            context: Additional context
            num_hypotheses: How many to generate
            
        Returns:
            List of HypothesisResult objects
        """
        await self._ensure_initialized()
        
        # Step 1: Gather evidence
        evidence = await self._gather_evidence(target, goal)
        
        # Step 2: Generate hypothesis
        hypotheses = await self._generate_hypotheses(
            target, goal, evidence, context, num_hypotheses
        )
        
        return hypotheses
    
    async def _gather_evidence(self, target: str, goal: str) -> str:
        """Gather evidence from RAG."""
        if not self._rag:
            return "[No evidence available - RAG not initialized]"
        
        queries = [
            f"Best practices for {target} in AI systems",
            f"How to {goal} in {target}",
            f"Common issues with {target} implementations",
        ]
        
        evidence_parts = []
        for q in queries:
            try:
                result = await self._rag.rag.query(q)
                evidence_parts.append(f"Q: {q}\nA: {result.answer}")
            except Exception:
                pass
        
        return "\n\n".join(evidence_parts) if evidence_parts else "[No evidence found]"
    
    async def _generate_hypotheses(
        self,
        target: str,
        goal: str,
        evidence: str,
        context: Optional[str],
        num: int
    ) -> List[HypothesisResult]:
        """Generate hypotheses using LLM."""
        # For now, generate template hypotheses
        # In production, would call local LLM
        
        hypotheses = []
        for i in range(num):
            h = HypothesisResult(
                name=f"Improve {target}: {goal}",
                target_component=target,
                proposed_change=f"Modify {target} to achieve {goal}",
                expected_outcome=f"Improved {goal} for {target}",
                testable_prediction=f"Measurable improvement in {goal} metrics",
                confidence=0.7,
                evidence_summary=evidence[:500] if evidence else "No evidence",
                risks=[f"May affect {target} performance", "Requires testing"],
                rollback_plan=f"Revert {target} to previous version"
            )
            hypotheses.append(h)
        
        return hypotheses
    
    def generate_sync(
        self,
        target: str,
        goal: str,
        context: Optional[str] = None
    ) -> List[HypothesisResult]:
        """Synchronous wrapper."""
        import asyncio
        return asyncio.run(self.generate(target, goal, context))
    
    # Tool interface for agent frameworks
    def __call__(self, target: str, goal: str, **kwargs) -> str:
        """Callable interface for tool frameworks."""
        results = self.generate_sync(target, goal, kwargs.get('context'))
        return json.dumps([r.to_dict() for r in results], indent=2)


# Global tool instance
_hypothesis_tool: Optional[HypothesisTool] = None

def get_hypothesis_tool() -> HypothesisTool:
    """Get or create the hypothesis tool."""
    global _hypothesis_tool
    if _hypothesis_tool is None:
        _hypothesis_tool = HypothesisTool()
    return _hypothesis_tool


# Simple function interface for agents
async def generate_hypothesis(target: str, goal: str) -> Dict[str, Any]:
    """
    Simple function for agents to generate a hypothesis.
    
    Args:
        target: What to improve (e.g., "deception_detector")
        goal: What to achieve (e.g., "improve accuracy")
        
    Returns:
        Dict with hypothesis details
    """
    tool = get_hypothesis_tool()
    results = await tool.generate(target, goal, num_hypotheses=1)
    return results[0].to_dict() if results else {}


def generate_hypothesis_sync(target: str, goal: str) -> Dict[str, Any]:
    """Synchronous version of generate_hypothesis."""
    import asyncio
    return asyncio.run(generate_hypothesis(target, goal))






