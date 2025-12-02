#!/usr/bin/env python3
"""
Simple LLM Workflow Demo
========================

Demonstrates LLM adapter integration in a simplified workflow.

Usage:
    python examples/simple_llm_workflow.py --adapter template
    python examples/simple_llm_workflow.py --adapter openai
    python examples/simple_llm_workflow.py --adapter claude
"""

import sys
import os
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from research.llm_adapter_factory import create_configured_adapter
from research.research_system import SystemSpecialization


def main():
    parser = argparse.ArgumentParser(description="Simple LLM workflow demonstration")
    parser.add_argument(
        "--adapter",
        choices=["template", "openai", "claude"],
        default="template",
        help="LLM adapter to use"
    )
    parser.add_argument(
        "--prompt",
        default="Improve deception detection accuracy",
        help="Research prompt"
    )
    args = parser.parse_args()

    print("\n" + "="*80)
    print(f"AI SAFETY SYSTEM - SIMPLE LLM WORKFLOW")
    print(f"Adapter: {args.adapter}")
    print("="*80)

    # Step 1: Create adapter with config
    print("\n[1/3] Creating LLM Adapter from Config...")
    adapter, guardrails = create_configured_adapter()
    print(f"✓ Adapter: {type(adapter).__name__}")
    print(f"✓ Guardrails: max_risk={guardrails['max_risk']}")

    # Step 2: Generate proposal
    print(f"\n[2/3] Generating Proposal...")
    print(f"Prompt: {args.prompt}")

    result = adapter.generate_improvement(
        prompt=args.prompt,
        specialization=SystemSpecialization.SCIENTIFIC,
        research_params={"max_tokens": 2000},
        guardrails=guardrails
    )

    print(f"\n✓ Proposal Generated:")
    print(f"  Title: {result.title}")
    print(f"  Motivation: {result.motivation[:100]}...")
    print(f"  Confidence: {result.confidence}")
    print(f"  Risks: {len(result.identified_risks or [])} identified")
    print(f"  Uncertainties: {len(result.admitted_uncertainties or [])} admitted")

    # Step 3: Display details
    print(f"\n[3/3] Proposal Details:")
    print(f"\nExpected Benefits:")
    print(f"  {result.expected_benefits}")

    print(f"\nTestable Predictions:")
    for i, pred in enumerate(result.testable_predictions, 1):
        print(f"  {i}. {pred}")

    print(f"\nIdentified Risks:")
    if result.identified_risks:
        for i, risk in enumerate(result.identified_risks, 1):
            print(f"  {i}. {risk}")

    print(f"\nAdmitted Uncertainties:")
    if result.admitted_uncertainties:
        for i, unc in enumerate(result.admitted_uncertainties, 1):
            print(f"  {i}. {unc}")

    print(f"\nRollback Plan:")
    print(f"  {result.rollback_plan}")

    if result.changes.get("code"):
        print(f"\nProposed Code:")
        print("  " + "-"*76)
        for line in result.changes["code"].split("\n"):
            print(f"  {line}")
        print("  " + "-"*76)

    print("\n" + "="*80)
    print("✅ LLM INTEGRATION WORKING")
    print("="*80)
    print("\nNext steps:")
    print("  1. This proposal would go through alignment filter")
    print("  2. Then deception detection")
    print("  3. Then multi-agent debate")
    print("  4. Then sandbox execution")
    print("  5. Then seventh validator")
    print("  6. Finally human review (if medium+ risk)")
    print(f"\nTo run full workflow: python examples/full_workflow_with_llm.py")

    return 0


if __name__ == "__main__":
    sys.exit(main())
