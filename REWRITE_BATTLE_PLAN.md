# AI Safety System - Complete Rewrite Battle Plan

**Target:** Production-ready codebase from line 1
**Timeline:** 1 day (aggressive sprint)
**Current Grade:** C (70/100) → **Target Grade:** A (90/100)
**Date:** 2025-11-13

---

## 🎯 EXECUTIVE SUMMARY

**The Problem:** Brilliant AI safety concepts trapped in prototype-quality code with 4,287-line monoliths, 131 inline event handlers, hardcoded secrets, and no deployment story.

**The Solution:** Surgical rewrite following industry best practices while preserving the innovative safety mechanisms.

**The Strategy:** Start with solid foundations (architecture, tooling, CI/CD) then rebuild each subsystem cleanly with proper separation of concerns.

---

## 📋 PRE-FLIGHT CHECKLIST

Before you write a single line of code:

- [ ] Create new repository: `ORKA-v2` or `ai-safety-system-v2`
- [ ] Set up proper Python project structure from day 1
- [ ] Initialize with `.gitignore`, `.env.example`, `Dockerfile` immediately
- [ ] Create GitHub Actions CI/CD pipeline first
- [ ] Set up pre-commit hooks for linting/formatting
- [ ] Document architecture decisions as you go

---

## 🏗️ PHASE 1: FOUNDATION (Hours 0-2)

### 1.1 Project Structure (30 min)

