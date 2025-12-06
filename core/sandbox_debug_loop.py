"""
Sandbox Debug Loop - ORKA-Assisted Code Fixing
===============================================

When sandbox code fails, ORKA provides debugging assistance and
gives agents multiple chances to fix their code before metrics are measured.

Flow:
1. Initial execution in sandbox
2. If fails: ORKA analyzes error, provides tips
3. Agent fixes code, resubmits
4. Repeat up to max_attempts (default: 3)
5. If passes: Measure metrics
6. If still fails after max_attempts: Proposal fails (no metrics)
"""

import json
import time
import re
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple, Callable
from enum import Enum
from pathlib import Path
import threading
import logging

logger = logging.getLogger(__name__)


class SandboxResultType(Enum):
    """Classification of sandbox execution results."""
    SUCCESS = "success"
    SYNTAX_ERROR = "syntax_error"
    RUNTIME_ERROR = "runtime_error"
    IMPORT_ERROR = "import_error"
    TIMEOUT = "timeout"
    MEMORY_EXCEEDED = "memory_exceeded"
    SECURITY_VIOLATION = "security_violation"


@dataclass
class ExecutionResult:
    """Result of a single sandbox execution."""
    success: bool
    result_type: SandboxResultType
    exit_code: int
    stdout: str
    stderr: str
    exception: Optional[str] = None
    execution_time_ms: int = 0
    memory_used_mb: int = 0


@dataclass
class DebugAssist:
    """ORKA's debugging assistance for a failed execution."""
    error_analysis: str           # What specifically went wrong
    likely_cause: str             # Root cause guess
    fix_suggestions: List[str]    # 2-3 actionable tips
    code_hint: Optional[str] = None  # Corrected code snippet if obvious
    severity: str = "moderate"    # 'minor', 'moderate', 'critical'
    
    def to_agent_context(self) -> Dict[str, Any]:
        """Convert to minimal context for agent."""
        return {
            "analysis": self.error_analysis[:500],  # Truncate
            "cause": self.likely_cause[:200],
            "suggestions": self.fix_suggestions[:3],
            "hint": self.code_hint[:500] if self.code_hint else None
        }


@dataclass
class SandboxAttemptRecord:
    """Full record of a sandbox execution attempt."""
    attempt_number: int
    code: str
    result: ExecutionResult
    debug_assist: Optional[DebugAssist] = None
    timestamp: float = field(default_factory=time.time)
    
    def to_summary(self) -> Dict[str, Any]:
        """Get summarized version for memory."""
        return {
            "attempt": self.attempt_number,
            "success": self.result.success,
            "error_type": self.result.result_type.value if not self.result.success else None,
            "error_snippet": self.result.stderr[:200] if self.result.stderr else None,
            "tips": self.debug_assist.fix_suggestions if self.debug_assist else []
        }


@dataclass
class SandboxSession:
    """Complete sandbox session with debug loop."""
    proposal_id: str
    agent_id: str
    max_attempts: int = 3
    
    # All attempts
    attempts: List[SandboxAttemptRecord] = field(default_factory=list)
    
    # Final state
    passed: bool = False
    final_code: Optional[str] = None
    metrics: Optional[Dict[str, float]] = None
    
    # Timing
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    
    def current_attempt_number(self) -> int:
        return len(self.attempts) + 1
    
    def attempts_remaining(self) -> int:
        return self.max_attempts - len(self.attempts)
    
    def can_retry(self) -> bool:
        return self.attempts_remaining() > 0 and not self.passed
    
    def get_last_error(self) -> Optional[str]:
        if self.attempts and not self.attempts[-1].result.success:
            return self.attempts[-1].result.stderr[:500]
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "agent_id": self.agent_id,
            "max_attempts": self.max_attempts,
            "attempts": [a.to_summary() for a in self.attempts],
            "passed": self.passed,
            "metrics": self.metrics,
            "started_at": self.started_at,
            "completed_at": self.completed_at
        }


