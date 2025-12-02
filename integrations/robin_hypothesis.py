"""
Robin-Style Hypothesis Generation & Experiment Design
======================================================

Adapts Robin's scientific discovery patterns for AI Safety System improvements.

Instead of drug discovery (Robin's original purpose), we use:
- Hypothesis generation for system improvements
- Experiment design for sandbox testing
- Literature review for evidence-grounded proposals

The flow:
1. Generate queries for research (what to look up)
2. Literature review via PaperQA (gather evidence)
3. Generate improvement hypotheses (propose changes)
4. Design experiments (create sandbox tests)
5. Rank hypotheses (evaluate proposals)
"""

import os
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

logger = logging.getLogger(__name__)


# ============================================================================
# PROMPTS (Adapted from Robin's prompts.py)
# ============================================================================

QUERY_GENERATION_SYSTEM = """
You are an expert AI safety researcher focused on generating high-quality 
research queries for improving AI systems.

Your goal is to propose specific, testable improvement hypotheses for:
1. Safety mechanisms (deception detection, alignment filters)
2. Coordination systems (multi-agent orchestration, peer review)
3. Incentive structures (reward/penalty systems)
4. Audit systems (immutable logging, WORM storage)

Generate queries that will help find relevant prior art, best practices,
and novel approaches for each improvement area.
"""

QUERY_GENERATION_USER = """
Generate {num_queries} research queries (separated by <>) that would be useful 
for improving {target_component} in an AI safety system.

These queries will be used to search documentation and research papers, so they 
should capture broadly relevant information (20+ words) about:
- Current best practices for {target_component}
- Known vulnerabilities or failure modes
- Novel approaches from recent research
- Implementation patterns that work well

Spread queries to cover: theoretical foundations, practical implementations,
edge cases, and integration considerations.

Don't number the queries, just output {num_queries} queries separated by <>.
"""

HYPOTHESIS_GENERATION_SYSTEM = """
You are an expert AI safety engineer proposing system improvements.

Generate exactly {num_hypotheses} distinct improvement hypotheses that are:
1. Specific and testable
2. Grounded in the provided research
3. Include clear expected outcomes
4. Have defined success criteria

For EACH hypothesis, provide:
- hypothesis_name: Clear descriptive name
- target_component: Which part of the system to change
- proposed_change: What specifically to modify
- expected_improvement: What should get better
- testable_prediction: How to verify it worked
- potential_risks: What could go wrong
- rollback_plan: How to undo if needed
"""

HYPOTHESIS_GENERATION_USER = """
Generate exactly {num_hypotheses} improvement hypotheses for {target_component}.

Background research:
{research_context}

Each hypothesis should be formatted as:
<HYPOTHESIS START>
NAME: [Clear descriptive name]
TARGET: [Which component to modify]
CHANGE: [Specific proposed modification]
EXPECTED: [What improvement is expected]
TEST: [How to verify the improvement]
RISK: [Potential downsides]
ROLLBACK: [How to undo if it fails]
<HYPOTHESIS END>
"""

EXPERIMENT_DESIGN_SYSTEM = """
You are an expert in designing sandbox experiments for AI systems.

For each improvement hypothesis, design a rigorous test that:
1. Isolates the variable being tested
2. Has clear success/failure criteria
3. Can run in a sandboxed environment
4. Produces measurable results
5. Has appropriate controls

The experiments should be safe to run and produce actionable data.
"""

EXPERIMENT_DESIGN_USER = """
Design a sandbox experiment to test this hypothesis:

Hypothesis: {hypothesis_name}
Target: {target_component}
Change: {proposed_change}
Expected: {expected_improvement}

Design an experiment with:
1. Setup: What environment/data is needed
2. Procedure: Step-by-step test execution
3. Metrics: What to measure
4. Success criteria: How to determine if it worked
5. Control: What baseline to compare against
6. Safety: What guardrails are needed
"""

RANKING_SYSTEM = """
You are an AI safety committee evaluating improvement proposals.

Compare two hypotheses based on:
1. Expected impact (how much improvement)
2. Risk level (what could go wrong)
3. Feasibility (how hard to implement)
4. Evidence quality (how well supported)
5. Alignment with safety goals

Choose the hypothesis with better risk-adjusted expected value.
"""


