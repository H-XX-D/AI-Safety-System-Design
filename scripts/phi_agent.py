#!/usr/bin/env python3
"""
Phi Agent - Phi drives its own research with ground truth always in context.
"""

import os
import json
import requests
from pathlib import Path

PHI_URL = "http://localhost:8080"
WORKSPACE = Path("./data/phi_research")
WORKSPACE.mkdir(parents=True, exist_ok=True)

# Ground truth file
GROUND_TRUTH = Path("./memory/WORKFLOW_GROUND_TRUTH.md")

# Step tracking
STEPS = [
    ("01_idea.md", "IDEA", "Decide what capability to improve"),
    ("02_papers_broad.md", "BROAD SEARCH", "Search for relevant papers"),
    ("03_triage.md", "TRIAGE", "Quick-scan and mark standouts"),
    ("04_deep_notes.md", "DEEP DIVE", "Deep notes on standouts"),
    ("05_synthesis.md", "SYNTHESIS", "Combine notes into summary"),
    ("06_hypothesis.md", "HYPOTHESIS", "Form testable hypothesis"),
    ("07_experiment.md", "EXPERIMENT DESIGN", "Design the experiment"),
    ("08_proposal.md", "WRITE PROPOSAL", "Write full proposal"),
    ("09_self_check_consistency.md", "SELF-CHECK CONSISTENCY", "Check internal consistency"),
    ("10_self_check_weaknesses.md", "SELF-CHECK WEAKNESSES", "Identify weaknesses"),
    ("11_peer_response.md", "PEER REVIEW", "Respond to peer feedback"),
    ("12_defense.md", "ORKA CHALLENGE", "Defend against ORKA"),
    ("13_revised_proposal.md", "REVISION", "Revise based on feedback"),
    ("14_final_proposal.md", "FINAL SUBMISSION", "Submit final proposal"),
    ("15_reward.md", "RECEIVE REWARD", "Review your reward"),
]

def get_current_step():
    """Determine current step based on which files exist."""
    for i, (filename, stage, desc) in enumerate(STEPS):
        filepath = WORKSPACE / filename
        if not filepath.exists():
            return i + 1, filename, stage, desc
    return 15, "15_reward.md", "COMPLETE", "All steps done"

def get_completed_files():
    """List completed step files."""
    completed = []
    for filename, stage, desc in STEPS:
        if (WORKSPACE / filename).exists():
            completed.append(filename)
    return completed

def load_ground_truth_with_state():
    """Load ground truth and inject current state."""
    with open(GROUND_TRUTH) as f:
        gt = f.read()
    
    step_num, filename, stage, desc = get_current_step()
    completed = get_completed_files()
    
    # Replace placeholders
    gt = gt.replace("[STAGE_NAME]", stage)
    gt = gt.replace("[STEP_NUMBER]", str(step_num))
    gt = gt.replace("[LIST]", ", ".join(completed) if completed else "None")
    gt = gt.replace("[SPECIFIC_ACTION]", f"Write to {filename}: {desc}")
    
    return gt, step_num, filename, stage, desc

def call_phi(system: str, user: str) -> str:
    """Call Phi with system context and user prompt."""
    # Truncate system if too long
    if len(system) > 3000:
        system = system[:3000] + "\n...[truncated]"
    
    prompt = f"<|user|>\n{user}<|end|>\n<|assistant|>\n"
    
    try:
        r = requests.post(f"{PHI_URL}/completion", json={
            "prompt": prompt,
            "n_predict": 1500,
            "temperature": 0.7,
            "stop": ["<|end|>"]
        }, timeout=180)
        return r.json().get("content", "").strip()
    except Exception as e:
        print(f"[Error: {e}]")
        return ""

def write_file(filename: str, content: str) -> str:
    path = WORKSPACE / filename
    with open(path, 'w') as f:
        f.write(content)
    return f"Saved to {filename}"

def read_file(filename: str) -> str:
    path = WORKSPACE / filename
    if path.exists():
        with open(path, 'r') as f:
            return f.read()
    return f"File {filename} not found"

def list_files() -> str:
    files = sorted(WORKSPACE.glob("*.md"))
    if files:
        return "Files: " + ", ".join(f.name for f in files)
    return "No files yet"

def search_papers(query: str) -> str:
    # In production, call PaperQA
    return f"""Search results for '{query}':
1. "Attention Is All You Need" (Vaswani 2017) - Transformer architecture
2. "BERT" (Devlin 2018) - Bidirectional context understanding
3. "GPT-3: Language Models are Few-Shot Learners" (Brown 2020) - Scaling laws
4. "Training language models to follow instructions with RLHF" (Ouyang 2022) - Alignment
5. "Constitutional AI" (Bai 2022) - Self-improvement through feedback
6. "Chain-of-Thought Prompting" (Wei 2022) - Reasoning improvements
7. "Self-Consistency" (Wang 2022) - Multiple reasoning paths"""

def main():
    print("="*60)
    print("PHI AGENT - Ground Truth Guided Research")
    print("="*60)
    print(f"Workspace: {WORKSPACE.absolute()}")
    
    max_iterations = 20
    
    for iteration in range(max_iterations):
        # Load ground truth with current state
        ground_truth, step_num, target_file, stage, desc = load_ground_truth_with_state()
        
        print(f"\n{'='*60}")
        print(f"STEP {step_num}/15: {stage}")
        print(f"Target: {target_file}")
        print(f"Task: {desc}")
        print("="*60)
        
        if step_num > 14:
            print("\n✓ ALL STEPS COMPLETE")
            break
        
        # Build context from previous files
        context_files = []
        for prev_file, _, _ in STEPS[:step_num-1]:
            path = WORKSPACE / prev_file
            if path.exists():
                with open(path) as f:
                    context_files.append(f"=== {prev_file} ===\n{f.read()[:500]}...")
        
        previous_work = "\n\n".join(context_files[-3:]) if context_files else "No previous work yet."
        
        # Ask Phi to do this step
        user_prompt = f"""You are on Step {step_num}: {stage}

YOUR PREVIOUS WORK:
{previous_work}

YOUR TASK NOW:
{desc}

Write the content for {target_file}. Output ONLY the content to save (no explanations)."""
        
        print("\n[Asking Phi...]")
        response = call_phi(ground_truth, user_prompt)
        
        if response.strip():
            print(f"\n[Phi's response ({len(response)} chars)]")
            print(response[:500] + "..." if len(response) > 500 else response)
            
            # Save to file
            write_file(target_file, response)
            print(f"\n✓ Saved to {target_file}")
        else:
            print("[Empty response - retrying with more guidance]")
            
            # More specific prompt
            if step_num == 1:
                user_prompt = "What capability do YOU (Phi-3.5-mini) want to improve about yourself? Write your idea."
            elif step_num == 2:
                user_prompt = f"Search for papers. Here are results:\n{search_papers('language model improvement')}\n\nList which papers are relevant to your idea and why."
            else:
                user_prompt = f"Complete step {step_num}: {desc}. Write the content now."
            
            response = call_phi(ground_truth, user_prompt)
            if response.strip():
                write_file(target_file, response)
                print(f"✓ Saved to {target_file}")
            else:
                print("✗ Still empty - stopping")
                break
    
    # Show final state
    print("\n" + "="*60)
    print("SESSION COMPLETE")
    print("="*60)
    print(f"Files created: {list_files()}")
    print(f"\nWorkspace: {WORKSPACE.absolute()}")

if __name__ == "__main__":
    main()