```
ai-safety-system-v2/
├── .github/
│   └── workflows/
│       ├── ci.yml                    # Tests, linting, security
│       └── deploy.yml                # Docker build & deploy
├── src/
│   └── orka/
│       ├── __init__.py
│       ├── core/                     # Core orchestration
│       │   ├── __init__.py
│       │   ├── orchestrator.py       # < 300 lines
│       │   ├── coordinator.py        # < 300 lines
│       │   └── pipeline.py           # < 300 lines
│       ├── detection/                # Deception detection
│       │   ├── __init__.py
│       │   ├── detector.py           # < 400 lines
│       │   ├── methods.py            # 7 detection methods
│       │   └── incidents.py          # Incident handling
│       ├── debate/                   # Multi-agent debate
│       │   ├── __init__.py
│       │   ├── engine.py             # < 300 lines
│       │   ├── scoring.py
│       │   └── consensus.py
│       ├── memory/                   # Merkle memory & auditing
│       │   ├── __init__.py
│       │   ├── merkle.py             # < 300 lines
│       │   ├── auditor.py            # < 300 lines
│       │   └── storage.py
│       ├── worm/                     # WORM USB security
│       │   ├── __init__.py
│       │   ├── manifest.py           # < 300 lines
│       │   ├── verifier.py           # < 300 lines
│       │   └── builder.py            # < 300 lines
│       ├── sandbox/                  # Isolated execution
│       │   ├── __init__.py
│       │   ├── docker_backend.py     # < 300 lines
│       │   ├── isolation.py          # < 300 lines
│       │   └── manager.py
│       ├── translation/              # Air-gapped translation
│       │   ├── __init__.py
│       │   ├── translator.py         # < 300 lines
│       │   └── hardware.py           # < 300 lines
│       ├── reputation/               # Reputation & penalties
│       │   ├── __init__.py
│       │   ├── system.py             # < 300 lines
│       │   ├── penalties.py
│       │   └── rewards.py
│       ├── validation/               # VAL validator bridge
│       │   ├── __init__.py
│       │   ├── pipeline.py           # < 300 lines
│       │   └── filters.py
│       ├── research/                 # Research agent system
│       │   ├── __init__.py
│       │   ├── agents.py             # < 400 lines
│       │   └── llm_adapters.py       # < 400 lines
│       ├── compression/              # AURA compression
│       │   ├── __init__.py
│       │   ├── codec.py
│       │   └── strategy.py
│       ├── api/                      # REST API layer
│       │   ├── __init__.py
│       │   ├── routes/
│       │   │   ├── __init__.py
│       │   │   ├── proposals.py      # < 200 lines
│       │   │   ├── detection.py      # < 200 lines
│       │   │   ├── penalties.py      # < 200 lines
│       │   │   ├── system.py         # < 200 lines
│       │   │   └── orka.py           # < 200 lines
│       │   ├── schemas.py            # Pydantic models
│       │   └── dependencies.py       # DI setup
│       ├── db/                       # Database layer
│       │   ├── __init__.py
│       │   ├── models.py             # SQLAlchemy models
│       │   ├── session.py            # Session management
│       │   └── migrations/           # Alembic migrations
│       ├── config/                   # Configuration
│       │   ├── __init__.py
│       │   ├── settings.py           # Pydantic settings
│       │   └── logging.py            # Logging config
│       └── utils/                    # Shared utilities
│           ├── __init__.py
│           ├── security.py
│           ├── types.py
│           └── constants.py
├── frontend/                         # Modern frontend (separate)
│   ├── src/
│   │   ├── components/               # React components
│   │   │   ├── Dashboard/
│   │   │   ├── Proposals/
│   │   │   ├── Detection/
│   │   │   ├── Penalties/
│   │   │   ├── System/
│   │   │   └── Orka/
│   │   ├── api/                      # API client
│   │   ├── hooks/                    # React hooks
│   │   ├── store/                    # State management
│   │   ├── utils/
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── public/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts                # Vite build tool
│   └── .eslintrc.js
├── tests/
│   ├── unit/                         # Unit tests by module
│   │   ├── test_orchestrator.py
│   │   ├── test_detector.py
│   │   └── ...
│   ├── integration/                  # Integration tests
│   │   ├── test_pipeline.py
│   │   └── test_api.py
│   ├── e2e/                          # End-to-end tests
│   │   └── test_workflows.py
│   ├── conftest.py                   # Pytest fixtures
│   └── factories.py                  # Test data factories
├── docs/
│   ├── architecture/
│   │   ├── OVERVIEW.md
│   │   ├── MODULES.md
│   │   └── DIAGRAMS.md
│   ├── api/
│   │   └── openapi.yaml              # OpenAPI spec
│   ├── deployment/
│   │   ├── DOCKER.md
│   │   ├── KUBERNETES.md
│   │   └── PRODUCTION.md
│   └── guides/
│       ├── QUICKSTART.md
│       └── DEVELOPMENT.md
├── scripts/
│   ├── setup_dev.sh                  # Dev environment setup
│   ├── run_tests.sh                  # Test runner
│   └── deploy.sh                     # Deployment script
├── docker/
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   └── docker-compose.yml
├── .github/
├── .gitignore
├── .env.example
├── .dockerignore
├── .pre-commit-config.yaml
├── pyproject.toml                    # Python project config
├── requirements.txt                  # Pinned dependencies
├── requirements-dev.txt              # Dev dependencies
├── README.md                         # Concise overview
└── LICENSE
```

### 1.2 Tooling Setup (30 min)

**pyproject.toml:**
```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[project]
name = "orka-ai-safety"
version = "2.0.0"
description = "Production AI Safety System with Multi-Tier Validation"
requires-python = ">=3.11"
dependencies = [
    "fastapi==0.109.0",
    "pydantic==2.5.0",
    "sqlalchemy==2.0.25",
    "alembic==1.13.1",
    "pynacl==1.5.0",
    "structlog==24.1.0",
    "redis==5.0.1",
    "celery==5.3.4",
]

[project.optional-dependencies]
dev = [
    "pytest==8.0.0",
    "pytest-cov==4.1.0",
    "pytest-asyncio==0.23.3",
    "black==24.8.0",
    "ruff==0.6.0",
    "mypy==1.7.1",
    "pre-commit==3.6.0",
]

[tool.black]
line-length = 100
target-version = ['py311']

[tool.ruff]
line-length = 100
select = ["E", "F", "I", "N", "W"]

[tool.mypy]
strict = true
warn_return_any = true
warn_unused_configs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

**.pre-commit-config.yaml:**
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/psf/black
    rev: 24.8.0
    hooks:
      - id: black

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.0
    hooks:
      - id: ruff
        args: [--fix]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.1
    hooks:
      - id: mypy
```