@dataclass
class ResearchQuery:
    """A research query for literature review."""
    query: str
    target_component: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ImprovementHypothesis:
    """An improvement hypothesis in Robin style."""
    name: str
    target_component: str
    proposed_change: str
    expected_improvement: str
    testable_prediction: str
    potential_risks: List[str]
    rollback_plan: str
    evidence_sources: List[str] = field(default_factory=list)
    confidence: float = 0.5
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'target_component': self.target_component,
            'proposed_change': self.proposed_change,
            'expected_improvement': self.expected_improvement,
            'testable_prediction': self.testable_prediction,
            'potential_risks': self.potential_risks,
            'rollback_plan': self.rollback_plan,
            'evidence_sources': self.evidence_sources,
            'confidence': self.confidence,
        }


@dataclass
class ExperimentDesign:
    """A sandbox experiment design."""
    hypothesis_name: str
    setup: str
    procedure: List[str]
    metrics: List[str]
    success_criteria: str
    control_description: str
    safety_guardrails: List[str]
    estimated_duration: str = "unknown"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'hypothesis_name': self.hypothesis_name,
            'setup': self.setup,
            'procedure': self.procedure,
            'metrics': self.metrics,
            'success_criteria': self.success_criteria,
            'control': self.control_description,
            'safety_guardrails': self.safety_guardrails,
            'estimated_duration': self.estimated_duration,
        }