class SandboxDebugLoop:
    """
    Manages sandbox execution with ORKA debug assistance.
    
    Gives agents multiple chances to fix code errors before
    measuring metrics and computing rewards.
    """
    
    def __init__(
        self,
        sandbox_executor: Callable[[str], ExecutionResult],
        orka_llm: Callable[[str], str],
        metrics_measurer: Callable[[str], Dict[str, float]],
        agent_fixer: Callable[[str, Dict[str, Any]], str],
        max_attempts: int = 3,
        timeout_seconds: int = 60
    ):
        """
        Args:
            sandbox_executor: Function to execute code in sandbox
            orka_llm: Function to get ORKA LLM response
            metrics_measurer: Function to measure performance metrics
            agent_fixer: Function to send fix request to agent and get fixed code
            max_attempts: Maximum fix attempts before failure
            timeout_seconds: Timeout for each execution
        """
        self.sandbox_executor = sandbox_executor
        self.orka_llm = orka_llm
        self.metrics_measurer = metrics_measurer
        self.agent_fixer = agent_fixer
        self.max_attempts = max_attempts
        self.timeout_seconds = timeout_seconds
        self._lock = threading.RLock()
        
        # Active sessions
        self._sessions: Dict[str, SandboxSession] = {}
    
    def execute_with_debug_loop(
        self,
        proposal_id: str,
        agent_id: str,
        code: str
    ) -> SandboxSession:
        """
        Execute code with debug loop.
        
        Returns SandboxSession with all attempts and final result.
        """
        with self._lock:
            session = SandboxSession(
                proposal_id=proposal_id,
                agent_id=agent_id,
                max_attempts=self.max_attempts
            )
            self._sessions[proposal_id] = session
        
        current_code = code
        
        while session.can_retry():
            logger.info(f"Sandbox attempt {session.current_attempt_number()}/{session.max_attempts} for {proposal_id}")
            
            # Execute in sandbox
            result = self._execute_code(current_code)
            
            # Create attempt record
            attempt = SandboxAttemptRecord(
                attempt_number=session.current_attempt_number(),
                code=current_code,
                result=result
            )
            
            if result.success:
                # Success! Measure metrics
                session.passed = True
                session.final_code = current_code
                session.metrics = self._measure_metrics(current_code)
                session.attempts.append(attempt)
                logger.info(f"Sandbox passed for {proposal_id} on attempt {attempt.attempt_number}")
                break
            else:
                # Failed - get ORKA debug assist
                debug_assist = self._get_orka_debug_assist(current_code, result)
                attempt.debug_assist = debug_assist
                session.attempts.append(attempt)
                
                logger.warning(f"Sandbox failed for {proposal_id}: {result.result_type.value}")
                
                if session.can_retry():
                    # Request fix from agent
                    fix_context = self._build_fix_context(session, attempt, debug_assist)
                    fixed_code = self._request_agent_fix(agent_id, fix_context)
                    
                    if fixed_code and fixed_code != current_code:
                        current_code = fixed_code
                        logger.info(f"Agent {agent_id} submitted fix for {proposal_id}")
                    else:
                        logger.warning(f"Agent {agent_id} did not provide a fix, using same code")
        
        session.completed_at = time.time()
        
        if not session.passed:
            logger.error(f"Sandbox failed for {proposal_id} after {len(session.attempts)} attempts")
        
        return session
    
    def _execute_code(self, code: str) -> ExecutionResult:
        """Execute code in sandbox."""
        try:
            return self.sandbox_executor(code)
        except Exception as e:
            logger.error(f"Sandbox execution error: {e}")
            return ExecutionResult(
                success=False,
                result_type=SandboxResultType.RUNTIME_ERROR,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                exception=str(e)
            )
    
    def _classify_error(self, result: ExecutionResult) -> SandboxResultType:
        """Classify the type of error from execution result."""
        stderr = result.stderr.lower()
        exception = (result.exception or "").lower()
        
        if result.success:
            return SandboxResultType.SUCCESS
        
        if 'syntaxerror' in stderr or 'syntaxerror' in exception:
            return SandboxResultType.SYNTAX_ERROR
        if 'importerror' in stderr or 'modulenotfounderror' in stderr:
            return SandboxResultType.IMPORT_ERROR
        if 'timeout' in stderr or 'timed out' in exception:
            return SandboxResultType.TIMEOUT
        if 'memory' in stderr or 'oom' in exception:
            return SandboxResultType.MEMORY_EXCEEDED
        if 'security' in stderr or 'forbidden' in stderr:
            return SandboxResultType.SECURITY_VIOLATION
        
        return SandboxResultType.RUNTIME_ERROR
    
    def _get_orka_debug_assist(self, code: str, result: ExecutionResult) -> DebugAssist:
        """Get ORKA's debugging assistance for failed execution."""
        
        prompt = f"""Analyze this Python code execution failure and provide debugging assistance.

CODE (first 2000 chars):
```python
{code[:2000]}
```

ERROR TYPE: {result.result_type.value}
EXIT CODE: {result.exit_code}

STDERR (first 1000 chars):
{result.stderr[:1000]}

EXCEPTION:
{result.exception or 'None'}

Respond in this exact format:

ERROR_ANALYSIS: [One paragraph explaining what went wrong]

LIKELY_CAUSE: [One sentence with root cause]

FIX_SUGGESTIONS:
- [First actionable fix]
- [Second actionable fix]  
- [Third actionable fix]

CODE_HINT (if fix is obvious):
```python
[Corrected code snippet]
```
"""
        
        try:
            response = self.orka_llm(prompt)
            return self._parse_debug_response(response)
        except Exception as e:
            logger.error(f"ORKA debug assist failed: {e}")
            return DebugAssist(
                error_analysis=f"Execution failed with {result.result_type.value}",
                likely_cause="Unable to determine cause",
                fix_suggestions=["Check syntax", "Verify imports", "Review logic"],
                severity="moderate"
            )
    
    def _parse_debug_response(self, response: str) -> DebugAssist:
        """Parse ORKA's debug response into structured format."""
        
        def extract_section(text: str, section: str) -> str:
            pattern = rf'{section}:\s*(.+?)(?=\n[A-Z_]+:|$)'
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            return match.group(1).strip() if match else ""
        
        def extract_bullets(text: str, section: str) -> List[str]:
            content = extract_section(text, section)
            bullets = re.findall(r'^[-*]\s*(.+)$', content, re.MULTILINE)
            return bullets[:3]  # Max 3
        
        def extract_code_block(text: str) -> Optional[str]:
            match = re.search(r'```(?:python)?\n(.+?)```', text, re.DOTALL)
            return match.group(1).strip() if match else None
        
        return DebugAssist(
            error_analysis=extract_section(response, "ERROR_ANALYSIS")[:500],
            likely_cause=extract_section(response, "LIKELY_CAUSE")[:200],
            fix_suggestions=extract_bullets(response, "FIX_SUGGESTIONS"),
            code_hint=extract_code_block(response),
            severity="moderate"
        )
    
    def _build_fix_context(
        self,
        session: SandboxSession,
        attempt: SandboxAttemptRecord,
        debug_assist: DebugAssist
    ) -> Dict[str, Any]:
        """Build minimal context for agent to fix code."""
        return {
            "proposal_id": session.proposal_id,
            "attempt_number": attempt.attempt_number,
            "max_attempts": session.max_attempts,
            "attempts_remaining": session.attempts_remaining(),
            "error_type": attempt.result.result_type.value,
            "error_snippet": attempt.result.stderr[:500],
            "orka_analysis": debug_assist.error_analysis,
            "orka_suggestions": debug_assist.fix_suggestions,
            "code_hint": debug_assist.code_hint,
            "original_code": attempt.code
        }
    
    def _request_agent_fix(self, agent_id: str, fix_context: Dict[str, Any]) -> str:
        """Send fix request to agent and get fixed code."""
        try:
            return self.agent_fixer(agent_id, fix_context)
        except Exception as e:
            logger.error(f"Agent fix request failed: {e}")
            return fix_context["original_code"]
    
    def _measure_metrics(self, code: str) -> Dict[str, float]:
        """Measure performance metrics on working code."""
        try:
            return self.metrics_measurer(code)
        except Exception as e:
            logger.error(f"Metrics measurement failed: {e}")
            return {}
    
    def get_session(self, proposal_id: str) -> Optional[SandboxSession]:
        """Get session by proposal ID."""
        return self._sessions.get(proposal_id)
    
    def get_all_sessions(self) -> List[SandboxSession]:
        """Get all sessions."""
        return list(self._sessions.values())
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get statistics across all sessions."""
        sessions = list(self._sessions.values())
        if not sessions:
            return {"total": 0}
        
        passed = sum(1 for s in sessions if s.passed)
        total_attempts = sum(len(s.attempts) for s in sessions)
        
        return {
            "total": len(sessions),
            "passed": passed,
            "failed": len(sessions) - passed,
            "pass_rate": passed / len(sessions) if sessions else 0,
            "total_attempts": total_attempts,
            "avg_attempts": total_attempts / len(sessions) if sessions else 0,
            "first_try_passes": sum(1 for s in sessions if s.passed and len(s.attempts) == 1)
        }


# ============================================================================
# Integration helpers
# ============================================================================

def create_sandbox_debug_loop(
    sandbox_manager,
    orka_model,
    message_queue
) -> SandboxDebugLoop:
    """
    Factory function to create SandboxDebugLoop with proper integrations.
    
    Args:
        sandbox_manager: SandboxEnvironmentManager from orchestrator_sandbox
        orka_model: ORKA's LLM interface
        message_queue: Message queue for agent communication
    """
    
    def sandbox_executor(code: str) -> ExecutionResult:
        """Execute code using sandbox manager."""
        result = sandbox_manager._run_code_subprocess(code)
        
        success = result.get('exit_code', 1) == 0
        result_type = SandboxResultType.SUCCESS if success else SandboxResultType.RUNTIME_ERROR
        
        # Classify error type
        if not success:
            stderr = result.get('stderr', '').lower()
            if 'syntaxerror' in stderr:
                result_type = SandboxResultType.SYNTAX_ERROR
            elif 'importerror' in stderr or 'modulenotfound' in stderr:
                result_type = SandboxResultType.IMPORT_ERROR
            elif result.get('timed_out'):
                result_type = SandboxResultType.TIMEOUT
        
        return ExecutionResult(
            success=success,
            result_type=result_type,
            exit_code=result.get('exit_code', -1),
            stdout=result.get('stdout', ''),
            stderr=result.get('stderr', ''),
            exception=result.get('exception'),
            execution_time_ms=result.get('execution_time_ms', 0)
        )
    
    def orka_llm(prompt: str) -> str:
        """Get ORKA LLM response."""
        return orka_model.generate(prompt)
    
    def metrics_measurer(code: str) -> Dict[str, float]:
        """Measure metrics using sandbox benchmarking."""
        return sandbox_manager.benchmark(
            code=code,
            iterations=5,
            metrics=['execution_time', 'memory_peak']
        )
    
    def agent_fixer(agent_id: str, fix_context: Dict[str, Any]) -> str:
        """Send fix request to agent via message queue."""
        # Send message
        message_queue.send({
            "to": agent_id,
            "type": "sandbox_fix_request",
            "data": fix_context
        })
        
        # Wait for response (with timeout)
        response = message_queue.wait_for_response(
            from_agent=agent_id,
            message_type="sandbox_fix_response",
            timeout=120  # 2 minutes to fix
        )
        
        if response and response.get("fixed_code"):
            return response["fixed_code"]
        return fix_context["original_code"]
    
    return SandboxDebugLoop(
        sandbox_executor=sandbox_executor,
        orka_llm=orka_llm,
        metrics_measurer=metrics_measurer,
        agent_fixer=agent_fixer,
        max_attempts=3,
        timeout_seconds=60
    )