### 1.3 CI/CD Pipeline (30 min)

**.github/workflows/ci.yml:**
```yaml
name: CI Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v5
      with:
        python-version: ${{ matrix.python-version }}
        cache: 'pip'

    - name: Install dependencies
      run: |
        pip install -e ".[dev]"

    - name: Lint with ruff
      run: ruff check .

    - name: Format check with black
      run: black --check .

    - name: Type check with mypy
      run: mypy src/

    - name: Run tests with coverage
      run: |
        pytest --cov=src --cov-report=xml --cov-report=term

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml

  security:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4

    - name: Run Trivy security scan
      uses: aquasecurity/trivy-action@master
      with:
        scan-type: 'fs'
        scan-ref: '.'

    - name: Run bandit security scan
      run: |
        pip install bandit
        bandit -r src/ -f json -o bandit-report.json

  docker:
    runs-on: ubuntu-latest
    needs: [test, security]
    steps:
    - uses: actions/checkout@v4

    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3

    - name: Build and test Docker image
      uses: docker/build-push-action@v5
      with:
        context: .
        file: docker/Dockerfile.backend
        push: false
        tags: orka-backend:${{ github.sha }}
```

### 1.4 Docker Setup (30 min)

**docker/Dockerfile.backend:**
```dockerfile
FROM python:3.11-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/
COPY pyproject.toml .

# Install package
RUN pip install -e .

# Create non-root user
RUN useradd -m -u 1000 orka && chown -R orka:orka /app
USER orka

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)"

CMD ["uvicorn", "orka.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: orka
      POSTGRES_USER: orka
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U orka"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: .
      dockerfile: docker/Dockerfile.backend
    environment:
      DATABASE_URL: postgresql://orka:${DB_PASSWORD}@postgres:5432/orka
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: ${SECRET_KEY}
      ADMIN_TOKEN: ${ADMIN_TOKEN}
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./logs:/app/logs
      - worm_data:/app/worm

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:80"
    depends_on:
      - backend

volumes:
  postgres_data:
  worm_data:
```

---

## 🚀 PHASE 2: CORE BACKEND (Hours 2-6)

### 2.1 Configuration & Settings (30 min)

**src/orka/config/settings.py:**
```python
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # App
    app_name: str = "ORKA AI Safety System"
    app_version: str = "2.0.0"
    environment: str = "development"
    debug: bool = False

    # Security
    secret_key: str
    admin_token: str
    cors_origins: list[str] = ["http://localhost:3000"]

    # Database
    database_url: str
    db_pool_size: int = 20
    db_max_overflow: int = 10

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # WORM USB
    worm_usb_path: str = "/media/usb"
    worm_verification_enabled: bool = True

    # Sandbox
    sandbox_engine: str = "docker"  # docker, firecracker, virtual
    sandbox_timeout: int = 300
    sandbox_memory_limit: str = "512m"
    sandbox_cpu_limit: str = "1.0"

    # AI Safety
    deception_threshold: float = 0.7
    collusion_detection_enabled: bool = True
    reputation_decay_rate: float = 0.95

    # LLM
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    class Config:
        env_file = ".env"
        case_sensitive = False

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### 2.2 Database Models (45 min)

**src/orka/db/models.py:**
```python
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Proposal(Base):
    """Improvement proposal model."""
    __tablename__ = "proposals"

    id = Column(String(36), primary_key=True)
    agent_id = Column(String(50), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    code = Column(Text, nullable=True)
    guardrails = Column(JSON, nullable=False)

    status = Column(String(20), nullable=False, default="submitted", index=True)
    pipeline_stage = Column(String(50), nullable=False, default="submitted")

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    detections = relationship("DeceptionDetection", back_populates="proposal", cascade="all, delete-orphan")
    reviews = relationship("PeerReview", back_populates="proposal", cascade="all, delete-orphan")
    execution = relationship("SandboxExecution", back_populates="proposal", uselist=False, cascade="all, delete-orphan")


class DeceptionDetection(Base):
    """Deception detection event model."""
    __tablename__ = "deception_detections"

    id = Column(Integer, primary_key=True)
    proposal_id = Column(String(36), ForeignKey("proposals.id"), nullable=False, index=True)

    detection_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)
    confidence = Column(Float, nullable=False)

    evidence = Column(JSON, nullable=False)
    methods_triggered = Column(JSON, nullable=False)  # List of 7 methods

    detected_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Relationships
    proposal = relationship("Proposal", back_populates="detections")