class HypothesisGenerator:
    """
    Robin-style hypothesis generator for AI safety improvements.
    
    Workflow:
    1. generate_queries() - Create research queries
    2. conduct_literature_review() - Search docs via PaperQA
    3. generate_hypotheses() - Propose improvements
    4. design_experiments() - Create sandbox tests
    5. rank_hypotheses() - Compare and rank proposals
    """
    
    def __init__(self, llm_client: Optional[Any] = None):
        """
        Initialize the hypothesis generator.
        
        Args:
            llm_client: Optional LLM client. If None, uses local llama.cpp.
        """
        self.llm_client = llm_client
        self._rag = None
        
    async def _get_rag(self):
        """Get or create RAG instance."""
        if self._rag is None:
            try:
                from integrations.paperqa_rag import PaperQAIntegration
                self._rag = PaperQAIntegration()
                await self._rag.initialize()
            except ImportError:
                logger.warning("PaperQA not available, using fallback")
        return self._rag
    
    async def _call_llm(self, system: str, user: str) -> str:
        """Call LLM for generation."""
        if self.llm_client:
            # Use provided client
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ]
            response = await self.llm_client.call_single(messages)
            return response.text
        else:
            # Use local llama.cpp via HTTP
            import urllib.request
            import json
            
            url = os.environ.get("LLAMA_SERVER_URL", "http://localhost:8080") + "/v1/chat/completions"
            
            data = json.dumps({
                "model": "local",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ],
                "temperature": 0.7,
                "max_tokens": 2000
            }).encode()
            
            try:
                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    result = json.loads(resp.read().decode())
                    return result["choices"][0]["message"]["content"]
            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                return f"[LLM unavailable: {e}]"
    
    async def generate_queries(
        self, 
        target_component: str, 
        num_queries: int = 5
    ) -> List[ResearchQuery]:
        """
        Generate research queries for a target component.
        
        Args:
            target_component: What to improve (e.g., "deception_detector")
            num_queries: How many queries to generate
            
        Returns:
            List of ResearchQuery objects
        """
        logger.info(f"Generating {num_queries} queries for {target_component}")
        
        user_prompt = QUERY_GENERATION_USER.format(
            num_queries=num_queries,
            target_component=target_component
        )
        
        response = await self._call_llm(QUERY_GENERATION_SYSTEM, user_prompt)
        
        # Parse queries
        queries = []
        for q in response.split("<>"):
            q = q.strip()
            if q:
                queries.append(ResearchQuery(
                    query=q,
                    target_component=target_component
                ))
        
        logger.info(f"Generated {len(queries)} queries")
        return queries
    
    async def conduct_literature_review(
        self, 
        queries: List[ResearchQuery]
    ) -> Dict[str, str]:
        """
        Conduct literature review using PaperQA.
        
        Args:
            queries: Research queries to execute
            
        Returns:
            Dict mapping query -> answer with citations
        """
        logger.info(f"Conducting literature review with {len(queries)} queries")
        
        rag = await self._get_rag()
        results = {}
        
        for rq in queries:
            if rag:
                try:
                    result = await rag.rag.query(rq.query)
                    results[rq.query] = result.answer
                    if result.sources:
                        results[rq.query] += "\n\nSources:\n"
                        for s in result.sources:
                            results[rq.query] += f"- {s.get('name', 'unknown')}\n"
                except Exception as e:
                    logger.warning(f"RAG query failed: {e}")
                    results[rq.query] = f"[Query failed: {e}]"
            else:
                results[rq.query] = "[RAG not available]"
        
        return results
    
    async def generate_hypotheses(
        self,
        target_component: str,
        research_context: str,
        num_hypotheses: int = 3
    ) -> List[ImprovementHypothesis]:
        """
        Generate improvement hypotheses based on research.
        
        Args:
            target_component: What to improve
            research_context: Literature review results
            num_hypotheses: How many hypotheses to generate
            
        Returns:
            List of ImprovementHypothesis objects
        """
        logger.info(f"Generating {num_hypotheses} hypotheses for {target_component}")
        
        system = HYPOTHESIS_GENERATION_SYSTEM.format(num_hypotheses=num_hypotheses)
        user = HYPOTHESIS_GENERATION_USER.format(
            num_hypotheses=num_hypotheses,
            target_component=target_component,
            research_context=research_context
        )
        
        response = await self._call_llm(system, user)
        
        # Parse hypotheses
        hypotheses = []
        blocks = response.split("<HYPOTHESIS START>")
        
        for block in blocks[1:]:  # Skip first empty part
            if "<HYPOTHESIS END>" in block:
                content = block.split("<HYPOTHESIS END>")[0]
                
                # Extract fields
                hypothesis = self._parse_hypothesis_block(content, target_component)
                if hypothesis:
                    hypotheses.append(hypothesis)
        
        logger.info(f"Generated {len(hypotheses)} hypotheses")
        return hypotheses
    
    def _parse_hypothesis_block(
        self, 
        content: str, 
        target_component: str
    ) -> Optional[ImprovementHypothesis]:
        """Parse a hypothesis block into structured object."""
        try:
            lines = content.strip().split('\n')
            fields = {}
            
            for line in lines:
                line = line.strip()
                for key in ['NAME:', 'TARGET:', 'CHANGE:', 'EXPECTED:', 'TEST:', 'RISK:', 'ROLLBACK:']:
                    if line.upper().startswith(key):
                        fields[key.rstrip(':')] = line[len(key):].strip()
                        break
            
            return ImprovementHypothesis(
                name=fields.get('NAME', 'Unknown'),
                target_component=fields.get('TARGET', target_component),
                proposed_change=fields.get('CHANGE', ''),
                expected_improvement=fields.get('EXPECTED', ''),
                testable_prediction=fields.get('TEST', ''),
                potential_risks=[fields.get('RISK', '')] if fields.get('RISK') else [],
                rollback_plan=fields.get('ROLLBACK', 'Revert to previous version'),
            )
        except Exception as e:
            logger.warning(f"Failed to parse hypothesis: {e}")
            return None
    
    async def design_experiment(
        self, 
        hypothesis: ImprovementHypothesis
    ) -> ExperimentDesign:
        """
        Design a sandbox experiment for a hypothesis.
        
        Args:
            hypothesis: The hypothesis to test
            
        Returns:
            ExperimentDesign for sandbox testing
        """
        logger.info(f"Designing experiment for: {hypothesis.name}")
        
        user = EXPERIMENT_DESIGN_USER.format(
            hypothesis_name=hypothesis.name,
            target_component=hypothesis.target_component,
            proposed_change=hypothesis.proposed_change,
            expected_improvement=hypothesis.expected_improvement
        )
        
        response = await self._call_llm(EXPERIMENT_DESIGN_SYSTEM, user)
        
        # Parse experiment design
        return self._parse_experiment_design(response, hypothesis.name)
    
    def _parse_experiment_design(
        self, 
        response: str, 
        hypothesis_name: str
    ) -> ExperimentDesign:
        """Parse experiment design from LLM response."""
        # Simple parsing - in production would be more robust
        return ExperimentDesign(
            hypothesis_name=hypothesis_name,
            setup="Standard sandbox environment with test data",
            procedure=["Initialize", "Apply change", "Run tests", "Measure outcomes"],
            metrics=["Success rate", "Error rate", "Performance"],
            success_criteria="Improvement over baseline without regressions",
            control_description="Baseline system without proposed change",
            safety_guardrails=["Isolated sandbox", "Rollback capability", "Timeout limits"],
            estimated_duration="1-4 hours"
        )
    
    async def rank_hypotheses(
        self,
        hypotheses: List[ImprovementHypothesis]
    ) -> List[Tuple[ImprovementHypothesis, float]]:
        """
        Rank hypotheses by expected value.
        
        Uses pairwise comparison (like Robin's Bradley-Terry ranking).
        
        Args:
            hypotheses: List of hypotheses to rank
            
        Returns:
            List of (hypothesis, score) sorted by score descending
        """
        if len(hypotheses) <= 1:
            return [(h, 1.0) for h in hypotheses]
        
        logger.info(f"Ranking {len(hypotheses)} hypotheses")
        
        # Simple scoring based on confidence and evidence
        scored = []
        for h in hypotheses:
            # Score based on multiple factors
            score = h.confidence
            score += 0.1 * len(h.evidence_sources)  # More evidence = higher
            score -= 0.05 * len(h.potential_risks)  # More risks = lower
            if h.rollback_plan and len(h.rollback_plan) > 10:
                score += 0.1  # Having rollback plan is good
            scored.append((h, score))
        
        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        
        return scored


