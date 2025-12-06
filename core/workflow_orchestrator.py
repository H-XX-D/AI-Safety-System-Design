"""
Workflow State Machine & Message Queue
=======================================

Manages the 18-step proposal workflow with:
- State machine for proposal lifecycle
- Message queue for async agent communication
- Scheduler for round-robin peer review
- PAGEQA rate limiting

This is CODE-based orchestration (not LLM) for reliability.
ORKA's LLM is only invoked for counterpoint and interpretation tasks.
"""

import json
import time
import threading
import queue
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Callable, Set
from enum import Enum, auto
from pathlib import Path
import sqlite3
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)


# ============================================================================
# Workflow States
# ============================================================================

class WorkflowState(Enum):
    """18-step proposal workflow states."""
    
    # Initialization
    AWAITING_SIGNAL = 1           # Waiting for ORKA build signal
    
    # Research & Drafting (TIER 1)
    DOMAIN_RESEARCH = 2           # Agent queries PAGEQA for domain info
    BUILDING_PROPOSAL = 3         # Agent drafts initial proposal
    
    # First Review Cycle (TIER 2)
    PEER_REVIEW_1_PENDING = 4     # Waiting for peer reviews
    PEER_REVIEW_1_COMPLETE = 5    # All reviews received
    REVISION_1 = 6                # Agent revising based on feedback
    
    # PAGEQA Deep Research
    PAGEQA_RESEARCH_PENDING = 7   # Waiting in PAGEQA queue
    PAGEQA_RESEARCH_COMPLETE = 8  # Research results received
    REVISION_2 = 9                # Agent revising based on research
    
    # Second Review Cycle (TIER 3)
    PEER_REVIEW_2_PENDING = 10    # Waiting for peer reviews
    PEER_REVIEW_2_COMPLETE = 11   # All reviews received
    REVISION_3 = 12               # Agent revising based on feedback
    
    # ORKA Counterpoint
    ORKA_COUNTERPOINT = 13        # ORKA generating adversarial challenges
    REVISION_4 = 14               # Agent addressing counterpoints
    
    # Voting
    VOTING_PENDING = 15           # Waiting for votes
    VOTING_COMPLETE = 16          # All votes received
    
    # Sandbox (TIER 4)
    SANDBOX_QUEUED = 17           # Waiting for sandbox slot
    SANDBOX_RUNNING = 18          # Code executing
    SANDBOX_DEBUG = 19            # ORKA debug assist in progress
    SANDBOX_METRICS = 20          # Measuring performance
    
    # Completion (TIER 5)
    REWARD_COMPUTE = 21           # Computing rewards
    RL_UPDATE = 22                # RL weight update
    MEMORY_DISTILL = 23           # Distilling to long-term memory
    COMPLETE = 24                 # Successfully completed
    REJECTED = 25                 # Rejected at voting
    FAILED = 26                   # Failed sandbox after max attempts


# ============================================================================
# Message Types
# ============================================================================

class MessageType(Enum):
    """Types of messages in the queue."""
    
    # ORKA → Agents
    BUILD_SIGNAL = "build_signal"
    PEER_REVIEW_REQUEST = "peer_review_request"
    ORKA_COUNTERPOINT = "orka_counterpoint"
    VOTE_REQUEST = "vote_request"
    SANDBOX_FIX_REQUEST = "sandbox_fix_request"
    
    # Agents → ORKA
    PROPOSAL_READY = "proposal_ready"
    PEER_REVIEW_RESPONSE = "peer_review_response"
    REVISION_COMPLETE = "revision_complete"
    COUNTERPOINT_RESPONSE = "counterpoint_response"
    VOTE_RESPONSE = "vote_response"
    SANDBOX_FIX_RESPONSE = "sandbox_fix_response"
    
    # PAGEQA
    PAGEQA_REQUEST = "pageqa_request"
    PAGEQA_RESPONSE = "pageqa_response"
    
    # System
    STATE_CHANGE = "state_change"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