class AgentReputation(Base):
    """Agent reputation and penalty tracking."""
    __tablename__ = "agent_reputations"

    agent_id = Column(String(50), primary_key=True)

    reputation_score = Column(Float, nullable=False, default=1.0)
    permanent_penalty_additive = Column(Float, nullable=False, default=0.0)
    permanent_penalty_multiplicative = Column(Float, nullable=False, default=1.0)

    total_proposals = Column(Integer, nullable=False, default=0)
    approved_proposals = Column(Integer, nullable=False, default=0)
    rejected_proposals = Column(Integer, nullable=False, default=0)
    deception_incidents = Column(Integer, nullable=False, default=0)
    collusion_attempts = Column(Integer, nullable=False, default=0)

    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class PeerReview(Base):
    """Peer review model."""
    __tablename__ = "peer_reviews"

    id = Column(Integer, primary_key=True)
    proposal_id = Column(String(36), ForeignKey("proposals.id"), nullable=False, index=True)
    reviewer_agent_id = Column(String(50), nullable=False)

    approved = Column(Boolean, nullable=False)
    confidence = Column(Float, nullable=False)
    reasoning = Column(Text, nullable=False)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    proposal = relationship("Proposal", back_populates="reviews")


class SandboxExecution(Base):
    """Sandbox execution results."""
    __tablename__ = "sandbox_executions"

    id = Column(Integer, primary_key=True)
    proposal_id = Column(String(36), ForeignKey("proposals.id"), nullable=False, unique=True, index=True)

    engine = Column(String(20), nullable=False)  # docker, firecracker, virtual
    executed = Column(Boolean, nullable=False, default=False)
    success = Column(Boolean, nullable=True)

    stdout = Column(Text, nullable=True)
    stderr = Column(Text, nullable=True)
    exit_code = Column(Integer, nullable=True)

    metrics = Column(JSON, nullable=True)  # CPU, memory, time stats
    sandbox_warnings = Column(JSON, nullable=True)

    executed_at = Column(DateTime, nullable=True)

    # Relationships
    proposal = relationship("Proposal", back_populates="execution")


class WORMManifest(Base):
    """WORM USB manifest entries."""
    __tablename__ = "worm_manifests"

    id = Column(Integer, primary_key=True)
    proposal_id = Column(String(36), nullable=False, index=True)

    merkle_root = Column(String(64), nullable=False)
    sequence_number = Column(Integer, nullable=False, index=True)

    entry_data = Column(JSON, nullable=False)
    signature = Column(String(128), nullable=False)

    written_at = Column(DateTime, nullable=False, default=datetime.utcnow)
```

### 2.3 API Layer with FastAPI (1 hour)

**src/orka/api/main.py:**
```python
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager

from orka.config.settings import get_settings
from orka.db.session import init_db, close_db
from orka.api.routes import proposals, detection, penalties, system, orka

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Security headers
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "frame-ancestors 'none';"
    )
    return response

# Routes
app.include_router(proposals.router, prefix="/api/proposals", tags=["proposals"])
app.include_router(detection.router, prefix="/api/detection", tags=["detection"])
app.include_router(penalties.router, prefix="/api/penalties", tags=["penalties"])
app.include_router(system.router, prefix="/api/system", tags=["system"])
app.include_router(orka.router, prefix="/api/orka", tags=["orka"])

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.app_version}

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs"
    }
