#!/usr/bin/env python3
"""
Phi Research Runner - Let Phi-3.5-mini conduct research like a human.

This script guides Phi through the 10-stage research workflow:
1. IDEA - Start with question/hypothesis
2. BROAD SEARCH - Gather papers via PaperQA
3. TRIAGE - Quick scan, mark standouts
4. DEEP DIVE - In-depth notes on standouts
5. SYNTHESIS - Compile notes into summary
6. HYPOTHESIS - Refine based on evidence
7. EXPERIMENT DESIGN - Design test
8. EXECUTION - Run experiment
9. ANALYSIS - Interpret results
10. CONCLUSION - Accept/reject/revise

Usage:
    python phi_research_runner.py --topic "emotion detection for AI safety"
    python phi_research_runner.py --resume emotion_detection_study
    python phi_research_runner.py --interactive
"""

import os
import sys
import json
import time
import argparse
import requests
from typing import Dict, List, Any, Optional
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.research_workflow import ResearchWorkflow, ResearchStage, PaperEntry


class PhiClient:
    """Client for talking to Phi-3.5-mini via llama.cpp server."""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.system_prompt = """You are a research scientist conducting rigorous academic research.

Your task is to follow the scientific method:
1. Form hypotheses based on evidence
2. Design experiments to test them
3. Be honest about limitations and uncertainties
4. Cite sources for all claims

When analyzing papers, extract:
- Key findings (specific, quantitative when possible)
- Methodology strengths and weaknesses
- Relevance to the research question
- Limitations and gaps

When generating hypotheses:
- Be specific and testable
- Define clear variables
- Make falsifiable predictions

When designing experiments:
- Specify step-by-step procedure
- Define success criteria
- Anticipate potential issues"""
    
    def generate(self, prompt: str, max_tokens: int = 1000, temperature: float = 0.7) -> str:
        """Generate response from Phi."""
        try:
            response = requests.post(
                f"{self.base_url}/completion",
                json={
                    "prompt": f"<|system|>\n{self.system_prompt}<|end|>\n<|user|>\n{prompt}<|end|>\n<|assistant|>\n",
                    "n_predict": max_tokens,
                    "temperature": temperature,
                    "stop": ["<|end|>", "<|user|>"]
                },
                timeout=120
            )
            response.raise_for_status()
            return response.json().get("content", "").strip()
        except Exception as e:
            print(f"[ERROR] Phi generation failed: {e}")
            return ""
    
    def generate_json(self, prompt: str, max_tokens: int = 1500) -> Dict[str, Any]:
        """Generate JSON response from Phi."""
        json_prompt = f"""{prompt}

Respond with valid JSON only. No other text."""
        
        response = self.generate(json_prompt, max_tokens=max_tokens, temperature=0.3)
        
        # Try to extract JSON
        try:
            # Find JSON in response
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            pass
        
        # Try array
        try:
            start = response.find('[')
            end = response.rfind(']') + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            pass
        
        return {}


