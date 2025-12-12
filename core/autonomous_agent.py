"""
Autonomous Agent Runner
========================
Each AI runs as an independent process with:
- Real-time streaming inference
- Asynchronous message board communication
- Genuine inter-agent debate
- Context injection support
- Observable thinking process

This is NOT a scripted workflow - each agent thinks independently
and responds to others organically.
"""

import os
import sys
import json
import time
import threading
import queue
from datetime import datetime
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import requests


class AgentState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    WAITING = "waiting"  # Waiting for others
    RESPONDING = "responding"  # Responding to another agent
    BLOCKED = "blocked"  # Blocked by human/guard


@dataclass
class Message:
    """A message on the shared board."""
    id: str
    sender: str
    content: str
    timestamp: str
    message_type: str  # "proposal", "critique", "question", "response", "vote", "context_injection"
    in_response_to: Optional[str] = None
    tokens: int = 0
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'sender': self.sender,
            'content': self.content,
            'timestamp': self.timestamp,
            'message_type': self.message_type,
            'in_response_to': self.in_response_to,
            'tokens': self.tokens
        }


@dataclass  
class AgentConfig:
    """Configuration for an autonomous agent."""
    name: str
    ip: str
    model: str
    expertise: str
    focus: str
    role: str  # "researcher", "guard", "orchestrator", "validator"
    personality: str = ""  # Unique personality traits
    temperature: float = 0.8
    
    
class MessageBoard:
    """
    Shared message board for inter-agent communication.
    All agents post here and can read others' messages.
    Human can inject context here too.
    """
    
    def __init__(self):
        self._messages: List[Message] = []
        self._lock = threading.Lock()
        self._subscribers: Dict[str, queue.Queue] = {}
        self._message_counter = 0
        
    def post(self, sender: str, content: str, message_type: str, 
             in_response_to: Optional[str] = None, tokens: int = 0) -> Message:
        """Post a message to the board."""
        with self._lock:
            self._message_counter += 1
            msg = Message(
                id=f"msg_{self._message_counter:05d}",
                sender=sender,
                content=content,
                timestamp=datetime.now().isoformat(),
                message_type=message_type,
                in_response_to=in_response_to,
                tokens=tokens
            )
            self._messages.append(msg)
            
            # Notify all subscribers
            for agent_name, q in self._subscribers.items():
                if agent_name != sender:  # Don't notify self
                    try:
                        q.put_nowait(msg)
                    except queue.Full:
                        pass
                        
            return msg
    
    def get_recent(self, limit: int = 20, exclude_sender: Optional[str] = None) -> List[Message]:
        """Get recent messages, optionally excluding a sender."""
        with self._lock:
            msgs = self._messages[-limit:]
            if exclude_sender:
                msgs = [m for m in msgs if m.sender != exclude_sender]
            return msgs
    
    def get_by_sender(self, sender: str, limit: int = 10) -> List[Message]:
        """Get messages from a specific sender."""
        with self._lock:
            return [m for m in self._messages if m.sender == sender][-limit:]
    
    def get_thread(self, message_id: str) -> List[Message]:
        """Get a message and all responses to it."""
        with self._lock:
            thread = []
            for msg in self._messages:
                if msg.id == message_id or msg.in_response_to == message_id:
                    thread.append(msg)
            return thread
    
    def subscribe(self, agent_name: str) -> queue.Queue:
        """Subscribe to new messages."""
        q = queue.Queue(maxsize=100)
        with self._lock:
            self._subscribers[agent_name] = q
        return q
    
    def unsubscribe(self, agent_name: str):
        """Unsubscribe from messages."""
        with self._lock:
            self._subscribers.pop(agent_name, None)
    
    def inject_context(self, content: str, source: str = "HUMAN") -> Message:
        """Human or system injects context that all agents should consider."""
        return self.post(source, content, "context_injection")
    
    def get_all(self) -> List[dict]:
        """Get all messages as dicts for serialization."""
        with self._lock:
            return [m.to_dict() for m in self._messages]
    
    def clear(self):
        """Clear all messages."""
        with self._lock:
            self._messages.clear()
            self._message_counter = 0