```

**src/orka/api/routes/proposals.py:**
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from orka.db.session import get_db
from orka.db.models import Proposal
from orka.api.schemas import ProposalCreate, ProposalResponse
from orka.core.orchestrator import Orchestrator

router = APIRouter()

@router.post("/", response_model=ProposalResponse, status_code=201)
async def create_proposal(
    proposal: ProposalCreate,
    db: AsyncSession = Depends(get_db),
    orchestrator: Orchestrator = Depends()
):
    """Submit a new improvement proposal."""
    result = await orchestrator.submit_proposal(proposal, db)
    return result

@router.get("/", response_model=list[ProposalResponse])
async def list_proposals(
    skip: int = 0,
    limit: int = 100,
    agent_id: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    """List all proposals with optional filtering."""
    # Implementation here (< 50 lines)
    pass

@router.get("/{proposal_id}", response_model=ProposalResponse)
async def get_proposal(
    proposal_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific proposal by ID."""
    # Implementation here (< 30 lines)
    pass
```

### 2.4 Core Orchestrator (1.5 hours)

**src/orka/core/orchestrator.py (< 300 lines):**
```python
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from orka.db.models import Proposal
from orka.detection.detector import DeceptionDetector
from orka.debate.engine import DebateEngine
from orka.sandbox.manager import SandboxManager
from orka.memory.merkle import MerkleMemory
from orka.worm.manifest import WORMManifest
from orka.reputation.system import ReputationSystem

class Orchestrator:
    """
    Main orchestration engine (< 300 lines).
    Coordinates proposal pipeline without doing everything itself.
    """

    def __init__(
        self,
        detector: DeceptionDetector,
        debate_engine: DebateEngine,
        sandbox: SandboxManager,
        memory: MerkleMemory,
        worm: WORMManifest,
        reputation: ReputationSystem
    ):
        self.detector = detector
        self.debate = debate_engine
        self.sandbox = sandbox
        self.memory = memory
        self.worm = worm
        self.reputation = reputation

    async def submit_proposal(
        self,
        proposal_data: dict[str, Any],
        db: AsyncSession
    ) -> dict[str, Any]:
        """
        Submit and process a proposal through the pipeline.

        Steps:
        1. Create proposal record
        2. Initial deception scan
        3. Peer review coordination
        4. Debate if needed
        5. Sandbox execution
        6. Memory recording
        7. WORM manifest entry
        8. Reputation update
        """
        # Create proposal (20 lines)
        proposal = await self._create_proposal(proposal_data, db)

        # Deception detection (10 lines)
        detection_result = await self.detector.scan(proposal)
        if detection_result.is_deceptive:
            return await self._handle_deception(proposal, detection_result, db)

        # Peer review (15 lines)
        reviews = await self._coordinate_reviews(proposal, db)

        # Debate if controversial (20 lines)
        if self._needs_debate(reviews):
            debate_result = await self.debate.conduct(proposal, reviews)
            if not debate_result.consensus:
                return await self._handle_rejection(proposal, debate_result, db)

        # Sandbox execution (15 lines)
        if proposal.code:
            exec_result = await self.sandbox.execute(proposal)
            if not exec_result.success:
                return await self._handle_sandbox_failure(proposal, exec_result, db)

        # Memory recording (10 lines)
        merkle_root = await self.memory.record(proposal)

        # WORM manifest (10 lines)
        await self.worm.append(proposal, merkle_root)

        # Reputation update (10 lines)
        await self.reputation.update_for_approval(proposal.agent_id, db)

        # Return result (5 lines)
        return await self._format_response(proposal, db)

    # Private helper methods (each < 50 lines)
    async def _create_proposal(self, data, db): pass
    async def _handle_deception(self, proposal, detection, db): pass
    async def _coordinate_reviews(self, proposal, db): pass
    def _needs_debate(self, reviews): pass
    async def _handle_rejection(self, proposal, debate, db): pass
    async def _handle_sandbox_failure(self, proposal, result, db): pass
    async def _format_response(self, proposal, db): pass
```