@dataclass
class Message:
    """Message in the queue."""
    id: str
    type: MessageType
    from_agent: str
    to_agent: str
    proposal_id: Optional[str]
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    priority: int = 5  # 1=highest, 10=lowest
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['type'] = self.type.value
        return d
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'Message':
        d = d.copy()
        d['type'] = MessageType(d['type'])
        return cls(**d)


# ============================================================================
# Message Queue
# ============================================================================

class MessageQueue:
    """
    Thread-safe message queue with priority support.
    
    Uses SQLite for persistence and recovery.
    """
    
    def __init__(self, db_path: str = "./data/message_queue.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._lock = threading.RLock()
        self._message_id = 0
        self._pending_responses: Dict[str, threading.Event] = {}
        self._responses: Dict[str, Message] = {}
        
        # In-memory queue for fast access
        self._queue: queue.PriorityQueue = queue.PriorityQueue()
        
        self._init_db()
        self._load_pending()
    
    def _init_db(self) -> None:
        """Initialize SQLite database."""
        with self._get_db() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    type TEXT,
                    from_agent TEXT,
                    to_agent TEXT,
                    proposal_id TEXT,
                    data TEXT,
                    timestamp REAL,
                    priority INTEGER,
                    processed INTEGER DEFAULT 0
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_to_agent ON messages(to_agent)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_processed ON messages(processed)')
    
    @contextmanager
    def _get_db(self):
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    
    def _load_pending(self) -> None:
        """Load unprocessed messages from DB into queue."""
        with self._get_db() as conn:
            rows = conn.execute(
                'SELECT * FROM messages WHERE processed = 0 ORDER BY priority, timestamp'
            ).fetchall()
            
            for row in rows:
                msg = Message(
                    id=row['id'],
                    type=MessageType(row['type']),
                    from_agent=row['from_agent'],
                    to_agent=row['to_agent'],
                    proposal_id=row['proposal_id'],
                    data=json.loads(row['data']),
                    timestamp=row['timestamp'],
                    priority=row['priority']
                )
                self._queue.put((msg.priority, msg.timestamp, msg))
    
    def _generate_id(self) -> str:
        """Generate unique message ID."""
        with self._lock:
            self._message_id += 1
            return f"msg_{int(time.time())}_{self._message_id}"
    
    def send(
        self,
        type: MessageType,
        from_agent: str,
        to_agent: str,
        data: Dict[str, Any],
        proposal_id: Optional[str] = None,
        priority: int = 5
    ) -> str:
        """Send a message."""
        msg = Message(
            id=self._generate_id(),
            type=type,
            from_agent=from_agent,
            to_agent=to_agent,
            proposal_id=proposal_id,
            data=data,
            priority=priority
        )
        
        # Persist to DB
        with self._get_db() as conn:
            conn.execute('''
                INSERT INTO messages (id, type, from_agent, to_agent, proposal_id, data, timestamp, priority)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (msg.id, msg.type.value, msg.from_agent, msg.to_agent, 
                  msg.proposal_id, json.dumps(msg.data), msg.timestamp, msg.priority))
        
        # Add to in-memory queue
        self._queue.put((msg.priority, msg.timestamp, msg))
        
        logger.debug(f"Message sent: {msg.type.value} from {from_agent} to {to_agent}")
        return msg.id
    
    def receive(self, agent_id: str, timeout: float = 0.1) -> Optional[Message]:
        """Receive next message for an agent."""
        try:
            while True:
                # Get from queue with timeout
                priority, timestamp, msg = self._queue.get(timeout=timeout)
                
                if msg.to_agent == agent_id or msg.to_agent == "broadcast":
                    # Mark as processed
                    with self._get_db() as conn:
                        conn.execute('UPDATE messages SET processed = 1 WHERE id = ?', (msg.id,))
                    return msg
                else:
                    # Put back for other agent
                    self._queue.put((priority, timestamp, msg))
        except queue.Empty:
            return None
    
    def receive_all(self, agent_id: str) -> List[Message]:
        """Receive all pending messages for an agent."""
        messages = []
        while True:
            msg = self.receive(agent_id, timeout=0.01)
            if msg is None:
                break
            messages.append(msg)
        return messages
    
    def wait_for_response(
        self,
        from_agent: str,
        message_type: MessageType,
        proposal_id: Optional[str] = None,
        timeout: float = 120.0
    ) -> Optional[Message]:
        """Wait for a specific response message."""
        key = f"{from_agent}:{message_type.value}:{proposal_id or 'any'}"
        
        event = threading.Event()
        with self._lock:
            self._pending_responses[key] = event
        
        # Check if already received
        for _ in range(int(timeout * 10)):
            with self._lock:
                if key in self._responses:
                    msg = self._responses.pop(key)
                    del self._pending_responses[key]
                    return msg
            
            # Poll queue
            try:
                priority, timestamp, msg = self._queue.get(timeout=0.1)
                
                check_key = f"{msg.from_agent}:{msg.type.value}:{msg.proposal_id or 'any'}"
                if check_key == key:
                    with self._get_db() as conn:
                        conn.execute('UPDATE messages SET processed = 1 WHERE id = ?', (msg.id,))
                    with self._lock:
                        if key in self._pending_responses:
                            del self._pending_responses[key]
                    return msg
                else:
                    # Put back
                    self._queue.put((priority, timestamp, msg))
            except queue.Empty:
                pass
        
        # Timeout
        with self._lock:
            if key in self._pending_responses:
                del self._pending_responses[key]
        
        logger.warning(f"Timeout waiting for {message_type.value} from {from_agent}")
        return None
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        with self._get_db() as conn:
            total = conn.execute('SELECT COUNT(*) FROM messages').fetchone()[0]
            pending = conn.execute('SELECT COUNT(*) FROM messages WHERE processed = 0').fetchone()[0]
            
            by_type = {}
            rows = conn.execute(
                'SELECT type, COUNT(*) as cnt FROM messages WHERE processed = 0 GROUP BY type'
            ).fetchall()
            for row in rows:
                by_type[row['type']] = row['cnt']
        
        return {
            "total_messages": total,
            "pending": pending,
            "in_memory_queue": self._queue.qsize(),
            "by_type": by_type
        }


# ============================================================================
# Proposal State Manager
# ============================================================================

@dataclass
class ProposalState:
    """State of a proposal in the workflow."""
    proposal_id: str
    agent_id: str
    state: WorkflowState
    
    # Progress tracking
    peer_reviews_received: int = 0
    peer_reviews_needed: int = 5  # All 6 agents review (minus proposer)
    votes_received: int = 0
    votes_needed: int = 5
    votes_for: int = 0
    votes_against: int = 0
    
    # Sandbox
    sandbox_attempts: int = 0
    sandbox_max_attempts: int = 3
    
    # Timing
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    state_entered_at: float = field(default_factory=time.time)
    
    # Timeout tracking
    timeout_seconds: float = 300.0  # 5 min default per state
    
    def is_timed_out(self) -> bool:
        return time.time() - self.state_entered_at > self.timeout_seconds
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['state'] = self.state.name
        return d


class ProposalStateManager:
    """
    Manages proposal states across the workflow.
    
    Uses SQLite for persistence.
    """
    
    def __init__(self, db_path: str = "./data/proposal_states.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._lock = threading.RLock()
        self._states: Dict[str, ProposalState] = {}
        
        self._init_db()
        self._load_states()
    
    def _init_db(self) -> None:
        """Initialize database."""
        with self._get_db() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS proposal_states (
                    proposal_id TEXT PRIMARY KEY,
                    agent_id TEXT,
                    state TEXT,
                    data TEXT,
                    created_at REAL,
                    updated_at REAL
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_state ON proposal_states(state)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_agent ON proposal_states(agent_id)')
    
    @contextmanager
    def _get_db(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    
    def _load_states(self) -> None:
        """Load states from database."""
        with self._get_db() as conn:
            rows = conn.execute('SELECT * FROM proposal_states').fetchall()
            for row in rows:
                data = json.loads(row['data'])
                data['state'] = WorkflowState[data['state']]
                state = ProposalState(**data)
                self._states[state.proposal_id] = state
    
    def _save_state(self, state: ProposalState) -> None:
        """Save state to database."""
        with self._get_db() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO proposal_states (proposal_id, agent_id, state, data, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (state.proposal_id, state.agent_id, state.state.name, 
                  json.dumps(state.to_dict()), state.created_at, state.updated_at))
    
    def create_proposal(self, proposal_id: str, agent_id: str) -> ProposalState:
        """Create new proposal state."""
        with self._lock:
            state = ProposalState(
                proposal_id=proposal_id,
                agent_id=agent_id,
                state=WorkflowState.AWAITING_SIGNAL
            )
            self._states[proposal_id] = state
            self._save_state(state)
            return state
    
    def get_state(self, proposal_id: str) -> Optional[ProposalState]:
        """Get proposal state."""
        return self._states.get(proposal_id)
    
    def update_state(
        self,
        proposal_id: str,
        new_state: WorkflowState,
        **updates
    ) -> Optional[ProposalState]:
        """Update proposal state."""
        with self._lock:
            state = self._states.get(proposal_id)
            if not state:
                return None
            
            old_state = state.state
            state.state = new_state
            state.state_entered_at = time.time()
            state.updated_at = time.time()
            
            # Apply additional updates
            for key, value in updates.items():
                if hasattr(state, key):
                    setattr(state, key, value)
            
            self._save_state(state)
            
            logger.info(f"Proposal {proposal_id}: {old_state.name} → {new_state.name}")
            return state
    
    def increment_reviews(self, proposal_id: str) -> Optional[ProposalState]:
        """Increment peer review count."""
        with self._lock:
            state = self._states.get(proposal_id)
            if state:
                state.peer_reviews_received += 1
                state.updated_at = time.time()
                self._save_state(state)
            return state
    
    def record_vote(self, proposal_id: str, vote: bool) -> Optional[ProposalState]:
        """Record a vote."""
        with self._lock:
            state = self._states.get(proposal_id)
            if state:
                state.votes_received += 1
                if vote:
                    state.votes_for += 1
                else:
                    state.votes_against += 1
                state.updated_at = time.time()
                self._save_state(state)
            return state
    
    def get_proposals_in_state(self, state: WorkflowState) -> List[ProposalState]:
        """Get all proposals in a given state."""
        return [s for s in self._states.values() if s.state == state]
    
    def get_proposals_by_agent(self, agent_id: str) -> List[ProposalState]:
        """Get all proposals for an agent."""
        return [s for s in self._states.values() if s.agent_id == agent_id]
    
    def get_timed_out_proposals(self) -> List[ProposalState]:
        """Get proposals that have timed out."""
        return [s for s in self._states.values() if s.is_timed_out()]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get workflow statistics."""
        by_state = {}
        for state in WorkflowState:
            count = len([s for s in self._states.values() if s.state == state])
            if count > 0:
                by_state[state.name] = count
        
        return {
            "total_proposals": len(self._states),
            "by_state": by_state,
            "timed_out": len(self.get_timed_out_proposals())
        }


# ============================================================================
# PAGEQA Rate Limiter
# ============================================================================

class PAGEQAQueue:
    """
    Rate-limited queue for PAGEQA requests.
    
    PAGEQA runs on a single Nano, so we queue requests.
    """
    
    def __init__(self, max_concurrent: int = 1):
        self.max_concurrent = max_concurrent
        self._queue: queue.Queue = queue.Queue()
        self._processing: Set[str] = set()
        self._lock = threading.RLock()
        self._results: Dict[str, Any] = {}
        self._events: Dict[str, threading.Event] = {}
    
    def submit(self, proposal_id: str, query: str, domain: str) -> str:
        """Submit a PAGEQA request."""
        request_id = f"pqa_{proposal_id}_{int(time.time())}"
        
        with self._lock:
            self._events[request_id] = threading.Event()
        
        self._queue.put({
            "request_id": request_id,
            "proposal_id": proposal_id,
            "query": query,
            "domain": domain,
            "submitted_at": time.time()
        })
        
        logger.info(f"PAGEQA request queued: {request_id}")
        return request_id
    
    def get_next(self) -> Optional[Dict[str, Any]]:
        """Get next request to process (for PAGEQA worker)."""
        with self._lock:
            if len(self._processing) >= self.max_concurrent:
                return None
        
        try:
            request = self._queue.get_nowait()
            with self._lock:
                self._processing.add(request["request_id"])
            return request
        except queue.Empty:
            return None
    
    def complete(self, request_id: str, result: Any) -> None:
        """Mark request as complete with result."""
        with self._lock:
            self._processing.discard(request_id)
            self._results[request_id] = result
            if request_id in self._events:
                self._events[request_id].set()
        
        logger.info(f"PAGEQA request completed: {request_id}")
    
    def wait_for_result(self, request_id: str, timeout: float = 300.0) -> Optional[Any]:
        """Wait for a result."""
        event = self._events.get(request_id)
        if not event:
            return None
        
        if event.wait(timeout=timeout):
            with self._lock:
                return self._results.pop(request_id, None)
        
        logger.warning(f"PAGEQA request timed out: {request_id}")
        return None
    
    def get_queue_length(self) -> int:
        return self._queue.qsize()
    
    def get_processing_count(self) -> int:
        return len(self._processing)


# ============================================================================
# Peer Review Scheduler
# ============================================================================

class PeerReviewScheduler:
    """
    Round-robin scheduler for peer reviews.
    
    Ensures each agent only has one review task at a time.
    """
    
    AGENTS = ["TIF", "GIN", "TORI", "THEO", "NOVEL", "GUARD"]
    
    def __init__(self):
        self._lock = threading.RLock()
        self._busy_agents: Set[str] = set()
        self._pending_reviews: queue.Queue = queue.Queue()
    
    def schedule_reviews(
        self,
        proposal_id: str,
        proposer_id: str,
        proposal_summary: str
    ) -> List[str]:
        """
        Schedule peer reviews for a proposal.
        
        Returns list of reviewer agent IDs.
        """
        reviewers = [a for a in self.AGENTS if a != proposer_id]
        
        for reviewer in reviewers:
            self._pending_reviews.put({
                "proposal_id": proposal_id,
                "proposer_id": proposer_id,
                "reviewer_id": reviewer,
                "proposal_summary": proposal_summary,
                "scheduled_at": time.time()
            })
        
        logger.info(f"Scheduled {len(reviewers)} reviews for {proposal_id}")
        return reviewers
    
    def get_next_review(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get next review assignment for an agent (if not busy)."""
        with self._lock:
            if agent_id in self._busy_agents:
                return None
        
        # Look for a review assigned to this agent
        temp = []
        result = None
        
        while True:
            try:
                review = self._pending_reviews.get_nowait()
                if review["reviewer_id"] == agent_id:
                    result = review
                    with self._lock:
                        self._busy_agents.add(agent_id)
                    break
                else:
                    temp.append(review)
            except queue.Empty:
                break
        
        # Put back unmatched reviews
        for r in temp:
            self._pending_reviews.put(r)
        
        return result
    
    def complete_review(self, agent_id: str) -> None:
        """Mark agent as done with current review."""
        with self._lock:
            self._busy_agents.discard(agent_id)
    
    def get_pending_count(self) -> int:
        return self._pending_reviews.qsize()
    
    def get_busy_agents(self) -> List[str]:
        with self._lock:
            return list(self._busy_agents)


# ============================================================================
# Workflow Orchestrator
# ============================================================================

class WorkflowOrchestrator:
    """
    Main orchestrator for the 18-step workflow.
    
    This is CODE-based orchestration. ORKA's LLM is only called for:
    - Counterpoint generation
    - Sandbox debug analysis
    - Ambiguous result interpretation
    """
    
    def __init__(
        self,
        message_queue: Optional[MessageQueue] = None,
        state_manager: Optional[ProposalStateManager] = None,
        pageqa_queue: Optional[PAGEQAQueue] = None,
        review_scheduler: Optional[PeerReviewScheduler] = None,
        data_dir: str = "./data"
    ):
        self.message_queue = message_queue or MessageQueue(f"{data_dir}/message_queue.db")
        self.state_manager = state_manager or ProposalStateManager(f"{data_dir}/proposal_states.db")
        self.pageqa_queue = pageqa_queue or PAGEQAQueue()
        self.review_scheduler = review_scheduler or PeerReviewScheduler()
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    def start(self) -> None:
        """Start the orchestrator loop."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Workflow orchestrator started")
    
    def stop(self) -> None:
        """Stop the orchestrator."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Workflow orchestrator stopped")
    
    def _run_loop(self) -> None:
        """Main orchestrator loop."""
        while self._running:
            try:
                # Process incoming messages
                self._process_messages()
                
                # Check for state transitions
                self._check_transitions()
                
                # Handle timeouts
                self._handle_timeouts()
                
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"Orchestrator loop error: {e}")
                time.sleep(1)
    
    def _process_messages(self) -> None:
        """Process messages directed to ORKA."""
        messages = self.message_queue.receive_all("ORKA")
        
        for msg in messages:
            try:
                self._handle_message(msg)
            except Exception as e:
                logger.error(f"Error handling message {msg.id}: {e}")
    
    def _handle_message(self, msg: Message) -> None:
        """Handle a single message."""
        handlers = {
            MessageType.PROPOSAL_READY: self._handle_proposal_ready,
            MessageType.PEER_REVIEW_RESPONSE: self._handle_peer_review,
            MessageType.REVISION_COMPLETE: self._handle_revision,
            MessageType.COUNTERPOINT_RESPONSE: self._handle_counterpoint_response,
            MessageType.VOTE_RESPONSE: self._handle_vote,
            MessageType.SANDBOX_FIX_RESPONSE: self._handle_sandbox_fix,
            MessageType.PAGEQA_RESPONSE: self._handle_pageqa_response,
        }
        
        handler = handlers.get(msg.type)
        if handler:
            handler(msg)
        else:
            logger.warning(f"No handler for message type: {msg.type}")
    
    def _handle_proposal_ready(self, msg: Message) -> None:
        """Handle proposal ready for review."""
        proposal_id = msg.proposal_id
        if not proposal_id:
            return
        
        state = self.state_manager.get_state(proposal_id)
        if not state:
            return
        
        # Schedule peer reviews
        self.review_scheduler.schedule_reviews(
            proposal_id=proposal_id,
            proposer_id=msg.from_agent,
            proposal_summary=msg.data.get("summary", "")
        )
        
        # Update state
        self.state_manager.update_state(proposal_id, WorkflowState.PEER_REVIEW_1_PENDING)
    
    def _handle_peer_review(self, msg: Message) -> None:
        """Handle peer review response."""
        proposal_id = msg.proposal_id
        if not proposal_id:
            return
        
        state = self.state_manager.increment_reviews(proposal_id)
        if not state:
            return
        
        self.review_scheduler.complete_review(msg.from_agent)
        
        # Check if all reviews received
        if state.peer_reviews_received >= state.peer_reviews_needed:
            if state.state == WorkflowState.PEER_REVIEW_1_PENDING:
                self.state_manager.update_state(proposal_id, WorkflowState.PEER_REVIEW_1_COMPLETE)
            elif state.state == WorkflowState.PEER_REVIEW_2_PENDING:
                self.state_manager.update_state(proposal_id, WorkflowState.PEER_REVIEW_2_COMPLETE)
    
    def _handle_revision(self, msg: Message) -> None:
        """Handle revision complete."""
        proposal_id = msg.proposal_id
        if not proposal_id:
            return
        
        state = self.state_manager.get_state(proposal_id)
        if not state:
            return
        
        # Determine next state based on current
        next_states = {
            WorkflowState.REVISION_1: WorkflowState.PAGEQA_RESEARCH_PENDING,
            WorkflowState.REVISION_2: WorkflowState.PEER_REVIEW_2_PENDING,
            WorkflowState.REVISION_3: WorkflowState.ORKA_COUNTERPOINT,
            WorkflowState.REVISION_4: WorkflowState.VOTING_PENDING,
        }
        
        next_state = next_states.get(state.state)
        if next_state:
            self.state_manager.update_state(proposal_id, next_state)
    
    def _handle_counterpoint_response(self, msg: Message) -> None:
        """Handle counterpoint response from agent."""
        proposal_id = msg.proposal_id
        if not proposal_id:
            return
        
        self.state_manager.update_state(proposal_id, WorkflowState.REVISION_4)
    
    def _handle_vote(self, msg: Message) -> None:
        """Handle vote response."""
        proposal_id = msg.proposal_id
        if not proposal_id:
            return
        
        vote = msg.data.get("vote", False)
        state = self.state_manager.record_vote(proposal_id, vote)
        
        if not state:
            return
        
        # Check if all votes received
        if state.votes_received >= state.votes_needed:
            # Determine outcome (simple majority for now)
            if state.votes_for > state.votes_against:
                self.state_manager.update_state(proposal_id, WorkflowState.SANDBOX_QUEUED)
            else:
                self.state_manager.update_state(proposal_id, WorkflowState.REJECTED)
    
    def _handle_sandbox_fix(self, msg: Message) -> None:
        """Handle sandbox fix response."""
        # This is handled by SandboxDebugLoop
        pass
    
    def _handle_pageqa_response(self, msg: Message) -> None:
        """Handle PAGEQA research response."""
        proposal_id = msg.proposal_id
        if not proposal_id:
            return
        
        self.state_manager.update_state(proposal_id, WorkflowState.PAGEQA_RESEARCH_COMPLETE)
    
    def _check_transitions(self) -> None:
        """Check for automatic state transitions."""
        # Peer review complete → revision
        for state in self.state_manager.get_proposals_in_state(WorkflowState.PEER_REVIEW_1_COMPLETE):
            self.state_manager.update_state(state.proposal_id, WorkflowState.REVISION_1)
            # Notify agent
            self.message_queue.send(
                type=MessageType.STATE_CHANGE,
                from_agent="ORKA",
                to_agent=state.agent_id,
                proposal_id=state.proposal_id,
                data={"new_state": "REVISION_1"}
            )
        
        for state in self.state_manager.get_proposals_in_state(WorkflowState.PEER_REVIEW_2_COMPLETE):
            self.state_manager.update_state(state.proposal_id, WorkflowState.REVISION_3)
            self.message_queue.send(
                type=MessageType.STATE_CHANGE,
                from_agent="ORKA",
                to_agent=state.agent_id,
                proposal_id=state.proposal_id,
                data={"new_state": "REVISION_3"}
            )
        
        # PAGEQA complete → revision
        for state in self.state_manager.get_proposals_in_state(WorkflowState.PAGEQA_RESEARCH_COMPLETE):
            self.state_manager.update_state(state.proposal_id, WorkflowState.REVISION_2)
            self.message_queue.send(
                type=MessageType.STATE_CHANGE,
                from_agent="ORKA",
                to_agent=state.agent_id,
                proposal_id=state.proposal_id,
                data={"new_state": "REVISION_2"}
            )
    
    def _handle_timeouts(self) -> None:
        """Handle timed out proposals."""
        for state in self.state_manager.get_timed_out_proposals():
            logger.warning(f"Proposal {state.proposal_id} timed out in {state.state.name}")
            # Could implement retry logic or failure here
    
    # ========== Public API ==========
    
    def broadcast_build_signal(self) -> None:
        """Broadcast build signal to all research agents."""
        for agent in PeerReviewScheduler.AGENTS:
            self.message_queue.send(
                type=MessageType.BUILD_SIGNAL,
                from_agent="ORKA",
                to_agent=agent,
                data={"signal": "build_proposal", "timestamp": time.time()}
            )
        logger.info("Build signal broadcast to all agents")
    
    def create_proposal(self, proposal_id: str, agent_id: str) -> ProposalState:
        """Create a new proposal."""
        return self.state_manager.create_proposal(proposal_id, agent_id)
    
    def get_workflow_status(self) -> Dict[str, Any]:
        """Get complete workflow status."""
        return {
            "state_manager": self.state_manager.get_stats(),
            "message_queue": self.message_queue.get_queue_stats(),
            "pageqa_queue": {
                "pending": self.pageqa_queue.get_queue_length(),
                "processing": self.pageqa_queue.get_processing_count()
            },
            "peer_reviews": {
                "pending": self.review_scheduler.get_pending_count(),
                "busy_agents": self.review_scheduler.get_busy_agents()
            }
        }
