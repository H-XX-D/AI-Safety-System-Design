"""
Research Workflow - Mirrors how humans actually do research.

STAGES:
1. IDEA: Initial hypothesis/question
2. BROAD SEARCH: Gather big list of papers (quick scan)
3. TRIAGE: Mark standouts, create smaller focused list
4. DEEP DIVE: In-depth notes on smaller list
5. SYNTHESIS: Compile notes into summary
6. HYPOTHESIS: Refine hypothesis based on evidence
7. EXPERIMENT DESIGN: Design experiment to test hypothesis
8. EXECUTION: Run experiment
9. ANALYSIS: Analyze results
10. CONCLUSION: Accept/reject/revise hypothesis

Each stage has its own files and can be resumed.
"""

import json
import time
import hashlib
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum
import threading
import logging

logger = logging.getLogger(__name__)


class ResearchStage(Enum):
    IDEA = "idea"
    BROAD_SEARCH = "broad_search"
    TRIAGE = "triage"
    DEEP_DIVE = "deep_dive"
    SYNTHESIS = "synthesis"
    HYPOTHESIS = "hypothesis"
    EXPERIMENT_DESIGN = "experiment_design"
    EXECUTION = "execution"
    ANALYSIS = "analysis"
    CONCLUSION = "conclusion"


@dataclass
class PaperEntry:
    """A paper in the research list."""
    id: str
    source: str  # "arxiv:2301.00001"
    title: str
    authors: List[str]
    year: Optional[int]
    abstract: str
    
    # Triage info (from quick scan)
    relevance_score: float = 0.0  # 0-1, how relevant to hypothesis
    is_standout: bool = False     # Marked for deep dive
    quick_notes: str = ""         # Notes from quick scan
    tags: List[str] = field(default_factory=list)
    
    # Deep dive info (if standout)
    deep_notes: List[Dict[str, Any]] = field(default_factory=list)
    key_findings: List[str] = field(default_factory=list)
    key_quotes: List[Dict[str, str]] = field(default_factory=list)
    methodology_notes: str = ""
    limitations: List[str] = field(default_factory=list)
    relevance_to_hypothesis: str = ""
    
    # Status
    status: str = "unread"  # 'unread', 'skimmed', 'deep_read', 'cited'
    added_at: float = field(default_factory=time.time)
    last_read: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PaperEntry':
        return cls(**data)


@dataclass
class Hypothesis:
    """A research hypothesis."""
    id: str
    statement: str
    rationale: str
    
    # Predictions
    predictions: List[Dict[str, Any]] = field(default_factory=list)
    # Each: {"prediction": "...", "testable": True, "test_method": "..."}
    
    # Variables
    independent_vars: List[str] = field(default_factory=list)
    dependent_vars: List[str] = field(default_factory=list)
    control_vars: List[str] = field(default_factory=list)
    
    # Evidence
    supporting_evidence: List[str] = field(default_factory=list)  # Paper IDs
    contradicting_evidence: List[str] = field(default_factory=list)
    
    # Status
    confidence: float = 0.5
    status: str = "proposed"  # 'proposed', 'testing', 'supported', 'refuted', 'revised'
    revision_history: List[Dict[str, Any]] = field(default_factory=list)
    
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Hypothesis':
        return cls(**data)


@dataclass
class Experiment:
    """An experiment to test a hypothesis."""
    id: str
    hypothesis_id: str
    name: str
    description: str
    
    # Design
    methodology: str
    variables: Dict[str, Any] = field(default_factory=dict)
    # {"independent": [...], "dependent": [...], "controlled": [...]}
    
    procedure: List[str] = field(default_factory=list)  # Step by step
    materials: List[str] = field(default_factory=list)  # What's needed
    
    # Predictions
    expected_outcomes: List[Dict[str, Any]] = field(default_factory=list)
    # {"condition": "...", "prediction": "...", "success_criteria": "..."}
    
    # Code (if computational)
    code_files: List[str] = field(default_factory=list)
    code_description: str = ""
    
    # Execution
    status: str = "designed"  # 'designed', 'running', 'completed', 'failed'
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    # Results
    raw_results: Dict[str, Any] = field(default_factory=dict)
    analysis: str = ""
    conclusion: str = ""
    supports_hypothesis: Optional[bool] = None
    
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Experiment':
        return cls(**data)