class PaperQAClient:
    """Client for PaperQA research API."""
    
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url
    
    def search(self, query: str, max_results: int = 20) -> List[Dict[str, Any]]:
        """Search for papers."""
        try:
            response = requests.post(
                f"{self.base_url}/api/research/search",
                json={"query": query, "max_results": max_results},
                timeout=60
            )
            response.raise_for_status()
            return response.json().get("results", [])
        except Exception as e:
            print(f"[WARNING] PaperQA search failed: {e}")
            return self._mock_search(query, max_results)
    
    def get_paper_details(self, paper_id: str) -> Dict[str, Any]:
        """Get detailed paper info."""
        try:
            response = requests.get(
                f"{self.base_url}/api/research/paper/{paper_id}",
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[WARNING] Paper details failed: {e}")
            return {}
    
    def _mock_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Mock search results for testing without PaperQA."""
        # Generate mock papers based on query
        mock_papers = [
            {
                "id": f"arxiv:2301.{10000 + i}",
                "title": f"Study on {query.title()} - Approach {i+1}",
                "authors": [f"Author{j}" for j in range(1, 4)],
                "year": 2023,
                "abstract": f"This paper investigates {query} using novel methods. We achieve significant improvements over baselines.",
                "source": "arxiv"
            }
            for i in range(min(max_results, 10))
        ]
        return mock_papers


class PhiResearchRunner:
    """
    Orchestrates Phi through the research workflow.
    
    Each stage is interactive - Phi processes, human can review/adjust.
    """
    
    def __init__(
        self,
        research_id: str,
        base_dir: str = "./data/research_projects",
        phi_url: str = "http://localhost:8080",
        paperqa_url: str = "http://localhost:5000",
        interactive: bool = True
    ):
        self.research_id = research_id
        self.interactive = interactive
        
        # Initialize clients
        self.phi = PhiClient(phi_url)
        self.paperqa = PaperQAClient(paperqa_url)
        
        # Initialize or load research workflow
        self.workflow = ResearchWorkflow(
            research_id=research_id,
            base_dir=base_dir,
            paperqa_client=self.paperqa,
            llm_client=self.phi
        )
        
        print(f"\n{'='*60}")
        print(f"  PHI RESEARCH RUNNER")
        print(f"  Project: {research_id}")
        print(f"  Stage: {self.workflow.get_current_stage().value}")
        print(f"{'='*60}\n")
    
    def run(self, topic: str = None):
        """Run the research workflow from current stage."""
        stage = self.workflow.get_current_stage()
        
        if stage == ResearchStage.IDEA:
            if not topic:
                topic = input("Enter research topic: ").strip()
            self.stage_idea(topic)
        
        # Continue through stages
        while True:
            stage = self.workflow.get_current_stage()
            
            if stage == ResearchStage.BROAD_SEARCH:
                self.stage_broad_search()
            elif stage == ResearchStage.TRIAGE:
                self.stage_triage()
            elif stage == ResearchStage.DEEP_DIVE:
                self.stage_deep_dive()
            elif stage == ResearchStage.SYNTHESIS:
                self.stage_synthesis()
            elif stage == ResearchStage.HYPOTHESIS:
                self.stage_hypothesis()
            elif stage == ResearchStage.EXPERIMENT_DESIGN:
                self.stage_experiment_design()
            elif stage == ResearchStage.EXECUTION:
                self.stage_execution()
            elif stage == ResearchStage.ANALYSIS:
                self.stage_analysis()
            elif stage == ResearchStage.CONCLUSION:
                self.stage_conclusion()
                break
            
            if self.interactive:
                cont = input("\n[Press Enter to continue, 'q' to quit] ").strip().lower()
                if cont == 'q':
                    print("Saving progress and exiting...")
                    break
    
    # ========== STAGE 1: IDEA ==========
    
    def stage_idea(self, topic: str):
        """Stage 1: Generate initial research question and hypothesis."""
        print("\n" + "="*60)
        print("  STAGE 1: IDEA")
        print("="*60)
        
        # Ask Phi to formulate research question and hypothesis
        prompt = f"""You are starting a research project on: {topic}

Generate:
1. A specific, focused research question
2. An initial hypothesis (testable prediction)
3. Why this matters (significance)

Format as JSON:
{{
    "title": "Short title for the research",
    "question": "The specific research question",
    "hypothesis": "Initial testable hypothesis",
    "significance": "Why this research matters",
    "key_terms": ["term1", "term2", "term3"]
}}"""
        
        print("\n[Phi is formulating research question...]")
        result = self.phi.generate_json(prompt)
        
        if result:
            print(f"\n📋 RESEARCH SETUP:")
            print(f"   Title: {result.get('title', topic)}")
            print(f"   Question: {result.get('question', '')}")
            print(f"   Hypothesis: {result.get('hypothesis', '')}")
            print(f"   Significance: {result.get('significance', '')}")
            
            # Start the research
            self.workflow.start_research(
                title=result.get('title', topic),
                initial_question=result.get('question', f"How can {topic} improve AI systems?"),
                initial_hypothesis=result.get('hypothesis', '')
            )
            
            # Save key terms for search
            self._state_data = {'key_terms': result.get('key_terms', [topic])}
        else:
            # Fallback
            self.workflow.start_research(
                title=topic,
                initial_question=f"How can {topic} be applied to improve AI safety?",
                initial_hypothesis=f"{topic} can improve AI safety metrics"
            )
            self._state_data = {'key_terms': [topic]}
        
        print("\n✓ Research initialized. Moving to broad search...")
    
    # ========== STAGE 2: BROAD SEARCH ==========
    
    def stage_broad_search(self):
        """Stage 2: Gather papers from PaperQA."""
        print("\n" + "="*60)
        print("  STAGE 2: BROAD SEARCH")
        print("="*60)
        
        # Get search terms
        key_terms = getattr(self, '_state_data', {}).get('key_terms', [])
        question = self.workflow._state.get('initial_question', '')
        
        # Generate search queries
        prompt = f"""Based on this research question: {question}

Generate 5 different search queries to find relevant papers.
Each query should target different aspects of the topic.

Format as JSON array:
["query 1", "query 2", "query 3", "query 4", "query 5"]"""
        
        print("\n[Phi is generating search queries...]")
        queries = self.phi.generate_json(prompt)
        
        if not isinstance(queries, list):
            queries = key_terms + [question]
        
        print(f"\n🔍 SEARCH QUERIES:")
        for i, q in enumerate(queries[:5], 1):
            print(f"   {i}. {q}")
        
        # Search for papers
        all_papers = []
        for query in queries[:5]:
            print(f"\n[Searching: {query[:50]}...]")
            results = self.paperqa.search(query, max_results=15)
            all_papers.extend(results)
            time.sleep(0.5)  # Rate limiting
        
        # Deduplicate by title
        seen_titles = set()
        unique_papers = []
        for paper in all_papers:
            title = paper.get('title', '')
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_papers.append(paper)
        
        print(f"\n📚 FOUND {len(unique_papers)} UNIQUE PAPERS")
        
        # Add to workflow
        for paper in unique_papers:
            self.workflow.add_paper_to_broad_list(
                source=paper.get('id', paper.get('source', 'unknown')),
                title=paper.get('title', 'Untitled'),
                authors=paper.get('authors', []),
                abstract=paper.get('abstract', ''),
                year=paper.get('year')
            )
        
        print(f"\n✓ Added {len(unique_papers)} papers to broad list")
        print("   Moving to triage stage...")
    
    # ========== STAGE 3: TRIAGE ==========
    
    def stage_triage(self):
        """Stage 3: Quick scan papers, mark standouts."""
        print("\n" + "="*60)
        print("  STAGE 3: TRIAGE (Quick Scan)")
        print("="*60)
        
        papers = self.workflow.get_unread_papers()
        hypothesis = self.workflow._state.get('initial_question', '')
        
        print(f"\n📋 {len(papers)} papers to triage")
        print("   [Phi will quick-scan each paper and score relevance]")
        
        standout_count = 0
        
        for i, paper in enumerate(papers):
            print(f"\n--- Paper {i+1}/{len(papers)} ---")
            print(f"Title: {paper.title[:70]}...")
            
            # Ask Phi to evaluate
            prompt = f"""Quick-scan this paper for relevance to: {hypothesis}

Title: {paper.title}
Abstract: {paper.abstract[:500]}

Evaluate quickly:
1. Relevance score (0.0-1.0)
2. Brief notes (1-2 sentences)
3. Is this a standout worth deep reading? (true/false)
4. Tags (methodology, empirical, theoretical, review, etc.)

JSON format:
{{
    "relevance": 0.7,
    "notes": "Brief notes here",
    "standout": true,
    "tags": ["tag1", "tag2"]
}}"""
            
            result = self.phi.generate_json(prompt)
            
            if result:
                relevance = float(result.get('relevance', 0.5))
                notes = result.get('notes', 'No notes')
                is_standout = result.get('standout', False)
                tags = result.get('tags', [])
                
                # Mark high relevance as standout
                if relevance >= 0.7:
                    is_standout = True
                
                print(f"   Relevance: {relevance:.2f} {'⭐ STANDOUT' if is_standout else ''}")
                print(f"   Notes: {notes[:100]}")
                
                self.workflow.skim_paper(
                    paper_id=paper.id,
                    relevance_score=relevance,
                    quick_notes=notes,
                    tags=tags,
                    is_standout=is_standout
                )
                
                if is_standout:
                    standout_count += 1
            else:
                # Fallback - mark as medium relevance
                self.workflow.skim_paper(
                    paper_id=paper.id,
                    relevance_score=0.5,
                    quick_notes="Auto-triaged",
                    tags=[],
                    is_standout=False
                )
        
        stats = self.workflow.get_triage_stats()
        print(f"\n✓ TRIAGE COMPLETE")
        print(f"   Total: {stats['total_papers']}")
        print(f"   Standouts: {standout_count} ⭐")
        print(f"   Avg relevance: {stats['avg_relevance']:.2f}")
        
        self.workflow.finish_triage()
        print("\n   Moving to deep dive stage...")
    
    # ========== STAGE 4: DEEP DIVE ==========
    
    def stage_deep_dive(self):
        """Stage 4: In-depth notes on standout papers."""
        print("\n" + "="*60)
        print("  STAGE 4: DEEP DIVE")
        print("="*60)
        
        standouts = [p for p in self.workflow.get_standouts() if p.status != 'deep_read']
        hypothesis = self.workflow._state.get('initial_question', '')
        
        print(f"\n📚 {len(standouts)} standout papers to deep-read")
        
        for i, paper in enumerate(standouts):
            print(f"\n{'='*40}")
            print(f"DEEP READING {i+1}/{len(standouts)}")
            print(f"Title: {paper.title}")
            print(f"{'='*40}")
            
            # Ask Phi for detailed analysis
            prompt = f"""Deep-read this paper and extract detailed notes.

Research Question: {hypothesis}

Paper:
Title: {paper.title}
Authors: {', '.join(paper.authors)}
Abstract: {paper.abstract}
Quick Notes: {paper.quick_notes}

Extract:
1. Key findings (specific, quantitative if possible)
2. Key quotes (with page numbers if available)
3. Methodology notes
4. Limitations
5. How it relates to our hypothesis

JSON format:
{{
    "key_findings": [
        "Finding 1 with specific numbers",
        "Finding 2",
        "Finding 3"
    ],
    "key_quotes": [
        {{"text": "Quote text", "page": 5}},
        {{"text": "Another quote", "page": 12}}
    ],
    "methodology": "Description of methods used",
    "limitations": [
        "Limitation 1",
        "Limitation 2"
    ],
    "relevance_to_hypothesis": "How this paper supports or contradicts our hypothesis"
}}"""
            
            print("\n[Phi is analyzing paper in depth...]")
            result = self.phi.generate_json(prompt)
            
            if result:
                print(f"\n📝 KEY FINDINGS:")
                for finding in result.get('key_findings', [])[:5]:
                    print(f"   • {finding}")
                
                print(f"\n📖 RELEVANCE: {result.get('relevance_to_hypothesis', 'N/A')[:200]}")
                
                self.workflow.deep_read_paper(
                    paper_id=paper.id,
                    key_findings=result.get('key_findings', []),
                    key_quotes=result.get('key_quotes', []),
                    methodology_notes=result.get('methodology', ''),
                    limitations=result.get('limitations', []),
                    relevance_to_hypothesis=result.get('relevance_to_hypothesis', '')
                )
            else:
                print("[WARNING] Could not analyze paper, using quick notes")
                self.workflow.deep_read_paper(
                    paper_id=paper.id,
                    key_findings=[paper.quick_notes],
                    key_quotes=[],
                    methodology_notes="",
                    limitations=[],
                    relevance_to_hypothesis="See quick notes"
                )
        
        progress = self.workflow.get_deep_dive_progress()
        print(f"\n✓ DEEP DIVE COMPLETE")
        print(f"   Papers analyzed: {progress['deep_read']}")
        
        self.workflow.finish_deep_dive()
        print("\n   Moving to synthesis stage...")
    
    # ========== STAGE 5: SYNTHESIS ==========
    
    def stage_synthesis(self):
        """Stage 5: Compile notes into summary."""
        print("\n" + "="*60)
        print("  STAGE 5: SYNTHESIS")
        print("="*60)
        
        deep_papers = self.workflow.get_deep_read_papers()
        question = self.workflow._state.get('initial_question', '')
        
        # Gather all findings
        all_findings = []
        all_methods = []
        all_limitations = []
        
        for paper in deep_papers:
            all_findings.extend(paper.key_findings)
            if paper.methodology_notes:
                all_methods.append(paper.methodology_notes)
            all_limitations.extend(paper.limitations)
        
        # Ask Phi to synthesize
        prompt = f"""Synthesize these research findings into a coherent summary.

Research Question: {question}

Papers Reviewed: {len(deep_papers)}

Key Findings from Papers:
{chr(10).join(f'- {f}' for f in all_findings[:20])}

Methodologies Used:
{chr(10).join(f'- {m[:200]}' for m in all_methods[:10])}

Limitations Found:
{chr(10).join(f'- {l}' for l in all_limitations[:10])}

Create a synthesis that:
1. Summarizes the background
2. Identifies key themes and patterns
3. Notes gaps in the literature
4. Highlights contradictions
5. Draws implications for our research

JSON format:
{{
    "background": "Background summary paragraph",
    "key_findings": ["Theme 1", "Theme 2", "Theme 3"],
    "methodologies_reviewed": ["Method 1", "Method 2"],
    "gaps_identified": ["Gap 1", "Gap 2"],
    "contradictions": ["Contradiction 1"],
    "synthesis": "Main synthesis paragraph combining everything",
    "implications": ["Implication 1", "Implication 2"]
}}"""
        
        print("\n[Phi is synthesizing research...]")
        result = self.phi.generate_json(prompt)
        
        if result:
            print(f"\n📊 SYNTHESIS RESULTS:")
            print(f"\n   Background: {result.get('background', '')[:200]}...")
            
            print(f"\n   Key Themes:")
            for theme in result.get('key_findings', []):
                print(f"      • {theme}")
            
            print(f"\n   Gaps Identified:")
            for gap in result.get('gaps_identified', []):
                print(f"      • {gap}")
            
            print(f"\n   Implications:")
            for imp in result.get('implications', []):
                print(f"      • {imp}")
            
            # Create summary
            self.workflow.create_summary(
                title=f"Literature Review: {self.workflow._state.get('title', 'Research')}",
                background=result.get('background', ''),
                key_findings=result.get('key_findings', []),
                methodologies_reviewed=result.get('methodologies_reviewed', []),
                gaps_identified=result.get('gaps_identified', []),
                contradictions=result.get('contradictions', []),
                synthesis=result.get('synthesis', ''),
                implications=result.get('implications', [])
            )
        
        print(f"\n✓ SYNTHESIS COMPLETE")
        self.workflow.finish_synthesis()
        print("   Moving to hypothesis refinement...")
    
    # ========== STAGE 6: HYPOTHESIS ==========
    
    def stage_hypothesis(self):
        """Stage 6: Refine hypothesis based on evidence."""
        print("\n" + "="*60)
        print("  STAGE 6: HYPOTHESIS REFINEMENT")
        print("="*60)
        
        hyp = self.workflow.get_primary_hypothesis()
        summaries = list(self.workflow._summaries.values())
        deep_papers = self.workflow.get_deep_read_papers()
        
        # Get synthesis info
        synthesis = summaries[0].synthesis if summaries else ""
        implications = summaries[0].implications if summaries else []
        
        prompt = f"""Based on the literature review, refine the hypothesis.

Original Hypothesis: {hyp.statement if hyp else 'None'}

Synthesis: {synthesis[:500]}

Implications: {', '.join(implications[:5])}

Supporting Papers: {len([p for p in deep_papers if 'support' in p.relevance_to_hypothesis.lower()])}
Contradicting Papers: {len([p for p in deep_papers if 'contradict' in p.relevance_to_hypothesis.lower()])}

Generate a refined, testable hypothesis with:
1. Specific, measurable statement
2. Clear independent and dependent variables
3. Testable predictions
4. Rationale based on evidence

JSON format:
{{
    "statement": "Refined hypothesis statement",
    "rationale": "Why this hypothesis is supported by evidence",
    "independent_vars": ["IV1", "IV2"],
    "dependent_vars": ["DV1", "DV2"],
    "control_vars": ["Control1", "Control2"],
    "predictions": [
        {{"prediction": "If X then Y", "testable": true, "test_method": "How to test"}}
    ],
    "confidence": 0.7
}}"""
        
        print("\n[Phi is refining hypothesis...]")
        result = self.phi.generate_json(prompt)
        
        if result and hyp:
            print(f"\n📋 REFINED HYPOTHESIS:")
            print(f"   {result.get('statement', '')}")
            print(f"\n   Rationale: {result.get('rationale', '')[:200]}")
            print(f"\n   Variables:")
            print(f"      IV: {', '.join(result.get('independent_vars', []))}")
            print(f"      DV: {', '.join(result.get('dependent_vars', []))}")
            print(f"      Control: {', '.join(result.get('control_vars', []))}")
            print(f"\n   Confidence: {result.get('confidence', 0.5):.2f}")
            
            # Update hypothesis
            self.workflow.revise_hypothesis(
                hypothesis_id=hyp.id,
                new_statement=result.get('statement', hyp.statement),
                revision_reason=result.get('rationale', 'Refined based on literature review')
            )
            
            # Update with variables
            hyp = self.workflow.get_primary_hypothesis()
            hyp.independent_vars = result.get('independent_vars', [])
            hyp.dependent_vars = result.get('dependent_vars', [])
            hyp.control_vars = result.get('control_vars', [])
            hyp.predictions = result.get('predictions', [])
            hyp.confidence = result.get('confidence', 0.5)
            self.workflow._save_hypotheses()
            
            # Link evidence
            for paper in deep_papers:
                supports = 'support' in paper.relevance_to_hypothesis.lower()
                self.workflow.link_evidence_to_hypothesis(hyp.id, paper.id, supports=supports)
        
        print(f"\n✓ HYPOTHESIS REFINED")
        self.workflow.finish_hypothesis()
        print("   Moving to experiment design...")
    
    # ========== STAGE 7: EXPERIMENT DESIGN ==========
    
    def stage_experiment_design(self):
        """Stage 7: Design experiment to test hypothesis."""
        print("\n" + "="*60)
        print("  STAGE 7: EXPERIMENT DESIGN")
        print("="*60)
        
        hyp = self.workflow.get_primary_hypothesis()
        
        prompt = f"""Design an experiment to test this hypothesis:

Hypothesis: {hyp.statement}
Independent Variables: {', '.join(hyp.independent_vars)}
Dependent Variables: {', '.join(hyp.dependent_vars)}
Control Variables: {', '.join(hyp.control_vars)}

Design a rigorous experiment with:
1. Clear methodology
2. Step-by-step procedure
3. Required materials/resources
4. Expected outcomes with success criteria
5. Code outline (if computational)

JSON format:
{{
    "name": "Experiment name",
    "description": "Brief description",
    "methodology": "Detailed methodology",
    "procedure": [
        "Step 1: ...",
        "Step 2: ...",
        "Step 3: ..."
    ],
    "materials": ["Material 1", "Material 2"],
    "expected_outcomes": [
        {{
            "condition": "Condition description",
            "prediction": "What we expect",
            "success_criteria": "How we measure success"
        }}
    ],
    "code_description": "What code needs to be written",
    "code_outline": "# Pseudocode or actual code outline"
}}"""
        
        print("\n[Phi is designing experiment...]")
        result = self.phi.generate_json(prompt)
        
        if result:
            print(f"\n🔬 EXPERIMENT DESIGN:")
            print(f"   Name: {result.get('name', 'Unnamed')}")
            print(f"   Description: {result.get('description', '')[:200]}")
            
            print(f"\n   Procedure:")
            for i, step in enumerate(result.get('procedure', [])[:8], 1):
                print(f"      {i}. {step}")
            
            print(f"\n   Expected Outcomes:")
            for outcome in result.get('expected_outcomes', []):
                print(f"      • {outcome.get('prediction', '')}")
                print(f"        Success: {outcome.get('success_criteria', '')}")
            
            # Create experiment
            exp_id = self.workflow.design_experiment(
                hypothesis_id=hyp.id,
                name=result.get('name', 'Experiment'),
                description=result.get('description', ''),
                methodology=result.get('methodology', ''),
                procedure=result.get('procedure', []),
                materials=result.get('materials', []),
                expected_outcomes=result.get('expected_outcomes', []),
                code_description=result.get('code_description', '')
            )
            
            # Generate code if described
            if result.get('code_outline'):
                code_prompt = f"""Write Python code for this experiment:

{result.get('code_description', '')}

Code outline:
{result.get('code_outline', '')}

Write complete, runnable Python code."""
                
                print("\n[Phi is writing experiment code...]")
                code = self.phi.generate(code_prompt, max_tokens=2000)
                
                if code:
                    # Extract code block
                    if '```python' in code:
                        code = code.split('```python')[1].split('```')[0]
                    elif '```' in code:
                        code = code.split('```')[1].split('```')[0]
                    
                    self.workflow.add_experiment_code(exp_id, "experiment.py", code)
                    print("   ✓ Code saved to experiment.py")
            
            self._current_experiment_id = exp_id
        
        print(f"\n✓ EXPERIMENT DESIGNED")
        self.workflow.finish_experiment_design()
        print("   Moving to execution...")
    
    # ========== STAGE 8: EXECUTION ==========
    
    def stage_execution(self):
        """Stage 8: Execute experiment."""
        print("\n" + "="*60)
        print("  STAGE 8: EXECUTION")
        print("="*60)
        
        exp_id = getattr(self, '_current_experiment_id', None)
        if not exp_id:
            exp_id = list(self.workflow._experiments.keys())[0] if self.workflow._experiments else None
        
        if not exp_id:
            print("[ERROR] No experiment to execute")
            return
        
        exp = self.workflow._experiments[exp_id]
        
        print(f"\n🔬 EXECUTING: {exp.name}")
        print(f"   Methodology: {exp.methodology[:200]}...")
        
        self.workflow.start_experiment(exp_id)
        
        # Check if we have code to run
        if exp.code_files:
            code_path = self.workflow.project_dir / "code" / exp.code_files[0]
            if code_path.exists():
                print(f"\n[Attempting to run {exp.code_files[0]}...]")
                
                # Try to run the code
                try:
                    import subprocess
                    result = subprocess.run(
                        ['python', str(code_path)],
                        capture_output=True,
                        text=True,
                        timeout=120,
                        cwd=str(self.workflow.project_dir / "code")
                    )
                    
                    if result.returncode == 0:
                        print("   ✓ Code executed successfully")
                        print(f"\n   Output:\n{result.stdout[:500]}")
                        
                        # Parse results from output
                        self.workflow.record_result(exp_id, "stdout", result.stdout)
                        self.workflow.record_result(exp_id, "success", True)
                    else:
                        print(f"   ✗ Code failed: {result.stderr[:200]}")
                        self.workflow.record_result(exp_id, "stderr", result.stderr)
                        self.workflow.record_result(exp_id, "success", False)
                        
                except subprocess.TimeoutExpired:
                    print("   ✗ Code timed out")
                    self.workflow.record_result(exp_id, "error", "Timeout")
                except Exception as e:
                    print(f"   ✗ Execution error: {e}")
                    self.workflow.record_result(exp_id, "error", str(e))
        else:
            # Simulate results based on expected outcomes
            print("\n[No executable code - simulating based on expected outcomes...]")
            
            prompt = f"""Simulate realistic results for this experiment:

Experiment: {exp.name}
Methodology: {exp.methodology}
Expected Outcomes:
{json.dumps(exp.expected_outcomes, indent=2)}

Generate plausible experimental results.

JSON format:
{{
    "results": {{
        "metric_1": 0.85,
        "metric_2": 0.72,
        "p_value": 0.03
    }},
    "observations": ["Observation 1", "Observation 2"],
    "unexpected_findings": ["Any unexpected result"]
}}"""
            
            result = self.phi.generate_json(prompt)
            
            if result:
                for key, value in result.get('results', {}).items():
                    self.workflow.record_result(exp_id, key, value)
                
                print(f"\n   Simulated Results:")
                for key, value in result.get('results', {}).items():
                    print(f"      {key}: {value}")
        
        self.workflow.complete_experiment(exp_id, success=True)
        print(f"\n✓ EXECUTION COMPLETE")
        print("   Moving to analysis...")
    
    # ========== STAGE 9: ANALYSIS ==========
    
    def stage_analysis(self):
        """Stage 9: Analyze experiment results."""
        print("\n" + "="*60)
        print("  STAGE 9: ANALYSIS")
        print("="*60)
        
        exp_id = getattr(self, '_current_experiment_id', None)
        if not exp_id:
            exp_id = list(self.workflow._experiments.keys())[0] if self.workflow._experiments else None
        
        if not exp_id:
            print("[ERROR] No experiment to analyze")
            return
        
        exp = self.workflow._experiments[exp_id]
        hyp = self.workflow.get_primary_hypothesis()
        
        prompt = f"""Analyze these experimental results:

Hypothesis: {hyp.statement}

Experiment: {exp.name}
Expected Outcomes:
{json.dumps(exp.expected_outcomes, indent=2)}

Actual Results:
{json.dumps(exp.raw_results, indent=2)}

Provide analysis:
1. Do results support or refute the hypothesis?
2. Statistical significance (if applicable)
3. Effect size interpretation
4. Limitations of the experiment
5. Conclusions

JSON format:
{{
    "supports_hypothesis": true,
    "analysis": "Detailed analysis paragraph",
    "key_findings": ["Finding 1", "Finding 2"],
    "limitations": ["Limitation 1"],
    "confidence": 0.8
}}"""
        
        print("\n[Phi is analyzing results...]")
        result = self.phi.generate_json(prompt)
        
        if result:
            supports = result.get('supports_hypothesis', False)
            analysis = result.get('analysis', '')
            
            print(f"\n📊 ANALYSIS:")
            print(f"   Supports Hypothesis: {'YES ✓' if supports else 'NO ✗'}")
            print(f"   Confidence: {result.get('confidence', 0.5):.2f}")
            print(f"\n   Analysis: {analysis[:300]}...")
            
            print(f"\n   Key Findings:")
            for finding in result.get('key_findings', []):
                print(f"      • {finding}")
            
            self.workflow.analyze_experiment(
                experiment_id=exp_id,
                analysis=analysis,
                supports_hypothesis=supports
            )
        
        print(f"\n✓ ANALYSIS COMPLETE")
        self.workflow.finish_analysis()
        print("   Moving to conclusion...")
    
    # ========== STAGE 10: CONCLUSION ==========
    
    def stage_conclusion(self):
        """Stage 10: Final conclusion."""
        print("\n" + "="*60)
        print("  STAGE 10: CONCLUSION")
        print("="*60)
        
        hyp = self.workflow.get_primary_hypothesis()
        experiments = list(self.workflow._experiments.values())
        
        # Gather all evidence
        supporting_exp = [e for e in experiments if e.supports_hypothesis]
        refuting_exp = [e for e in experiments if e.supports_hypothesis == False]
        
        prompt = f"""Draw final conclusions for this research:

Hypothesis: {hyp.statement}

Supporting Experiments: {len(supporting_exp)}
Refuting Experiments: {len(refuting_exp)}
Supporting Papers: {len(hyp.supporting_evidence)}
Contradicting Papers: {len(hyp.contradicting_evidence)}

Experiment Analyses:
{chr(10).join(e.analysis[:200] for e in experiments if e.analysis)}

Provide final conclusion:
1. Is hypothesis supported, refuted, or inconclusive?
2. Summary of evidence
3. Implications for the field
4. Future research directions

JSON format:
{{
    "status": "supported",  // or "refuted" or "inconclusive"
    "conclusion": "Final conclusion paragraph",
    "evidence_summary": "Summary of supporting/contradicting evidence",
    "implications": ["Implication 1", "Implication 2"],
    "future_research": ["Future direction 1", "Future direction 2"],
    "confidence": 0.8
}}"""
        
        print("\n[Phi is drawing conclusions...]")
        result = self.phi.generate_json(prompt)
        
        if result:
            status = result.get('status', 'inconclusive')
            conclusion = result.get('conclusion', '')
            
            print(f"\n🎯 FINAL CONCLUSION:")
            print(f"   Status: {status.upper()}")
            print(f"\n   {conclusion}")
            
            print(f"\n   Implications:")
            for imp in result.get('implications', []):
                print(f"      • {imp}")
            
            print(f"\n   Future Research:")
            for future in result.get('future_research', []):
                print(f"      • {future}")
            
            self.workflow.conclude(
                hypothesis_id=hyp.id,
                conclusion=conclusion,
                hypothesis_status=status
            )
        
        print(f"\n{'='*60}")
        print(f"  RESEARCH COMPLETE!")
        print(f"{'='*60}")
        
        # Export for proposal
        export = self.workflow.export_for_proposal()
        export_path = self.workflow.project_dir / "EXPORT_FOR_PROPOSAL.json"
        with open(export_path, 'w') as f:
            json.dump(export, f, indent=2, default=str)
        
        print(f"\n📦 Research exported to: {export_path}")
        print(f"\n   Ready to create proposal from this research!")


def main():
    parser = argparse.ArgumentParser(description="Phi Research Runner")
    parser.add_argument("--topic", type=str, help="Research topic to start with")
    parser.add_argument("--resume", type=str, help="Resume existing research project")
    parser.add_argument("--interactive", action="store_true", default=True, help="Interactive mode")
    parser.add_argument("--auto", action="store_true", help="Automatic mode (no prompts)")
    parser.add_argument("--phi-url", type=str, default="http://localhost:8080", help="Phi server URL")
    parser.add_argument("--paperqa-url", type=str, default="http://localhost:5000", help="PaperQA server URL")
    parser.add_argument("--output-dir", type=str, default="./data/research_projects", help="Output directory")
    
    args = parser.parse_args()
    
    # Determine research ID
    if args.resume:
        research_id = args.resume
    elif args.topic:
        # Generate ID from topic
        research_id = args.topic.lower().replace(' ', '_')[:30]
    else:
        research_id = f"research_{int(time.time())}"
    
    # Create runner
    runner = PhiResearchRunner(
        research_id=research_id,
        base_dir=args.output_dir,
        phi_url=args.phi_url,
        paperqa_url=args.paperqa_url,
        interactive=not args.auto
    )
    
    # Run
    runner.run(topic=args.topic)


if __name__ == "__main__":
    main()

