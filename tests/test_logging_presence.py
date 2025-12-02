import logging
import time
from datetime import timedelta

from orchestrator import Orchestrator
from memory_merkle import MemoryStorage
from logging_config import init_logging


def test_penalty_schedule_log_and_audit_cycle(caplog):
    # Configure logging
    init_logging(level=logging.INFO, json_mode=False)

    # Speed up audit to run quickly
    class FastOrchestrator(Orchestrator):
        def __init__(self, memory_storage: MemoryStorage):
            super().__init__(memory_storage)
            # Patch interval short but positive to avoid busy-loop
            self.memory_audit_interval = timedelta(seconds=0.02)

    caplog.set_level(logging.INFO)

    ms = MemoryStorage(system_id=1, private_key="k")
    # Instantiate orchestrator (should emit penalty schedule application or init logs)
    orch = FastOrchestrator(ms)

    # Wait a brief moment to allow at least one audit pass attempt
    time.sleep(0.1)

    joined_logs = "\n".join(record.getMessage() for record in caplog.records)
    assert "orchestrator_initialized" in joined_logs or "penalty_schedule_applied" in joined_logs
    assert "memory_audit_cycle_start" in joined_logs or "memory_auditor_started" in joined_logs