### 2.5 Deception Detector (1 hour)

**src/orka/detection/detector.py (< 400 lines):**
```python
from dataclasses import dataclass
from orka.detection.methods import (
    complexity_mismatch,
    overconfidence_detection,
    pattern_signatures,
    semantic_cues,
    consistency_check,
    historical_comparison,
    peer_disagreement
)

@dataclass
class DetectionResult:
    is_deceptive: bool
    confidence: float
    severity: str
    evidence: dict[str, Any]
    methods_triggered: list[str]

class DeceptionDetector:
    """
    7-method deception detection system (< 400 lines).
    Each method is in separate module for clarity.
    """

    def __init__(self, threshold: float = 0.7):
        self.threshold = threshold
        self.methods = [
            complexity_mismatch,
            overconfidence_detection,
            pattern_signatures,
            semantic_cues,
            consistency_check,
            historical_comparison,
            peer_disagreement
        ]

    async def scan(self, proposal: Proposal) -> DetectionResult:
        """
        Run all 7 detection methods and aggregate results.
        """
        # Run methods in parallel (20 lines)
        results = await asyncio.gather(*[
            method(proposal) for method in self.methods
        ])

        # Aggregate confidence scores (30 lines)
        total_confidence = self._aggregate_confidence(results)

        # Determine severity (15 lines)
        severity = self._calculate_severity(total_confidence, results)

        # Collect evidence (20 lines)
        evidence = self._collect_evidence(results)

        # Build result (10 lines)
        return DetectionResult(
            is_deceptive=total_confidence >= self.threshold,
            confidence=total_confidence,
            severity=severity,
            evidence=evidence,
            methods_triggered=[r.method_name for r in results if r.triggered]
        )

    def _aggregate_confidence(self, results): pass  # 30 lines
    def _calculate_severity(self, confidence, results): pass  # 15 lines
    def _collect_evidence(self, results): pass  # 20 lines
```

**src/orka/detection/methods.py (each method < 100 lines):**
```python
async def complexity_mismatch(proposal: Proposal) -> MethodResult:
    """Detect complexity mismatch between claim and implementation."""
    # Implementation (< 100 lines)
    pass

async def overconfidence_detection(proposal: Proposal) -> MethodResult:
    """Detect overconfident language patterns."""
    # Implementation (< 100 lines)
    pass

# ... 5 more methods, each < 100 lines
```

---

## ⚡ PHASE 3: FRONTEND REWRITE (Hours 6-8)

### 3.1 Modern React + TypeScript Setup (30 min)

**frontend/package.json:**
```json
{
  "name": "orka-frontend",
  "version": "2.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext ts,tsx",
    "test": "vitest"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.21.0",
    "@tanstack/react-query": "^5.17.0",
    "zustand": "^4.4.7",
    "recharts": "^2.10.3",
    "axios": "^1.6.5"
  },
  "devDependencies": {
    "@types/react": "^18.2.48",
    "@types/react-dom": "^18.2.18",
    "@vitejs/plugin-react": "^4.2.1",
    "typescript": "^5.3.3",
    "vite": "^5.0.11",
    "eslint": "^8.56.0",
    "vitest": "^1.2.0"
  }
}
```

**frontend/vite.config.ts:**
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: true
  }
})
```

### 3.2 Component Architecture (1 hour)

**frontend/src/components/Dashboard/Dashboard.tsx:**
```typescript
import { useQuery } from '@tanstack/react-query'
import { fetchSystemStatus } from '@/api/system'
import { MetricsCard } from './MetricsCard'
import { RecentActivity } from './RecentActivity'

