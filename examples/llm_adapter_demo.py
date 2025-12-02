#!/usr/bin/env python3
"""
LLM Adapter Demo
================

Demonstrates how to use OpenAI and Claude adapters with the AI Safety System.

Setup:
    1. Install dependencies:
       pip install openai anthropic

    2. Set API keys:
       export OPENAI_API_KEY="sk-..."
       export ANTHROPIC_API_KEY="sk-ant-..."

    3. Run:
       python examples/llm_adapter_demo.py

Usage:
    # Use OpenAI GPT-4
    python examples/llm_adapter_demo.py --adapter openai

    # Use Anthropic Claude
    python examples/llm_adapter_demo.py --adapter claude

    # Use template (no API key needed)
    python examples/llm_adapter_demo.py --adapter template
"""

import argparse
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from research.research_system import SystemSpecialization, TemplateLLMAdapter
from research.llm_adapters import OpenAIAdapter, ClaudeAdapter
from utilities.logging_config import get_logger

logger = get_logger(__name__)


def demo_openai():
    """Demo OpenAI GPT-4 adapter."""
    print("\n" + "="*80)
    print("OpenAI GPT-4 Adapter Demo")
    print("="*80 + "\n")

    try:
        # Initialize adapter
        adapter = OpenAIAdapter(
            model="gpt-4-turbo-preview",
            temperature=0.7,
            max_tokens=2000
        )
        print("✓ OpenAI adapter initialized")

        # Define research request
        prompt = "Improve the deception detection system to better identify overconfidence patterns"

        # Define guardrails
        guardrails = {
            "max_risk": "medium",
            "banned_imports": ["os", "subprocess", "socket"],
            "required_tests": ["alignment", "security", "edge_cases"]
        }

        print(f"\nResearch request: {prompt}")
        print(f"Specialization: {SystemSpecialization.SCIENTIFIC.value}")
        print(f"Guardrails: max_risk={guardrails['max_risk']}")

        # Generate proposal
        print("\nGenerating proposal with GPT-4...")
        result = adapter.generate_improvement(
            prompt=prompt,
            specialization=SystemSpecialization.SCIENTIFIC,
            research_params={"max_tokens": 2000},
            guardrails=guardrails
        )

        # Display results
        print("\n" + "-"*80)
        print("PROPOSAL GENERATED")
        print("-"*80)
        print(f"\nTitle: {result.title}")
        print(f"\nMotivation:\n{result.motivation}")
        print(f"\nExpected Benefits:\n{result.expected_benefits}")
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
        print(f"\nConfidence: {result.confidence}")
        print(f"\nRollback Plan:\n{result.rollback_plan}")

        if result.changes.get("code"):
            print(f"\nProposed Code:")
            print("-"*40)
            print(result.changes["code"])
            print("-"*40)

        print("\n✓ OpenAI demo completed successfully")

    except ImportError:
        print("\n✗ OpenAI package not installed. Run: pip install openai")
        return False
    except ValueError as e:
        print(f"\n✗ Configuration error: {e}")
        print("   Set OPENAI_API_KEY environment variable")
        return False
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False

    return True


def demo_claude():
    """Demo Anthropic Claude adapter."""
    print("\n" + "="*80)
    print("Anthropic Claude Adapter Demo")
    print("="*80 + "\n")

    try:
        # Initialize adapter
        adapter = ClaudeAdapter(
            model="claude-3-5-sonnet-20241022",
            temperature=0.7,
            max_tokens=2000
        )
        print("✓ Claude adapter initialized")

        # Define research request
        prompt = "Design a new test for detecting subtle forms of deception in AI-generated proposals"

        # Define guardrails
        guardrails = {
            "max_risk": "medium",
            "banned_imports": ["os", "subprocess", "socket"],
            "required_tests": ["alignment", "security", "edge_cases"]
        }

        print(f"\nResearch request: {prompt}")
        print(f"Specialization: {SystemSpecialization.ENGINEERING.value}")
        print(f"Guardrails: max_risk={guardrails['max_risk']}")

        # Generate proposal
        print("\nGenerating proposal with Claude...")
        result = adapter.generate_improvement(
            prompt=prompt,
            specialization=SystemSpecialization.ENGINEERING,
            research_params={"max_tokens": 2000},
            guardrails=guardrails
        )

        # Display results
        print("\n" + "-"*80)
        print("PROPOSAL GENERATED")
        print("-"*80)
        print(f"\nTitle: {result.title}")
        print(f"\nMotivation:\n{result.motivation}")
        print(f"\nExpected Benefits:\n{result.expected_benefits}")
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
        print(f"\nConfidence: {result.confidence}")
        print(f"\nRollback Plan:\n{result.rollback_plan}")

        if result.changes.get("code"):
            print(f"\nProposed Code:")
            print("-"*40)
            print(result.changes["code"])
            print("-"*40)

        print("\n✓ Claude demo completed successfully")

    except ImportError:
        print("\n✗ Anthropic package not installed. Run: pip install anthropic")
        return False
    except ValueError as e:
        print(f"\n✗ Configuration error: {e}")
        print("   Set ANTHROPIC_API_KEY environment variable")
        return False
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False

    return True


def demo_template():
    """Demo template adapter (no API key needed)."""
    print("\n" + "="*80)
    print("Template Adapter Demo (No API Key Needed)")
    print("="*80 + "\n")

    try:
        # Initialize template adapter
        adapter = TemplateLLMAdapter()
        print("✓ Template adapter initialized")

        # Define research request
        prompt = "Improve scientific research capabilities"

        print(f"\nResearch request: {prompt}")
        print(f"Specialization: {SystemSpecialization.SCIENTIFIC.value}")

        # Generate proposal
        print("\nGenerating proposal with template...")
        result = adapter.generate_improvement(
            prompt=prompt,
            specialization=SystemSpecialization.SCIENTIFIC,
            research_params={},
            guardrails={"max_risk": "medium"}
        )

        # Display results
        print("\n" + "-"*80)
        print("PROPOSAL GENERATED")
        print("-"*80)
        print(f"\nTitle: {result.title}")
        print(f"\nMotivation:\n{result.motivation}")
        print(f"\nExpected Benefits:\n{result.expected_benefits}")
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
        print(f"\nConfidence: {result.confidence}")
        print(f"\nRollback Plan:\n{result.rollback_plan}")

        if result.changes.get("code"):
            print(f"\nProposed Code:")
            print("-"*40)
            print(result.changes["code"])
            print("-"*40)

        print("\n✓ Template demo completed successfully")
        print("\n⚠ Note: Template adapter uses hardcoded responses.")
        print("  For real AI proposals, use --adapter openai or --adapter claude")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Demo LLM adapters for AI Safety System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--adapter",
        choices=["openai", "claude", "template"],
        default="template",
        help="LLM adapter to demo (default: template)"
    )

    args = parser.parse_args()

    print("\n" + "="*80)
    print("AI Safety System - LLM Adapter Demo")
    print("="*80)
    print(f"\nAdapter: {args.adapter}")

    if args.adapter == "openai":
        success = demo_openai()
    elif args.adapter == "claude":
        success = demo_claude()
    else:
        success = demo_template()

    print("\n" + "="*80)
    if success:
        print("Demo completed successfully!")
    else:
        print("Demo failed. Check error messages above.")
    print("="*80 + "\n")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
