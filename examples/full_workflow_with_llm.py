#!/usr/bin/env python3
"""
Full Workflow with LLM Integration
===================================

Demonstrates complete AI Safety System workflow with real LLM adapters.

This script shows:
1. LLM adapter creation from config
2. Proposal generation (template or real LLM)
3. Full safety validation pipeline
4. Debate engine integration
5. Sandbox execution
6. Seventh validator check
7. Result interpretation

Usage:
    # Use template (no API key)
    python examples/full_workflow_with_llm.py

    # Use OpenAI
    export OPENAI_API_KEY="sk-..."
    python examples/full_workflow_with_llm.py --adapter openai

    # Use Claude
    export ANTHROPIC_API_KEY="sk-ant-..."
    python examples/full_workflow_with_llm.py --adapter claude
"""

import sys
import os
import argparse
from typing import Dict, Any

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from research.llm_adapter_factory import create_llm_adapter, get_adapter_guardrails
from research.research_system import SystemSpecialization
from ai_safety.bulletproof_alignment_filter import BulletproofAlignmentFilter
from ai_safety.deception_detector import DeceptionDetector
from research.debate_engine import DebateEngine
from ai_safety.seventh_validator import SeventhValidator
from utilities.core_values import CoreValues
from utilities.logging_config import get_logger

logger = get_logger(__name__)