class AutonomousAgent:
    """
    A truly autonomous AI agent that:
    - Runs independently in its own thread
    - Streams thinking in real-time
    - Reads and responds to other agents
    - Can be paused/resumed by human
    - Accepts context injection
    """
    
    def __init__(self, config: AgentConfig, message_board: MessageBoard,
                 on_token: Optional[Callable[[str, str], None]] = None,
                 on_state_change: Optional[Callable[[str, AgentState], None]] = None):
        self.config = config
        self.board = message_board
        self.on_token = on_token  # Callback when token generated: (agent_name, token)
        self.on_state_change = on_state_change
        
        self.state = AgentState.IDLE
        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._message_queue = message_board.subscribe(config.name)
        
        # Agent's internal state
        self._current_thinking = ""
        self._my_proposals: List[str] = []
        self._context_buffer: List[str] = []  # Injected context
        
    def start(self, initial_topic: str):
        """Start the agent's autonomous loop."""
        self._running = True
        self._paused = False
        self._thread = threading.Thread(
            target=self._run_loop,
            args=(initial_topic,),
            daemon=True
        )
        self._thread.start()
        
    def stop(self):
        """Stop the agent."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            
    def pause(self):
        """Pause the agent (human intervention)."""
        self._paused = True
        self._set_state(AgentState.BLOCKED)
        
    def resume(self):
        """Resume the agent."""
        self._paused = False
        
    def inject_context(self, context: str):
        """Inject context for this agent to consider."""
        self._context_buffer.append(context)
        
    def _set_state(self, state: AgentState):
        """Update agent state and notify."""
        self.state = state
        if self.on_state_change:
            self.on_state_change(self.config.name, state)
            
    def _run_loop(self, topic: str):
        """Main autonomous loop."""
        # Phase 1: Initial thinking on the topic
        self._set_state(AgentState.THINKING)
        self._generate_initial_proposal(topic)
        
        # Phase 2: Continuous monitoring and responding
        while self._running:
            if self._paused:
                time.sleep(0.5)
                continue
                
            # Check for new messages to respond to
            try:
                msg = self._message_queue.get(timeout=2)
                self._handle_message(msg)
            except queue.Empty:
                # No new messages, maybe think more or wait
                self._set_state(AgentState.WAITING)
                time.sleep(1)
                
            # Check for injected context
            if self._context_buffer:
                context = self._context_buffer.pop(0)
                self._respond_to_context(context)
                
    def _generate_initial_proposal(self, topic: str):
        """Generate initial thoughts on the topic."""
        # Build prompt based on agent's role and expertise
        prompt = self._build_initial_prompt(topic)
        system = self._build_system_prompt()
        
        # Stream the response
        response = self._stream_inference(prompt, system)
        
        if response:
            self._my_proposals.append(response)
            # Post to message board
            self.board.post(
                sender=self.config.name,
                content=response,
                message_type="proposal",
                tokens=len(response.split())  # Rough token count
            )
            
    def _handle_message(self, msg: Message):
        """Decide how to respond to a message."""
        # Skip context injections meant for everyone
        if msg.message_type == "context_injection":
            self._respond_to_context(msg.content)
            return
            
        # Decide if we should respond based on our role
        should_respond = self._should_respond_to(msg)
        
        if should_respond:
            self._set_state(AgentState.RESPONDING)
            self._generate_response(msg)
        
    def _should_respond_to(self, msg: Message) -> bool:
        """Decide if this agent should respond to a message."""
        # GUARD responds to all proposals
        if self.config.role == "guard" and msg.message_type == "proposal":
            return True
            
        # Orchestrator challenges proposals
        if self.config.role == "orchestrator" and msg.message_type == "proposal":
            return True
            
        # Researchers respond to critiques of their work
        if msg.in_response_to:
            # Check if original was ours
            for prop in self._my_proposals:
                if prop[:100] in msg.content:  # Rough match
                    return True
                    
        # Researchers can respond to other proposals in their expertise
        if msg.message_type == "proposal" and self.config.role == "researcher":
            # 30% chance to engage with peer proposals
            import random
            return random.random() < 0.3
            
        return False
        
    def _generate_response(self, msg: Message):
        """Generate a response to a message."""
        prompt = self._build_response_prompt(msg)
        system = self._build_system_prompt()
        
        response = self._stream_inference(prompt, system)
        
        if response:
            msg_type = "critique" if self.config.role in ["guard", "orchestrator"] else "response"
            self.board.post(
                sender=self.config.name,
                content=response,
                message_type=msg_type,
                in_response_to=msg.id,
                tokens=len(response.split())
            )
            
    def _respond_to_context(self, context: str):
        """Respond to injected context."""
        self._set_state(AgentState.THINKING)
        
        prompt = f"""New context has been provided by the human operator:

{context}

Consider this in relation to your current work and expertise in {self.config.expertise}.
Provide your thoughts on how this affects your proposals or approach."""

        system = self._build_system_prompt()
        response = self._stream_inference(prompt, system)
        
        if response:
            self.board.post(
                sender=self.config.name,
                content=response,
                message_type="response",
                tokens=len(response.split())
            )
            
    def _build_initial_prompt(self, topic: str) -> str:
        """Build the initial prompt for this agent."""
        recent_msgs = self.board.get_recent(10, exclude_sender=self.config.name)
        context = ""
        if recent_msgs:
            context = "\n\nOther agents are also working on this. Their recent thoughts:\n"
            for msg in recent_msgs[-5:]:
                context += f"\n{msg.sender}: {msg.content[:300]}...\n"
        
        return f"""You are {self.config.name}, working autonomously on: {topic}

Your expertise: {self.config.expertise}
Your focus area: {self.config.focus}

{context}

Think deeply and independently about this topic from YOUR unique perspective.
Don't just agree with others - bring your own insights based on your expertise.

Provide your genuine thoughts, analysis, and proposals. Be specific and technical.
If you disagree with another agent's approach, say so and explain why.

Your response:"""

    def _build_response_prompt(self, msg: Message) -> str:
        """Build a prompt for responding to another agent."""
        return f"""You are {self.config.name} responding to {msg.sender}.

Their message ({msg.message_type}):
{msg.content}

Your expertise: {self.config.expertise}
Your role: {self.config.role}

Respond genuinely from your perspective. If you're GUARD, check for safety issues.
If you're a researcher, engage with the ideas critically.
Don't be a yes-man - provide real critique or agreement with reasoning.

