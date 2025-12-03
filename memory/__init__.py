"""
AI Safety System - 3-Tier Memory Architecture with RAG

This module implements a hierarchical memory system with:

TIER 1: Working Memory (RAM + Disk Spillover)
├── Fast, session-scoped context
├── Automatic disk spillover when RAM fills
├── Session notes for long research sessions
└── Research scratchpads per proposal

TIER 2: Personal Memory (On-Device)
├── SQLite + vector embeddings
├── Agent-specific history and patterns
├── Distilled session summaries (not raw data)
└── Citation store (refs only, PaperQA has full content)

TIER 3: Shared Memory (Orchestra)
├── Network-accessible, cross-agent
├── Approved proposals as collective knowledge
└── Synchronized across all Jetson Nanos

Supporting Systems:
├── RAG Retriever - Unified search across all tiers
├── Citation Store - Lightweight refs, PaperQA retrieves full content
├── Dedup LUT Tree - Prevents redundant storage while preserving history
├── Session Distiller - Compresses sessions into insights
├── Steering Vectors - Behavior modification without retraining
└── Research Scratchpad - Per-proposal research with context offloading

Architecture:
┌─────────────────────────────────────────────────────────────────────────┐
│                          MEMORY MANAGER                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │ WORKING MEMORY  │  │ PERSONAL MEMORY │  │  SHARED MEMORY  │         │
│  │  (RAM + Disk)   │  │   (On-Device)   │  │   (Orchestra)   │         │
│  │                 │  │                 │  │                 │         │
│  │ • Session ctx   │  │ • Proposals     │  │ • Approved      │         │
│  │ • Notes         │  │ • Patterns      │  │ • Patterns      │         │
│  │ • Scratchpads   │  │ • Distilled     │  │ • Cross-agent   │         │
│  │ • Spillover     │  │ • Citations     │  │                 │         │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘         │
│           │                    │                    │                   │
│           └────────────────────┼────────────────────┘                   │
│                                │                                        │
│                    ┌───────────┴───────────┐                            │
│                    │     RAG RETRIEVER     │                            │
│                    │  (Unified Search)     │                            │
│                    └───────────────────────┘                            │
│                                                                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │
│  │  CITATION   │ │   DEDUP     │ │  SESSION    │ │  STEERING   │       │
│  │   STORE     │ │  LUT TREE   │ │  DISTILLER  │ │  VECTORS    │       │
│  │ (Refs only) │ │ (No dupes)  │ │ (Compress)  │ │ (Behavior)  │       │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘       │
│                                                                         │
│  PaperQA handles full document retrieval - we only store references    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
"""

from .working_memory import WorkingMemory, MemoryItem, SessionNote
from .personal_memory import PersonalMemory, ProposalRecord, LearningPattern
from .shared_memory import SharedMemoryClient, SharedMemoryServer, SharedProposal
from .citation_store import CitationStore, Citation, CitationBundle
from .dedup_lut_tree import DedupLUTTree, KnowledgeNode, DedupResult
from .session_distiller import SessionDistiller, DistilledSession, DistilledInsight
from .steering_vectors import SteeringVectorStore, SteeringVector, SteeringConfig
from .research_scratchpad import ResearchScratchpad, DistilledPaper, ProposalOutline as ScratchpadOutline
from .rag_retriever import RAGRetriever, RAGContext, RetrievalResult, EmbeddingProvider
from .memory_manager import MemoryManager
from .proposal_workspace import ProposalWorkspace, ProposalManifest, ProposalOutline, WorkingContext
from .research_workflow import (
    ResearchWorkflow, ResearchStage, PaperEntry, Hypothesis, 
    Experiment, NoteSummary
)

__all__ = [
    # Core memory tiers
    'WorkingMemory',
    'PersonalMemory', 
    'SharedMemoryClient',
    'SharedMemoryServer',
    
    # Memory manager
    'MemoryManager',
    
    # RAG
    'RAGRetriever',
    'RAGContext',
    'RetrievalResult',
    'EmbeddingProvider',
    
    # Citations
    'CitationStore',
    'Citation',
    'CitationBundle',
    
    # Deduplication
    'DedupLUTTree',
    'KnowledgeNode',
    'DedupResult',
    
    # Session handling
    'SessionDistiller',
    'DistilledSession',
    'DistilledInsight',
    
    # Steering
    'SteeringVectorStore',
    'SteeringVector',
    'SteeringConfig',
    
    # Research & Proposals
    'ResearchScratchpad',
    'DistilledPaper',
    'ProposalWorkspace',
    'ProposalManifest',
    'ProposalOutline',
    'WorkingContext',
    
    # Research Workflow (Human-style)
    'ResearchWorkflow',
    'ResearchStage',
    'PaperEntry',
    'Hypothesis',
    'Experiment',
    'NoteSummary',
    
    # Data classes
    'MemoryItem',
    'SessionNote',
    'ProposalRecord',
    'LearningPattern',
    'SharedProposal',
]


# Version
__version__ = '1.0.0'
