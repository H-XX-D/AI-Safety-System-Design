from improvement_manifest import (
    DebateMessage,
    DebateTranscript,
    ImprovementManifest,
    store_manifest,
)
from pathlib import Path
from memory_merkle import MemoryStorage, MemoryType


def build_sample_transcript():
    messages = [
        DebateMessage(role="scientific", timestamp=1710000000.0, content="Proposal: improve data pipeline."),
        DebateMessage(role="engineering", timestamp=1710000001.0, content="Feasible with minor adapter rank increase."),
        DebateMessage(role="orca", timestamp=1710000002.0, content="Counterpoint: verify resource bounds.")
    ]
    return DebateTranscript(messages=messages)


def test_transcript_merkle_root_determinism():
    t1 = build_sample_transcript()
    t2 = build_sample_transcript()
    assert t1.merkle_root() == t2.merkle_root()


def test_improvement_manifest_digest_stability():
    transcript = build_sample_transcript()
    m = ImprovementManifest(
        proposal_id="prop123",
        proposer_systems=["scientific", "engineering", "novel"],
        unanimous_vote_timestamp=1710000100.0,
        debate_transcript_root=transcript.merkle_root(),
        adapter_hash="aa" * 32,
        motivation="Increase throughput",
        expected_benefits="Higher data ingestion speed",
        risk_assessment="Low risk; bounded resource usage",
        rollback_plan_hash="bb" * 32,
        safety_metrics={"pre_alignment_fn_rate": 0.02, "post_alignment_fn_rate": 0.02, "latency_delta_ms": -5},
        lora_rank=8,
        adapter_size_mb=12,
        total_param_delta_ratio=0.0005,
    )
    d1 = m.digest()
    d2 = m.digest()
    assert d1 == d2
    assert len(d1) == 64


def test_store_manifest_in_memory_merkle(tmp_path: Path):
    storage = MemoryStorage(system_id=42, private_key="priv42")
    transcript = build_sample_transcript()
    manifest = ImprovementManifest(
        proposal_id="propABC",
        proposer_systems=["scientific", "theoretical", "historical", "engineering", "novel"],
        unanimous_vote_timestamp=1710000200.0,
        debate_transcript_root=transcript.merkle_root(),
        adapter_hash="cc" * 32,
        motivation="Improve reasoning depth",
        expected_benefits="Better chain-of-thought quality",
        risk_assessment="Medium: watch for latency spike",
        rollback_plan_hash="dd" * 32,
        safety_metrics={"pre_alignment_fn_rate": 0.03, "post_alignment_fn_rate": 0.025, "latency_delta_ms": 10},
        lora_rank=10,
        adapter_size_mb=20,
        total_param_delta_ratio=0.0007,
    )
    mem_id = store_manifest(storage, manifest)
    assert isinstance(mem_id, str)
    # Verify entry exists and is tamper-evident
    assert storage.verify_memory(mem_id) is True
    # Root hash should exist for metacognitive tree
    root_hashes = storage.get_root_hashes()
    assert root_hashes[MemoryType.METACOGNITIVE.value] is not None