@dataclass
class NoteSummary:
    """Compiled summary from research notes."""
    id: str
    title: str
    
    # Summary sections
    background: str = ""
    key_findings: List[str] = field(default_factory=list)
    methodologies_reviewed: List[str] = field(default_factory=list)
    gaps_identified: List[str] = field(default_factory=list)
    contradictions: List[str] = field(default_factory=list)
    
    # Synthesis
    synthesis: str = ""  # Main narrative synthesis
    implications: List[str] = field(default_factory=list)
    
    # Sources
    papers_cited: List[str] = field(default_factory=list)
    
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NoteSummary':
        return cls(**data)


class ResearchWorkflow:
    """
    Complete research workflow from idea to conclusion.
    
    Mirrors human research process:
    1. Start with idea/question
    2. Broad search -> big list of papers
    3. Triage -> mark standouts, create focused list
    4. Deep dive -> detailed notes on standouts
    5. Synthesis -> compile notes into summary
    6. Hypothesis -> refine based on evidence
    7. Experiment design -> plan how to test
    8. Execute -> run experiment
    9. Analyze -> interpret results
    10. Conclude -> accept/reject/revise hypothesis
    """
    
    def __init__(
        self,
        research_id: str,
        base_dir: str = "./data/research_projects",
        paperqa_client=None,  # For paper retrieval
        llm_client=None       # For hypothesis/experiment generation
    ):
        self.research_id = research_id
        self.base_dir = Path(base_dir)
        self.project_dir = self.base_dir / research_id
        self.project_dir.mkdir(parents=True, exist_ok=True)
        
        self.paperqa = paperqa_client
        self.llm = llm_client
        
        self._lock = threading.RLock()
        
        # Create directory structure
        self._init_directories()
        
        # Load or create state
        self._state = self._load_state()
        
        # In-memory data
        self._papers: Dict[str, PaperEntry] = self._load_papers()
        self._hypotheses: Dict[str, Hypothesis] = self._load_hypotheses()
        self._experiments: Dict[str, Experiment] = self._load_experiments()
        self._summaries: Dict[str, NoteSummary] = self._load_summaries()
    
    def _init_directories(self) -> None:
        """Create directory structure."""
        dirs = [
            self.project_dir / "papers" / "broad_list",
            self.project_dir / "papers" / "standouts",
            self.project_dir / "notes" / "quick",
            self.project_dir / "notes" / "deep",
            self.project_dir / "summaries",
            self.project_dir / "hypotheses",
            self.project_dir / "experiments",
            self.project_dir / "results",
            self.project_dir / "code"
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
    
    def _load_json(self, path: Path, default: Any = None) -> Any:
        if path.exists():
            with open(path, 'r') as f:
                return json.load(f)
        return default if default is not None else {}
    
    def _save_json(self, path: Path, data: Any) -> None:
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def _load_state(self) -> Dict[str, Any]:
        state_file = self.project_dir / "state.json"
        default = {
            'research_id': self.research_id,
            'title': '',
            'initial_question': '',
            'current_stage': ResearchStage.IDEA.value,
            'created_at': time.time(),
            'updated_at': time.time(),
            'stage_history': []
        }
        return self._load_json(state_file, default)
    
    def _save_state(self) -> None:
        self._state['updated_at'] = time.time()
        self._save_json(self.project_dir / "state.json", self._state)
    
    def _load_papers(self) -> Dict[str, PaperEntry]:
        papers = {}
        papers_file = self.project_dir / "papers" / "all_papers.json"
        data = self._load_json(papers_file, {})
        for pid, pdata in data.items():
            papers[pid] = PaperEntry.from_dict(pdata)
        return papers
    
    def _save_papers(self) -> None:
        data = {pid: p.to_dict() for pid, p in self._papers.items()}
        self._save_json(self.project_dir / "papers" / "all_papers.json", data)
    
    def _load_hypotheses(self) -> Dict[str, Hypothesis]:
        hypotheses = {}
        hyp_file = self.project_dir / "hypotheses" / "hypotheses.json"
        data = self._load_json(hyp_file, {})
        for hid, hdata in data.items():
            hypotheses[hid] = Hypothesis.from_dict(hdata)
        return hypotheses
    
    def _save_hypotheses(self) -> None:
        data = {hid: h.to_dict() for hid, h in self._hypotheses.items()}
        self._save_json(self.project_dir / "hypotheses" / "hypotheses.json", data)
    
    def _load_experiments(self) -> Dict[str, Experiment]:
        experiments = {}
        exp_file = self.project_dir / "experiments" / "experiments.json"
        data = self._load_json(exp_file, {})
        for eid, edata in data.items():
            experiments[eid] = Experiment.from_dict(edata)
        return experiments
    
    def _save_experiments(self) -> None:
        data = {eid: e.to_dict() for eid, e in self._experiments.items()}
        self._save_json(self.project_dir / "experiments" / "experiments.json", data)
    
    def _load_summaries(self) -> Dict[str, NoteSummary]:
        summaries = {}
        sum_file = self.project_dir / "summaries" / "summaries.json"
        data = self._load_json(sum_file, {})
        for sid, sdata in data.items():
            summaries[sid] = NoteSummary.from_dict(sdata)
        return summaries
    
    def _save_summaries(self) -> None:
        data = {sid: s.to_dict() for sid, s in self._summaries.items()}
        self._save_json(self.project_dir / "summaries" / "summaries.json", data)
    
    def _advance_stage(self, new_stage: ResearchStage) -> None:
        """Record stage transition."""
        self._state['stage_history'].append({
            'from': self._state['current_stage'],
            'to': new_stage.value,
            'timestamp': time.time()
        })
        self._state['current_stage'] = new_stage.value
        self._save_state()
    
    # ========== STAGE 1: IDEA ==========
    
    def start_research(
        self,
        title: str,
        initial_question: str,
        initial_hypothesis: str = ""
    ) -> str:
        """Start a new research project with an idea."""
        with self._lock:
            self._state['title'] = title
            self._state['initial_question'] = initial_question
            
            # Create initial hypothesis if provided
            if initial_hypothesis:
                self.add_hypothesis(initial_hypothesis, "Initial hypothesis based on research question")
            
            self._advance_stage(ResearchStage.BROAD_SEARCH)
            self._save_state()
            
            return self.research_id
    
    # ========== STAGE 2: BROAD SEARCH ==========
    
    def add_paper_to_broad_list(
        self,
        source: str,
        title: str,
        authors: List[str],
        abstract: str,
        year: Optional[int] = None
    ) -> str:
        """Add a paper to the broad search list (quick scan)."""
        with self._lock:
            paper_id = hashlib.sha256(f"{source}{title}".encode()).hexdigest()[:12]
            
            paper = PaperEntry(
                id=paper_id,
                source=source,
                title=title,
                authors=authors,
                year=year,
                abstract=abstract,
                status='unread'
            )
            
            self._papers[paper_id] = paper
            self._save_papers()
            
            return paper_id
    
    def search_and_add_papers(
        self,
        query: str,
        max_results: int = 50
    ) -> List[str]:
        """Search via PaperQA and add results to broad list."""
        if not self.paperqa:
            logger.warning("PaperQA client not configured")
            return []
        
        # This would call PaperQA to search
        # results = self.paperqa.search(query, max_results=max_results)
        # For now, return empty - implement based on your PaperQA API
        
        return []
    
    def get_broad_list(self) -> List[PaperEntry]:
        """Get all papers in broad list."""
        return list(self._papers.values())
    
    def get_unread_papers(self) -> List[PaperEntry]:
        """Get papers not yet skimmed."""
        return [p for p in self._papers.values() if p.status == 'unread']
    
    # ========== STAGE 3: TRIAGE (Quick scan, mark standouts) ==========
    
    def skim_paper(
        self,
        paper_id: str,
        relevance_score: float,
        quick_notes: str,
        tags: List[str] = None,
        is_standout: bool = False
    ) -> None:
        """Quick scan a paper, take brief notes, mark if standout."""
        with self._lock:
            if paper_id not in self._papers:
                raise ValueError(f"Paper {paper_id} not found")
            
            paper = self._papers[paper_id]
            paper.status = 'skimmed'
            paper.relevance_score = relevance_score
            paper.quick_notes = quick_notes
            paper.tags = tags or []
            paper.is_standout = is_standout
            paper.last_read = time.time()
            
            # Save quick notes to file
            notes_file = self.project_dir / "notes" / "quick" / f"{paper_id}.md"
            with open(notes_file, 'w') as f:
                f.write(f"# Quick Notes: {paper.title}\n\n")
                f.write(f"**Source:** {paper.source}\n")
                f.write(f"**Relevance:** {relevance_score:.2f}\n")
                f.write(f"**Standout:** {'Yes' if is_standout else 'No'}\n")
                f.write(f"**Tags:** {', '.join(tags or [])}\n\n")
                f.write(f"## Notes\n{quick_notes}\n")
            
            self._save_papers()
    
    def mark_as_standout(self, paper_id: str) -> None:
        """Mark a paper as standout for deep dive."""
        with self._lock:
            if paper_id in self._papers:
                self._papers[paper_id].is_standout = True
                self._save_papers()
    
    def get_standouts(self) -> List[PaperEntry]:
        """Get papers marked as standouts."""
        return [p for p in self._papers.values() if p.is_standout]
    
    def get_triage_stats(self) -> Dict[str, Any]:
        """Get triage progress stats."""
        total = len(self._papers)
        skimmed = sum(1 for p in self._papers.values() if p.status in ('skimmed', 'deep_read'))
        standouts = sum(1 for p in self._papers.values() if p.is_standout)
        avg_relevance = sum(p.relevance_score for p in self._papers.values()) / total if total > 0 else 0
        
        return {
            'total_papers': total,
            'skimmed': skimmed,
            'remaining': total - skimmed,
            'standouts': standouts,
            'avg_relevance': avg_relevance,
            'progress_pct': (skimmed / total * 100) if total > 0 else 0
        }
    
    def finish_triage(self) -> None:
        """Move to deep dive stage."""
        self._advance_stage(ResearchStage.DEEP_DIVE)
    
    # ========== STAGE 4: DEEP DIVE (In-depth notes on standouts) ==========
    
    def deep_read_paper(
        self,
        paper_id: str,
        key_findings: List[str],
        key_quotes: List[Dict[str, str]],
        methodology_notes: str,
        limitations: List[str],
        relevance_to_hypothesis: str,
        detailed_notes: str = ""
    ) -> None:
        """Take in-depth notes on a standout paper."""
        with self._lock:
            if paper_id not in self._papers:
                raise ValueError(f"Paper {paper_id} not found")
            
            paper = self._papers[paper_id]
            paper.status = 'deep_read'
            paper.key_findings = key_findings
            paper.key_quotes = key_quotes
            paper.methodology_notes = methodology_notes
            paper.limitations = limitations
            paper.relevance_to_hypothesis = relevance_to_hypothesis
            paper.last_read = time.time()
            
            if detailed_notes:
                paper.deep_notes.append({
                    'content': detailed_notes,
                    'timestamp': time.time()
                })
            
            # Save deep notes to file
            notes_file = self.project_dir / "notes" / "deep" / f"{paper_id}.md"
            with open(notes_file, 'w') as f:
                f.write(f"# Deep Dive: {paper.title}\n\n")
                f.write(f"**Source:** {paper.source}\n")
                f.write(f"**Authors:** {', '.join(paper.authors)}\n\n")
                
                f.write("## Key Findings\n")
                for finding in key_findings:
                    f.write(f"- {finding}\n")
                
                f.write("\n## Key Quotes\n")
                for quote in key_quotes:
                    f.write(f"> \"{quote.get('text', '')}\" (p.{quote.get('page', '?')})\n\n")
                
                f.write(f"\n## Methodology\n{methodology_notes}\n")
                
                f.write("\n## Limitations\n")
                for lim in limitations:
                    f.write(f"- {lim}\n")
                
                f.write(f"\n## Relevance to Hypothesis\n{relevance_to_hypothesis}\n")
                
                if detailed_notes:
                    f.write(f"\n## Detailed Notes\n{detailed_notes}\n")
            
            self._save_papers()
    
    def get_deep_read_papers(self) -> List[PaperEntry]:
        """Get papers that have been deep read."""
        return [p for p in self._papers.values() if p.status == 'deep_read']
    
    def get_deep_dive_progress(self) -> Dict[str, Any]:
        """Get deep dive progress."""
        standouts = self.get_standouts()
        deep_read = self.get_deep_read_papers()
        
        return {
            'standouts_total': len(standouts),
            'deep_read': len(deep_read),
            'remaining': len(standouts) - len(deep_read),
            'progress_pct': (len(deep_read) / len(standouts) * 100) if standouts else 0
        }
    
    def finish_deep_dive(self) -> None:
        """Move to synthesis stage."""
        self._advance_stage(ResearchStage.SYNTHESIS)
    
    # ========== STAGE 5: SYNTHESIS (Compile notes into summary) ==========
    
    def create_summary(
        self,
        title: str,
        background: str,
        key_findings: List[str],
        methodologies_reviewed: List[str],
        gaps_identified: List[str],
        contradictions: List[str],
        synthesis: str,
        implications: List[str]
    ) -> str:
        """Create a summary from research notes."""
        with self._lock:
            summary_id = hashlib.sha256(f"{title}{time.time()}".encode()).hexdigest()[:12]
            
            # Get papers cited
            papers_cited = [p.id for p in self._papers.values() if p.status == 'deep_read']
            
            summary = NoteSummary(
                id=summary_id,
                title=title,
                background=background,
                key_findings=key_findings,
                methodologies_reviewed=methodologies_reviewed,
                gaps_identified=gaps_identified,
                contradictions=contradictions,
                synthesis=synthesis,
                implications=implications,
                papers_cited=papers_cited
            )
            
            self._summaries[summary_id] = summary
            self._save_summaries()
            
            # Write summary to markdown
            summary_file = self.project_dir / "summaries" / f"{summary_id}.md"
            with open(summary_file, 'w') as f:
                f.write(f"# {title}\n\n")
                f.write(f"## Background\n{background}\n\n")
                
                f.write("## Key Findings\n")
                for finding in key_findings:
                    f.write(f"- {finding}\n")
                
                f.write("\n## Methodologies Reviewed\n")
                for method in methodologies_reviewed:
                    f.write(f"- {method}\n")
                
                f.write("\n## Gaps Identified\n")
                for gap in gaps_identified:
                    f.write(f"- {gap}\n")
                
                if contradictions:
                    f.write("\n## Contradictions in Literature\n")
                    for contra in contradictions:
                        f.write(f"- {contra}\n")
                
                f.write(f"\n## Synthesis\n{synthesis}\n")
                
                f.write("\n## Implications\n")
                for imp in implications:
                    f.write(f"- {imp}\n")
                
                f.write(f"\n## Papers Cited ({len(papers_cited)})\n")
                for pid in papers_cited:
                    if pid in self._papers:
                        p = self._papers[pid]
                        f.write(f"- {p.title} ({p.source})\n")
            
            return summary_id
    
    def auto_generate_summary(self) -> Optional[str]:
        """Use LLM to generate summary from notes (if LLM client configured)."""
        if not self.llm:
            logger.warning("LLM client not configured for auto-generation")
            return None
        
        # Gather all deep notes
        deep_papers = self.get_deep_read_papers()
        
        # Build context for LLM
        notes_context = []
        for paper in deep_papers:
            notes_context.append({
                'title': paper.title,
                'key_findings': paper.key_findings,
                'relevance': paper.relevance_to_hypothesis,
                'limitations': paper.limitations
            })
        
        # This would call your LLM to synthesize
        # summary = self.llm.synthesize_notes(notes_context, self._state['initial_question'])
        
        return None  # Implement based on your LLM API
    
    def finish_synthesis(self) -> None:
        """Move to hypothesis refinement stage."""
        self._advance_stage(ResearchStage.HYPOTHESIS)
    
    # ========== STAGE 6: HYPOTHESIS (Refine based on evidence) ==========
    
    def add_hypothesis(
        self,
        statement: str,
        rationale: str,
        predictions: List[Dict[str, Any]] = None,
        independent_vars: List[str] = None,
        dependent_vars: List[str] = None,
        control_vars: List[str] = None
    ) -> str:
        """Add or refine a hypothesis."""
        with self._lock:
            hyp_id = hashlib.sha256(f"{statement}{time.time()}".encode()).hexdigest()[:12]
            
            hypothesis = Hypothesis(
                id=hyp_id,
                statement=statement,
                rationale=rationale,
                predictions=predictions or [],
                independent_vars=independent_vars or [],
                dependent_vars=dependent_vars or [],
                control_vars=control_vars or []
            )
            
            self._hypotheses[hyp_id] = hypothesis
            self._save_hypotheses()
            
            return hyp_id
    
    def link_evidence_to_hypothesis(
        self,
        hypothesis_id: str,
        paper_id: str,
        supports: bool = True
    ) -> None:
        """Link a paper as evidence for/against hypothesis."""
        with self._lock:
            if hypothesis_id not in self._hypotheses:
                raise ValueError(f"Hypothesis {hypothesis_id} not found")
            
            hyp = self._hypotheses[hypothesis_id]
            
            if supports:
                if paper_id not in hyp.supporting_evidence:
                    hyp.supporting_evidence.append(paper_id)
            else:
                if paper_id not in hyp.contradicting_evidence:
                    hyp.contradicting_evidence.append(paper_id)
            
            hyp.updated_at = time.time()
            self._save_hypotheses()
    
    def revise_hypothesis(
        self,
        hypothesis_id: str,
        new_statement: str,
        revision_reason: str
    ) -> None:
        """Revise a hypothesis based on evidence."""
        with self._lock:
            if hypothesis_id not in self._hypotheses:
                raise ValueError(f"Hypothesis {hypothesis_id} not found")
            
            hyp = self._hypotheses[hypothesis_id]
            
            # Record revision
            hyp.revision_history.append({
                'old_statement': hyp.statement,
                'new_statement': new_statement,
                'reason': revision_reason,
                'timestamp': time.time()
            })
            
            hyp.statement = new_statement
            hyp.status = 'revised'
            hyp.updated_at = time.time()
            
            self._save_hypotheses()
    
    def get_hypothesis(self, hypothesis_id: str) -> Optional[Hypothesis]:
        """Get a hypothesis."""
        return self._hypotheses.get(hypothesis_id)
    
    def get_primary_hypothesis(self) -> Optional[Hypothesis]:
        """Get the primary (first) hypothesis."""
        if self._hypotheses:
            return list(self._hypotheses.values())[0]
        return None
    
    def auto_generate_hypothesis(self) -> Optional[str]:
        """Use LLM to generate/refine hypothesis based on evidence."""
        if not self.llm:
            return None
        
        # Gather evidence summary
        # Call LLM to generate hypothesis
        # This would implement based on your LLM API
        
        return None
    
    def finish_hypothesis(self) -> None:
        """Move to experiment design stage."""
        self._advance_stage(ResearchStage.EXPERIMENT_DESIGN)
    
    # ========== STAGE 7: EXPERIMENT DESIGN ==========
    
    def design_experiment(
        self,
        hypothesis_id: str,
        name: str,
        description: str,
        methodology: str,
        procedure: List[str],
        materials: List[str] = None,
        expected_outcomes: List[Dict[str, Any]] = None,
        code_description: str = ""
    ) -> str:
        """Design an experiment to test a hypothesis."""
        with self._lock:
            if hypothesis_id not in self._hypotheses:
                raise ValueError(f"Hypothesis {hypothesis_id} not found")
            
            hyp = self._hypotheses[hypothesis_id]
            exp_id = hashlib.sha256(f"{name}{time.time()}".encode()).hexdigest()[:12]
            
            experiment = Experiment(
                id=exp_id,
                hypothesis_id=hypothesis_id,
                name=name,
                description=description,
                methodology=methodology,
                variables={
                    'independent': hyp.independent_vars,
                    'dependent': hyp.dependent_vars,
                    'controlled': hyp.control_vars
                },
                procedure=procedure,
                materials=materials or [],
                expected_outcomes=expected_outcomes or [],
                code_description=code_description
            )
            
            self._experiments[exp_id] = experiment
            self._save_experiments()
            
            # Write experiment design to file
            exp_file = self.project_dir / "experiments" / f"{exp_id}_design.md"
            with open(exp_file, 'w') as f:
                f.write(f"# Experiment: {name}\n\n")
                f.write(f"**Hypothesis:** {hyp.statement}\n\n")
                f.write(f"## Description\n{description}\n\n")
                f.write(f"## Methodology\n{methodology}\n\n")
                
                f.write("## Variables\n")
                f.write(f"- **Independent:** {', '.join(hyp.independent_vars)}\n")
                f.write(f"- **Dependent:** {', '.join(hyp.dependent_vars)}\n")
                f.write(f"- **Controlled:** {', '.join(hyp.control_vars)}\n\n")
                
                f.write("## Procedure\n")
                for i, step in enumerate(procedure, 1):
                    f.write(f"{i}. {step}\n")
                
                if materials:
                    f.write("\n## Materials\n")
                    for mat in materials:
                        f.write(f"- {mat}\n")
                
                if expected_outcomes:
                    f.write("\n## Expected Outcomes\n")
                    for outcome in expected_outcomes:
                        f.write(f"- **{outcome.get('condition', '')}:** {outcome.get('prediction', '')}\n")
                        f.write(f"  - Success criteria: {outcome.get('success_criteria', '')}\n")
            
            return exp_id
    
    def add_experiment_code(
        self,
        experiment_id: str,
        filename: str,
        code: str
    ) -> str:
        """Add code for an experiment."""
        with self._lock:
            if experiment_id not in self._experiments:
                raise ValueError(f"Experiment {experiment_id} not found")
            
            code_path = self.project_dir / "code" / filename
            with open(code_path, 'w') as f:
                f.write(code)
            
            exp = self._experiments[experiment_id]
            if filename not in exp.code_files:
                exp.code_files.append(filename)
            
            self._save_experiments()
            
            return str(code_path)
    
    def auto_generate_experiment(self, hypothesis_id: str) -> Optional[str]:
        """Use LLM to generate experiment design."""
        if not self.llm:
            return None
        
        # Get hypothesis
        # Call LLM to design experiment
        # This would implement based on your LLM API
        
        return None
    
    def finish_experiment_design(self) -> None:
        """Move to execution stage."""
        self._advance_stage(ResearchStage.EXECUTION)
    
    # ========== STAGE 8: EXECUTION ==========
    
    def start_experiment(self, experiment_id: str) -> None:
        """Mark experiment as started."""
        with self._lock:
            if experiment_id not in self._experiments:
                raise ValueError(f"Experiment {experiment_id} not found")
            
            exp = self._experiments[experiment_id]
            exp.status = 'running'
            exp.started_at = time.time()
            
            self._save_experiments()
    
    def record_result(
        self,
        experiment_id: str,
        result_key: str,
        result_value: Any
    ) -> None:
        """Record a result from experiment execution."""
        with self._lock:
            if experiment_id not in self._experiments:
                raise ValueError(f"Experiment {experiment_id} not found")
            
            exp = self._experiments[experiment_id]
            exp.raw_results[result_key] = {
                'value': result_value,
                'recorded_at': time.time()
            }
            
            self._save_experiments()
    
    def complete_experiment(
        self,
        experiment_id: str,
        success: bool = True
    ) -> None:
        """Mark experiment as completed."""
        with self._lock:
            if experiment_id not in self._experiments:
                raise ValueError(f"Experiment {experiment_id} not found")
            
            exp = self._experiments[experiment_id]
            exp.status = 'completed' if success else 'failed'
            exp.completed_at = time.time()
            
            self._save_experiments()
            self._advance_stage(ResearchStage.ANALYSIS)
    
    # ========== STAGE 9: ANALYSIS ==========
    
    def analyze_experiment(
        self,
        experiment_id: str,
        analysis: str,
        supports_hypothesis: bool
    ) -> None:
        """Record analysis of experiment results."""
        with self._lock:
            if experiment_id not in self._experiments:
                raise ValueError(f"Experiment {experiment_id} not found")
            
            exp = self._experiments[experiment_id]
            exp.analysis = analysis
            exp.supports_hypothesis = supports_hypothesis
            
            # Write analysis to file
            analysis_file = self.project_dir / "results" / f"{experiment_id}_analysis.md"
            with open(analysis_file, 'w') as f:
                f.write(f"# Analysis: {exp.name}\n\n")
                f.write(f"**Supports Hypothesis:** {'Yes' if supports_hypothesis else 'No'}\n\n")
                f.write(f"## Results\n")
                for key, val in exp.raw_results.items():
                    f.write(f"- **{key}:** {val.get('value', '')}\n")
                f.write(f"\n## Analysis\n{analysis}\n")
            
            self._save_experiments()
    
    def finish_analysis(self) -> None:
        """Move to conclusion stage."""
        self._advance_stage(ResearchStage.CONCLUSION)
    
    # ========== STAGE 10: CONCLUSION ==========
    
    def conclude(
        self,
        hypothesis_id: str,
        conclusion: str,
        hypothesis_status: str  # 'supported', 'refuted', 'inconclusive'
    ) -> None:
        """Record final conclusion."""
        with self._lock:
            if hypothesis_id not in self._hypotheses:
                raise ValueError(f"Hypothesis {hypothesis_id} not found")
            
            hyp = self._hypotheses[hypothesis_id]
            hyp.status = hypothesis_status
            hyp.updated_at = time.time()
            
            # Update experiments
            for exp in self._experiments.values():
                if exp.hypothesis_id == hypothesis_id:
                    exp.conclusion = conclusion
            
            self._save_hypotheses()
            self._save_experiments()
            
            # Write final conclusion
            conclusion_file = self.project_dir / "CONCLUSION.md"
            with open(conclusion_file, 'w') as f:
                f.write(f"# Research Conclusion: {self._state['title']}\n\n")
                f.write(f"**Initial Question:** {self._state['initial_question']}\n\n")
                f.write(f"**Hypothesis:** {hyp.statement}\n\n")
                f.write(f"**Status:** {hypothesis_status.upper()}\n\n")
                f.write(f"## Conclusion\n{conclusion}\n\n")
                
                f.write("## Evidence Summary\n")
                f.write(f"- Supporting papers: {len(hyp.supporting_evidence)}\n")
                f.write(f"- Contradicting papers: {len(hyp.contradicting_evidence)}\n")
                f.write(f"- Experiments run: {len(self._experiments)}\n")
    
    # ========== UTILITIES ==========
    
    def get_current_stage(self) -> ResearchStage:
        """Get current research stage."""
        return ResearchStage(self._state['current_stage'])
    
    def get_progress(self) -> Dict[str, Any]:
        """Get overall research progress."""
        stage = self.get_current_stage()
        stages_order = list(ResearchStage)
        current_index = stages_order.index(stage)
        
        return {
            'research_id': self.research_id,
            'title': self._state['title'],
            'current_stage': stage.value,
            'stage_index': current_index,
            'total_stages': len(stages_order),
            'progress_pct': (current_index / len(stages_order)) * 100,
            'papers_total': len(self._papers),
            'papers_standout': len(self.get_standouts()),
            'papers_deep_read': len(self.get_deep_read_papers()),
            'hypotheses': len(self._hypotheses),
            'experiments': len(self._experiments),
            'summaries': len(self._summaries)
        }
    
    def get_context_for_stage(self, max_chars: int = 4000) -> str:
        """Get context summary appropriate for current stage."""
        stage = self.get_current_stage()
        parts = []
        char_count = 0
        
        # Always include question and hypothesis
        parts.append(f"RESEARCH: {self._state['title']}")
        parts.append(f"QUESTION: {self._state['initial_question']}")
        
        hyp = self.get_primary_hypothesis()
        if hyp:
            parts.append(f"HYPOTHESIS: {hyp.statement}")
        
        char_count = sum(len(p) for p in parts)
        
        # Stage-specific context
        if stage in (ResearchStage.BROAD_SEARCH, ResearchStage.TRIAGE):
            stats = self.get_triage_stats()
            parts.append(f"\nPROGRESS: {stats['skimmed']}/{stats['total_papers']} papers skimmed, {stats['standouts']} standouts")
        
        elif stage == ResearchStage.DEEP_DIVE:
            standouts = self.get_standouts()
            parts.append(f"\nSTANDOUTS TO READ: {len(standouts)}")
            for p in standouts[:5]:
                if p.status != 'deep_read':
                    s = f"- {p.title} (relevance: {p.relevance_score:.2f})"
                    if char_count + len(s) < max_chars:
                        parts.append(s)
                        char_count += len(s)
        
        elif stage == ResearchStage.SYNTHESIS:
            deep_papers = self.get_deep_read_papers()
            parts.append(f"\nPAPERS TO SYNTHESIZE: {len(deep_papers)}")
            all_findings = []
            for p in deep_papers:
                all_findings.extend(p.key_findings[:2])
            parts.append("KEY FINDINGS:")
            for finding in all_findings[:10]:
                if char_count + len(finding) < max_chars:
                    parts.append(f"- {finding}")
                    char_count += len(finding)
        
        elif stage in (ResearchStage.HYPOTHESIS, ResearchStage.EXPERIMENT_DESIGN):
            if hyp:
                parts.append(f"\nSUPPORTING EVIDENCE: {len(hyp.supporting_evidence)}")
                parts.append(f"CONTRADICTING EVIDENCE: {len(hyp.contradicting_evidence)}")
                parts.append(f"CONFIDENCE: {hyp.confidence:.2f}")
        
        return "\n".join(parts)
    
    def export_for_proposal(self) -> Dict[str, Any]:
        """Export research for use in a proposal."""
        hyp = self.get_primary_hypothesis()
        
        return {
            'research_id': self.research_id,
            'title': self._state['title'],
            'question': self._state['initial_question'],
            'hypothesis': hyp.to_dict() if hyp else None,
            'summaries': [s.to_dict() for s in self._summaries.values()],
            'experiments': [e.to_dict() for e in self._experiments.values()],
            'papers_cited': [
                {'id': p.id, 'title': p.title, 'source': p.source, 'key_findings': p.key_findings}
                for p in self._papers.values() if p.status == 'deep_read'
            ],
            'stage': self._state['current_stage']
        }