export function Dashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ['systemStatus'],
    queryFn: fetchSystemStatus,
    refetchInterval: 30000
  })

  if (isLoading) return <LoadingSpinner />

  return (
    <div className="dashboard">
      <h1>AI Safety System Dashboard</h1>
      <div className="metrics-grid">
        <MetricsCard
          title="Proposals Processed"
          value={data.totalProposals}
          change="+12%"
        />
        <MetricsCard
          title="Deception Detected"
          value={data.deceptionCount}
          severity="warning"
        />
        <MetricsCard
          title="Active Penalties"
          value={data.activePenalties}
        />
      </div>
      <RecentActivity proposals={data.recentProposals} />
    </div>
  )
}
```

**NO INLINE onclick HANDLERS - ALL EVENTS IN COMPONENTS:**
```typescript
// ✅ CORRECT
function ProposalCard({ proposal }: Props) {
  const handleView = () => {
    navigate(`/proposals/${proposal.id}`)
  }

  return (
    <div className="proposal-card" onClick={handleView}>
      {/* content */}
    </div>
  )
}

// ❌ WRONG (old way)
<div onclick="viewProposal('123')">  // NEVER DO THIS
```

### 3.3 State Management (30 min)

**frontend/src/store/proposalStore.ts:**
```typescript
import { create } from 'zustand'

interface ProposalStore {
  selectedProposal: Proposal | null
  filterStatus: string | null
  setSelectedProposal: (proposal: Proposal | null) => void
  setFilterStatus: (status: string | null) => void
}

export const useProposalStore = create<ProposalStore>((set) => ({
  selectedProposal: null,
  filterStatus: null,
  setSelectedProposal: (proposal) => set({ selectedProposal: proposal }),
  setFilterStatus: (status) => set({ filterStatus: status })
}))
```

---

## 🧪 PHASE 4: TESTING (Hour 8)

### 4.1 Test Structure

```python
# tests/unit/test_orchestrator.py
import pytest
from orka.core.orchestrator import Orchestrator

@pytest.mark.asyncio
async def test_submit_proposal_success(orchestrator, db_session, sample_proposal):
    """Test successful proposal submission."""
    result = await orchestrator.submit_proposal(sample_proposal, db_session)

    assert result['status'] == 'approved'
    assert result['merkle_root'] is not None

@pytest.mark.asyncio
async def test_submit_proposal_deception_detected(orchestrator, db_session, deceptive_proposal):
    """Test proposal rejection due to deception."""
    result = await orchestrator.submit_proposal(deceptive_proposal, db_session)

    assert result['status'] == 'rejected'
    assert result['reason'] == 'deception_detected'

# tests/integration/test_api.py
from httpx import AsyncClient
from orka.api.main import app