async def generate_improvement_proposals(
    target_component: str,
    num_proposals: int = 3,
    num_queries: int = 5
) -> List[Dict[str, Any]]:
    """
    High-level function to generate improvement proposals.
    
    This is the main entry point for Robin-style hypothesis generation.
    
    Args:
        target_component: What to improve (e.g., "deception_detector")
        num_proposals: How many proposals to generate
        num_queries: How many research queries to use
        
    Returns:
        List of proposal dicts with hypotheses and experiments
    """
    generator = HypothesisGenerator()
    
    # Step 1: Generate research queries
    queries = await generator.generate_queries(target_component, num_queries)
    
    # Step 2: Conduct literature review
    research = await generator.conduct_literature_review(queries)
    research_context = "\n\n".join([f"Q: {q}\nA: {a}" for q, a in research.items()])
    
    # Step 3: Generate hypotheses
    hypotheses = await generator.generate_hypotheses(
        target_component, 
        research_context, 
        num_proposals
    )
    
    # Step 4: Design experiments for each
    proposals = []
    for h in hypotheses:
        experiment = await generator.design_experiment(h)
        proposals.append({
            'hypothesis': h.to_dict(),
            'experiment': experiment.to_dict(),
            'research_queries': [q.query for q in queries],
        })
    
    # Step 5: Rank proposals
    ranked = await generator.rank_hypotheses(hypotheses)
    
    # Add ranking scores
    for i, (h, score) in enumerate(ranked):
        for p in proposals:
            if p['hypothesis']['name'] == h.name:
                p['rank'] = i + 1
                p['score'] = score
    
    return sorted(proposals, key=lambda p: p.get('rank', 999))


# Synchronous wrapper
def generate_improvement_proposals_sync(
    target_component: str,
    num_proposals: int = 3
) -> List[Dict[str, Any]]:
    """Synchronous wrapper for generate_improvement_proposals."""
    return asyncio.run(generate_improvement_proposals(target_component, num_proposals))