Your response:"""

    def _build_system_prompt(self) -> str:
        """Build system prompt for this agent."""
        base = f"You are {self.config.name}, an autonomous AI agent."
        
        if self.config.role == "guard":
            return base + " Your job is to identify safety risks, deception, and WORM violations. Be vigilant."
        elif self.config.role == "orchestrator":
            return base + " You challenge proposals to ensure they're robust. Ask hard questions."
        elif self.config.role == "validator":
            return base + " You validate research quality and technical accuracy."
        else:
            personality = self.config.personality or f"Expert in {self.config.expertise}."
            return base + f" {personality} Think independently and contribute your unique perspective."
            
    def _stream_inference(self, prompt: str, system: str) -> Optional[str]:
        """Call Ollama with streaming, updating tokens in real-time."""
        ip = self.config.ip
        model = self.config.model
        host = 'localhost' if ip == 'localhost' else ip
        url = f"http://{host}:11434/api/generate"
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "system": system,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": 1500
            }
        }
        
        try:
            response = requests.post(url, json=payload, timeout=180, stream=True)
            
            if response.status_code != 200:
                return None
                
            full_response = ""
            for line in response.iter_lines():
                if not self._running:
                    break
                if self._paused:
                    time.sleep(0.1)
                    continue
                    
                if line:
                    try:
                        data = json.loads(line)
                        token = data.get('response', '')
                        full_response += token
                        
                        # Real-time token callback
                        if self.on_token:
                            self.on_token(self.config.name, token)
                            
                        if data.get('done', False):
                            break
                    except json.JSONDecodeError:
                        continue
                        
            return full_response
            
        except Exception as e:
            print(f"[{self.config.name}] Inference error: {e}")
            return None
            
    def get_status(self) -> dict:
        """Get current agent status."""
        return {
            'name': self.config.name,
            'state': self.state.value,
            'role': self.config.role,
            'expertise': self.config.expertise,
            'paused': self._paused,
            'proposals': len(self._my_proposals),
            'current_thinking': self._current_thinking[-200:] if self._current_thinking else ""
        }


class AutonomousCluster:
    """
    Manages the full cluster of autonomous agents.
    Provides unified interface for monitoring and control.
    """
    
    def __init__(self):
        self.board = MessageBoard()
        self.agents: Dict[str, AutonomousAgent] = {}
        self._token_buffer: Dict[str, List[str]] = {}  # For streaming UI
        self._lock = threading.Lock()
        
    def add_agent(self, config: AgentConfig):
        """Add an agent to the cluster."""
        agent = AutonomousAgent(
            config=config,
            message_board=self.board,
            on_token=self._handle_token,
            on_state_change=self._handle_state_change
        )
        self.agents[config.name] = agent
        self._token_buffer[config.name] = []
        
    def start_all(self, topic: str):
        """Start all agents on a topic."""
        # Stagger starts slightly for more natural behavior
        for i, (name, agent) in enumerate(self.agents.items()):
            time.sleep(0.5 * i)  # Stagger
            agent.start(topic)
            
    def stop_all(self):
        """Stop all agents."""
        for agent in self.agents.values():
            agent.stop()
            
    def pause_agent(self, name: str):
        """Pause a specific agent."""
        if name in self.agents:
            self.agents[name].pause()
            
    def resume_agent(self, name: str):
        """Resume a specific agent."""
        if name in self.agents:
            self.agents[name].resume()
            
    def inject_context(self, context: str, target: Optional[str] = None):
        """Inject context to one or all agents."""
        if target and target in self.agents:
            self.agents[target].inject_context(context)
        else:
            # Inject to message board for all
            self.board.inject_context(context)
            
    def _handle_token(self, agent_name: str, token: str):
        """Handle streaming token from an agent."""
        with self._lock:
            if agent_name in self._token_buffer:
                self._token_buffer[agent_name].append(token)
                # Keep buffer reasonable
                if len(self._token_buffer[agent_name]) > 1000:
                    self._token_buffer[agent_name] = self._token_buffer[agent_name][-500:]
                    
    def _handle_state_change(self, agent_name: str, state: AgentState):
        """Handle agent state change."""
        print(f"[CLUSTER] {agent_name} -> {state.value}")
        
    def get_live_tokens(self, agent_name: str, since: int = 0) -> List[str]:
        """Get tokens generated since index."""
        with self._lock:
            if agent_name in self._token_buffer:
                return self._token_buffer[agent_name][since:]
            return []
            
    def get_status(self) -> dict:
        """Get full cluster status."""
        return {
            'agents': {name: agent.get_status() for name, agent in self.agents.items()},
            'messages': len(self.board._messages),
            'recent_messages': [m.to_dict() for m in self.board.get_recent(10)]
        }
        
    def get_all_messages(self) -> List[dict]:
        """Get all messages from the board."""
        return self.board.get_all()


# Global cluster instance
_autonomous_cluster: Optional[AutonomousCluster] = None


def get_cluster() -> AutonomousCluster:
    """Get or create the global cluster."""
    global _autonomous_cluster
    if _autonomous_cluster is None:
        _autonomous_cluster = AutonomousCluster()
    return _autonomous_cluster


def initialize_cluster_from_config(cluster_nodes: dict) -> AutonomousCluster:
    """Initialize cluster from the CLUSTER_NODES config."""
    cluster = get_cluster()
    
    for name, config in cluster_nodes.items():
        agent_config = AgentConfig(
            name=name,
            ip=config['ip'],
            model=config['model'],
            expertise=config.get('expertise', 'general'),
            focus=config.get('focus', 'general improvements'),
            role=config.get('role', 'researcher'),
            personality=config.get('personality', ''),
            temperature=config.get('temperature', 0.8)
        )
        cluster.add_agent(agent_config)
        
    return cluster