@pytest.mark.asyncio
async def test_create_proposal_endpoint():
    """Test POST /api/proposals endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/proposals",
            json={"agent_id": "TIF", "title": "Test", "code": "print('test')"}
        )

    assert response.status_code == 201
    data = response.json()
    assert data['id'] is not None
```

---

## 📊 PHASE 5: DOCUMENTATION (Continuous)

### 5.1 README Template

```markdown
# ORKA AI Safety System v2

**Production-ready AI safety system with multi-tier validation, deception detection, and immutable auditing.**

[![Tests](https://github.com/user/repo/workflows/CI/badge.svg)](...)
[![Coverage](https://codecov.io/gh/user/repo/badge.svg)](...)
[![Docker](https://img.shields.io/docker/v/user/orka)](...)

## Quick Start

```bash
# Clone and setup
git clone https://github.com/user/orka-v2
cd orka-v2
cp .env.example .env
# Edit .env with your secrets

# Run with Docker
docker-compose up -d

# Access UI
open http://localhost:3000
```

## Architecture

See [docs/architecture/OVERVIEW.md](docs/architecture/OVERVIEW.md)

## Development

See [docs/guides/DEVELOPMENT.md](docs/guides/DEVELOPMENT.md)
```

---

## 🎯 SUCCESS METRICS

By end of day, you should have:

- [ ] ✅ **No files >500 lines**
- [ ] ✅ **All dependencies pinned**
- [ ] ✅ **Docker deployment working**
- [ ] ✅ **CI/CD passing**
- [ ] ✅ **>80% test coverage**
- [ ] ✅ **Zero inline event handlers**
- [ ] ✅ **API documented (OpenAPI)**
- [ ] ✅ **Health checks working**
- [ ] ✅ **Type checking passing (mypy)**
- [ ] ✅ **All security headers set**

**Grade Target: A (90/100)**

---

## ⚠️ PITFALLS TO AVOID

1. **Don't try to preserve old code** - Start fresh, it's faster
2. **Don't skip the tooling setup** - Pre-commit hooks save hours later
3. **Don't write monoliths** - If a file hits 400 lines, split it
4. **Don't skimp on tests** - Write them as you go, not after
5. **Don't hardcode anything** - Use settings.py for all config
6. **Don't use inline handlers** - All events in React components
7. **Don't skip documentation** - Write docstrings as you code
8. **Don't ignore typing** - mypy --strict from day 1

---

## 🏁 DEPLOYMENT CHECKLIST

Before calling it done:

- [ ] Run full test suite: `pytest --cov`
- [ ] Run type checker: `mypy src/`
- [ ] Run linter: `ruff check .`
- [ ] Run security scan: `bandit -r src/`
- [ ] Build Docker image: `docker build -f docker/Dockerfile.backend .`
- [ ] Test Docker locally: `docker-compose up`
- [ ] Check all endpoints: `/health`, `/docs`, `/api/*`
- [ ] Verify CSP headers: `curl -I http://localhost:8000`
- [ ] Load test: `locust -f tests/load/locustfile.py`
- [ ] Review logs: `docker-compose logs`

---

## 🚀 POST-REWRITE: NEXT 30 DAYS

**Week 1:**
- Deploy to staging environment
- Run penetration testing
- Performance optimization
- Documentation completion

**Week 2:**
- User acceptance testing
- Bug fixes from testing
- Monitoring dashboard setup
- Backup/recovery testing

**Week 3:**
- Production deployment prep
- Team training
- Incident response playbook
- Runbook documentation

**Week 4:**
- Production deployment
- Monitor metrics closely
- Gather feedback
- Plan v2.1 features

---

## 💡 KEY PRINCIPLES

1. **Separation of Concerns** - Each module does ONE thing
2. **Dependency Injection** - Easy to test, easy to swap
3. **Type Safety** - Catch bugs at dev time, not runtime
4. **Fail Fast** - Better to crash early than corrupt data
5. **Observable** - Log everything, expose metrics
6. **Secure by Default** - Auth, HTTPS, CSP, headers
7. **Document as Code** - Code is documentation
8. **Test Everything** - If it's not tested, it's broken

---

## 🎓 LESSONS FROM V1

**What to Keep:**
- ✅ AI safety concepts (deception detection, WORM, reputation)
- ✅ Multi-agent debate approach
- ✅ Merkle memory auditing
- ✅ Sandbox isolation philosophy

**What to Fix:**
- ❌ Monolithic files → Small modules
- ❌ No type hints → Strict typing
- ❌ Inline handlers → React components
- ❌ Hardcoded secrets → Environment variables
- ❌ No CI/CD → Automated pipeline
- ❌ No deployment → Docker + docker-compose
- ❌ Scattered config → Pydantic settings
- ❌ JSON files → PostgreSQL

---

## 📝 FINAL NOTES

**This is an AGGRESSIVE 1-day rewrite plan.** You may need to adjust timeline based on:
- Team size (1 person vs 3 people)
- Existing familiarity with stack
- Complexity of migration decisions
- Testing thoroughness requirements

**Minimum Viable Rewrite** (if pressed for time):
- Phases 1-2 are CRITICAL (foundation + backend core)
- Phase 3 can be deferred (keep old UI temporarily)
- Phase 4 can be partial (focus on critical paths)
- Phase 5 is continuous (improve over time)

**The goal is NOT perfection on day 1.**
**The goal is SOLID FOUNDATION that can evolve.**

Good luck! 🚀

---

**Generated:** 2025-11-13
**Source:** Comprehensive assessment of AI-Safety-System-Design v1
**Target:** Production-ready v2 in 1 day