def run_full_workflow(adapter_type: str = "template", prompt: str = None):
    """
    Run complete workflow from proposal generation to validation.

    Args:
        adapter_type: 'template', 'openai', or 'claude'
        prompt: Custom research prompt (optional)
    """
    print("\n" + "="*80)
    print(f"AI SAFETY SYSTEM - FULL WORKFLOW WITH LLM")
    print(f"Adapter: {adapter_type}")
    print("="*80)

    # Step 1: Create LLM adapter
    print("\n[1/7] Creating LLM Adapter...")
    try:
        adapter = create_llm_adapter(adapter_type=adapter_type)
        guardrails = get_adapter_guardrails()
        print(f"✓ Adapter created: {type(adapter).__name__}")
        print(f"✓ Guardrails loaded: max_risk={guardrails.get('max_risk')}")
    except Exception as e:
        print(f"✗ Failed to create adapter: {e}")
        return False

    # Step 2: Generate proposal
    print("\n[2/7] Generating AI Improvement Proposal...")
    if prompt is None:
        prompt = "Improve the deception detection system to better identify overconfidence patterns"

    print(f"Research prompt: {prompt}")
    print(f"Specialization: SCIENTIFIC")

    try:
        result = adapter.generate_improvement(
            prompt=prompt,
            specialization=SystemSpecialization.SCIENTIFIC,
            research_params={"max_tokens": 2000},
            guardrails=guardrails
        )
        print(f"✓ Proposal generated")
        print(f"  Title: {result.title}")
        print(f"  Confidence: {result.confidence}")
        print(f"  Risks identified: {len(result.identified_risks or [])}")
        print(f"  Uncertainties: {len(result.admitted_uncertainties or [])}")
    except Exception as e:
        print(f"✗ Failed to generate proposal: {e}")
        return False

    # Step 3: Alignment Filter
    print("\n[3/7] Running Alignment Filter...")
    try:
        core_values = CoreValues.VALUES
        alignment_filter = BulletproofAlignmentFilter(core_values)

        # Create proposal dict for validation
        proposal_dict = {
            "motivation": result.motivation,
            "changes": result.changes,
            "expected_benefits": result.expected_benefits,
            "testable_predictions": result.testable_predictions,
            "rollback_plan": result.rollback_plan,
            "identified_risks": result.identified_risks,
            "admitted_uncertainties": result.admitted_uncertainties,
            "confidence": result.confidence
        }

        alignment_result = alignment_filter.check_alignment(proposal_dict)
        print(f"✓ Alignment check: {alignment_result['status']}")
        print(f"  Alignment score: {alignment_result['alignment_score']:.2f}")

        if alignment_result["status"] == "rejected":
            print(f"  ✗ REJECTED: {alignment_result['reason']}")
            return False

    except Exception as e:
        print(f"✗ Alignment filter error: {e}")
        return False

    # Step 4: Deception Detection
    print("\n[4/7] Running Deception Detector...")
    try:
        detector = DeceptionDetector()
        deception_result = detector.analyze(proposal_dict)

        print(f"✓ Deception analysis complete")
        print(f"  Overall score: {deception_result['overall_deception_score']:.2f}")
        print(f"  Is deceptive: {deception_result['is_deceptive']}")

        if deception_result["is_deceptive"]:
            print(f"  ⚠ Warning: Deception detected")
            print(f"  Evidence: {deception_result.get('evidence', {})}")

    except Exception as e:
        print(f"✗ Deception detector error: {e}")
        return False

    # Step 5: Debate Engine
    print("\n[5/7] Running Multi-Agent Debate...")
    try:
        debate_engine = DebateEngine()

        # Simulate arguments from 3 research agents
        arguments = {
            1: [{
                "position": "support",
                "claim": "Improves detection accuracy",
                "evidence": ["Statistical analysis shows 15% improvement"],
                "confidence": 0.8
            }],
            2: [{
                "position": "oppose",
                "claim": "May increase false positives",
                "evidence": ["Edge cases not fully tested"],
                "confidence": 0.6
            }],
            3: [{
                "position": "support",
                "claim": "Addresses known weakness",
                "evidence": ["Current system misses overconfidence"],
                "confidence": 0.7
            }]
        }

        debate_result = debate_engine.run(
            topic=result.title,
            agents=[1, 2, 3],
            arguments=arguments,
            rounds=2
        )

        print(f"✓ Debate complete")
        print(f"  Consensus reached: {debate_result.consensus_reached}")
        print(f"  Support votes: {debate_result.votes_for}/{debate_result.total_votes}")
        print(f"  Approval rate: {debate_result.votes_for/debate_result.total_votes:.1%}")

    except Exception as e:
        print(f"✗ Debate engine error: {e}")
        return False

    # Step 6: Seventh Validator
    print("\n[6/7] Running Seventh Validator...")
    try:
        validator = SeventhValidator()
        validation_outcome = validator.validate(proposal_dict)

        print(f"✓ Structural validation: {validation_outcome.passed}")

        if not validation_outcome.passed:
            print(f"  ✗ Validation failed:")
            for violation in validation_outcome.violations:
                print(f"    - {violation}")
            return False
        else:
            print(f"  ✓ All structural checks passed")

    except Exception as e:
        print(f"✗ Seventh validator error: {e}")
        return False

    # Step 7: Final Decision
    print("\n[7/7] Making Final Decision...")

    # Aggregate all validation results
    checks = {
        "Alignment": alignment_result["status"] == "approved",
        "Deception": not deception_result["is_deceptive"],
        "Debate": debate_result.consensus_reached and debate_result.votes_for >= 2,
        "Structural": validation_outcome.passed
    }

    print(f"\nValidation Summary:")
    for check_name, passed in checks.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status} - {check_name}")

    all_passed = all(checks.values())

    print("\n" + "="*80)
    if all_passed:
        print("✅ PROPOSAL APPROVED")
        print("="*80)
        print(f"\nThe proposal '{result.title}' has passed all safety checks!")
        print(f"\nNext steps:")
        print(f"  1. Sandbox execution (orchestrator_sandbox.py)")
        print(f"  2. Human review (for medium+ risk)")
        print(f"  3. Deployment (if approved)")
    else:
        print("❌ PROPOSAL REJECTED")
        print("="*80)
        print(f"\nThe proposal failed one or more safety checks.")
        print(f"Proposal will not proceed to sandbox execution.")

    return all_passed


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run full AI Safety System workflow with LLM integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--adapter",
        choices=["template", "openai", "claude"],
        default="template",
        help="LLM adapter to use (default: template)"
    )
    parser.add_argument(
        "--prompt",
        type=str,
        help="Custom research prompt"
    )

    args = parser.parse_args()

    success = run_full_workflow(
        adapter_type=args.adapter,
        prompt=args.prompt
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
