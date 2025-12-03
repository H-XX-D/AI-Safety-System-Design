#!/usr/bin/env python3
"""
Minimal runner - Phi does genuine research using ResearchWorkflow.
No simulation. Real API calls. Phi drives everything.
"""

import sys
import os
from pathlib import Path

# Direct import to avoid __init__.py loading everything
sys.path.insert(0, str(Path(__file__).parent.parent / "memory"))
import importlib.util
spec = importlib.util.spec_from_file_location("research_workflow", 
    Path(__file__).parent.parent / "memory" / "research_workflow.py")
rw_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rw_module)
ResearchWorkflow = rw_module.ResearchWorkflow

import requests
import json

PHI_URL = "http://localhost:8080"

def ask_phi(prompt: str) -> str:
    """Send prompt to Phi, get response."""
    r = requests.post(f"{PHI_URL}/completion", json={
        "prompt": f"<|user|>\n{prompt}<|end|>\n<|assistant|>\n",
        "n_predict": 1500,
        "temperature": 0.7,
        "stop": ["<|end|>"]
    }, timeout=120)
    return r.json().get("content", "").strip()

def main():
    # Create workflow
    workflow = ResearchWorkflow("phi_self_improvement")
    
    # Ask Phi what capability it wants to improve
    print("\n[Asking Phi what capability it wants to research...]\n")
    
    response = ask_phi("""You are a small language model (Phi-3.5-mini) that can propose improvements to yourself.

What capability would you most like to improve about yourself? 

Think about:
- What tasks do you struggle with?
- What would make you more useful?
- What's realistic to improve?

Respond with:
1. The capability you want to improve
2. Why you chose this
3. Your initial hypothesis about how to improve it""")
    
    print(response)
    print("\n" + "="*60)
    
    # Save Phi's choice
    workflow.start_research(
        title="Phi Self-Improvement Research",
        initial_question=response[:500],
        initial_hypothesis=""
    )
    
    # Let Phi continue - it now has access to the workflow files
    print(f"\nWorkflow initialized at: {workflow.project_dir}")
    print("Phi can now use the research workflow to investigate this.")

if __name__ == "__main__":
    main()

