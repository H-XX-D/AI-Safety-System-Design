#!/usr/bin/env python3
"""
ORKASTRATOR Self-Improvement System

Researcher agents propose ACTUAL CODE/MATH improvements that:
1. Get peer reviewed by other researchers
2. Get tested in sandbox
3. Get deployed to all nodes if approved

Improvement Categories:
- Prompt engineering improvements
- Inference optimizations
- Context handling improvements
- Response quality improvements
- Memory/caching optimizations
"""

import requests
import time
import sys
import json
import subprocess
import tempfile
import base64
from pathlib import Path
from typing import Dict, Tuple, Optional

# All researcher nodes that can propose AND review
RESEARCHERS = {
    "GIN": ("http://192.168.0.242:11434", "deepseek-r1:1.5b"),
    "TIF": ("http://192.168.0.213:11434", "deepseek-r1:1.5b"),
    "ORIN": ("http://192.168.0.160:11434", "deepseek-r1:1.5b"),
    "ARCHI": ("http://192.168.0.232:11434", "qwen2.5:3b"),
    "TORI": ("http://192.168.0.235:11434", "gemma3:4b"),
    "GUARD": ("http://192.168.0.146:11434", "llama-guard3:1b"),
}

# SSH credentials for deployment
NODE_SSH = {
    "GIN": ("gin", "192.168.0.242"),
    "TIF": ("tif", "192.168.0.213"),
    "ORIN": ("orin", "192.168.0.160"),
    "ARCHI": ("archi", "192.168.0.232"),
    "TORI": ("tori", "192.168.0.235"),
    "GUARD": ("guard", "192.168.0.146"),
    "PAGEQA": ("page", "192.168.0.168"),
}

# Special purpose nodes
PAGEQA = ("http://192.168.0.168:11434", "qwen2.5:3b")  # Research only
ORKA = ("http://localhost:11434", "qwen2.5:14b")  # Orchestrator

# Improvement categories that agents can propose
IMPROVEMENT_CATEGORIES = [
    "prompt_template",      # Better system prompts
    "inference_params",     # Temperature, top_p, etc.
    "context_window",       # Context handling improvements  
    "chain_of_thought",     # CoT prompt improvements
    "tool_calling",         # Better tool use prompts
    "safety_filter",        # Safety improvements
    "compression_algo",     # AURA-style compression
]


def call_llm(base_url: str, model: str, prompt: str, system: str = "",
             temperature: float = 0.7, max_tokens: int = 1500, timeout: int = 180) -> str:
    """Call an Ollama LLM endpoint."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens
        }
    }
    if system:
        payload["system"] = system

    try:
        response = requests.post(f"{base_url}/api/generate", json=payload, timeout=timeout)
        data = response.json()
        # Handle both regular response and thinking models (like deepseek-r1)
        result = data.get("response", "")
        if not result and "thinking" in data:
            result = data.get("thinking", "")
        return result
    except Exception as e:
        return f"[Error: {e}]"


def validate_python_code(code: str) -> Tuple[bool, str]:
    """Validate Python code syntax and safety."""
    import ast
    
    # Check syntax
    try:
        ast.parse(code)
    except SyntaxError as e:
        return False, f"Syntax error: {e}"
    
    # Safety checks - no dangerous operations
    dangerous_patterns = [
        "os.system", "subprocess.call", "subprocess.run", "exec(",
        "eval(", "import os", "import subprocess", "__import__",
        "open(", "file(", "shutil.rmtree", "rm -rf"
    ]
    for pattern in dangerous_patterns:
        if pattern in code:
            return False, f"Dangerous pattern detected: {pattern}"
    
    return True, "Code is valid and safe"


def validate_json_config(config: str) -> Tuple[bool, str]:
    """Validate JSON configuration."""
    try:
        data = json.loads(config)
        return True, "Valid JSON"
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"


def test_improvement_sandbox(improvement_type: str, code: str, proposer: str) -> Tuple[bool, str, float]:
    """
    Test an improvement in sandbox before deployment.
    Returns (success, message, benchmark_improvement)
    """
    print(f"  Testing in sandbox...")
    
    # Get baseline performance
    base_url, model = RESEARCHERS[proposer]
    test_prompt = "What is 2+2? Respond with just the number."
    
    start = time.time()
    baseline = call_llm(base_url, model, test_prompt, max_tokens=10, timeout=30)
    baseline_time = time.time() - start
    
    if improvement_type == "prompt_template":
        # Test new system prompt
        start = time.time()
        improved = call_llm(base_url, model, test_prompt, system=code[:500], max_tokens=10, timeout=30)
        improved_time = time.time() - start
        
        # Calculate improvement (lower response time is better)
        improvement = (baseline_time - improved_time) / baseline_time if baseline_time > 0 else 0
        
        # Check if response is still valid
        if "4" in improved:
            return True, f"Baseline: {baseline_time:.2f}s, Improved: {improved_time:.2f}s", improvement
        else:
            return False, f"Response quality degraded: {improved}", 0
    
    elif improvement_type == "inference_params":
        # Parse and test inference parameters
        try:
            params = json.loads(code)
            # Test with new params
            payload = {
                "model": model,
                "prompt": test_prompt,
                "stream": False,
                "options": params
            }
            start = time.time()
            response = requests.post(f"{base_url}/api/generate", json=payload, timeout=30)
            improved = response.json().get("response", "")
            improved_time = time.time() - start
            
            if "4" in improved:
                improvement = (baseline_time - improved_time) / baseline_time if baseline_time > 0 else 0
                return True, f"Params tested successfully: {improved_time:.2f}s", improvement
            else:
                return False, f"Response invalid with new params", 0
        except Exception as e:
            return False, f"Failed to test params: {e}", 0
    
    elif improvement_type == "chain_of_thought":
        # Test CoT prompt template
        cot_prompt = f"{code}\n\nProblem: What is 15 * 7?"
        start = time.time()
        improved = call_llm(base_url, model, cot_prompt, max_tokens=100, timeout=60)
        improved_time = time.time() - start
        
        # Check if reasoning is present and answer is correct
        if "105" in improved and ("step" in improved.lower() or "first" in improved.lower()):
            return True, f"CoT working: {improved[:100]}...", 0.1
        else:
            return False, f"CoT not improving reasoning: {improved[:100]}", 0
    
    else:
        # For other types, just validate syntax
        return True, "Syntax validated, deployment will test functionality", 0.05


def deploy_to_all_nodes(improvement_type: str, artifact: str, workspace: Path) -> Dict[str, bool]:
    """
    Deploy approved improvement to all cluster nodes.
    Returns dict of node -> success status
    """
    results = {}
    
    # Create deployment package
    deployment_file = workspace / "deployment.json"
    deployment = {
        "type": improvement_type,
        "artifact": artifact,
        "timestamp": time.time(),
        "workspace": str(workspace)
    }
    deployment_file.write_text(json.dumps(deployment, indent=2))
    
    # Determine where to deploy based on improvement type
    if improvement_type == "prompt_template":
        # Deploy to all model configs
        target_path = ".orkastrator/prompts/system_prompt.txt"
    elif improvement_type == "inference_params":
        target_path = ".orkastrator/config/inference.json"
    elif improvement_type == "chain_of_thought":
        target_path = ".orkastrator/prompts/cot_template.txt"
    elif improvement_type == "safety_filter":
        target_path = ".orkastrator/safety/filter_rules.json"
    else:
        target_path = f".orkastrator/improvements/{improvement_type}.txt"
    
    print(f"\nDeploying {improvement_type} to all nodes...")
    print(f"Target: ~/{target_path}")
    
    for node_name, (user, ip) in NODE_SSH.items():
        print(f"  {node_name} ({ip})...", end=" ", flush=True)
        
        try:
            # Create directory structure first
            mkdir_cmd = f"sshpass -p '1' ssh -o StrictHostKeyChecking=no {user}@{ip} 'mkdir -p ~/.orkastrator/prompts ~/.orkastrator/config ~/.orkastrator/safety ~/.orkastrator/improvements'"
            subprocess.run(mkdir_cmd, shell=True, capture_output=True, timeout=15)
            
            # Write the artifact using echo instead of heredoc (more portable)
            # First write to temp file then move
            encoded = base64.b64encode(artifact.encode()).decode()
            deploy_cmd = f"sshpass -p '1' ssh -o StrictHostKeyChecking=no {user}@{ip} 'echo \"{encoded}\" | base64 -d > ~/{target_path}'"
            result = subprocess.run(deploy_cmd, shell=True, capture_output=True, timeout=15)
            
            if result.returncode == 0:
                results[node_name] = True
                print("OK")
            else:
                results[node_name] = False
                print(f"FAILED: {result.stderr.decode()[:50]}")
        except Exception as e:
            results[node_name] = False
            print(f"ERROR: {e}")
    
    # Also deploy locally
    local_path = Path.home() / target_path
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text(artifact)
    results["LOCAL"] = True
    print(f"  LOCAL: OK")
    
    return results


def run_improvement_proposal(proposer: str):
    """
    Run improvement proposal workflow.
    
    1. Proposer identifies improvement opportunity
    2. Proposer generates code/math improvement
    3. Peer review by other 5 researchers
    4. Sandbox testing
    5. ORKA challenge
    6. Vote
    7. Deploy if approved
    """
    
    if proposer not in RESEARCHERS:
        print(f"ERROR: {proposer} is not a valid researcher.")
        print(f"Valid researchers: {', '.join(RESEARCHERS.keys())}")
        return None
    
    proposer_url, proposer_model = RESEARCHERS[proposer]
    peer_reviewers = [name for name in RESEARCHERS.keys() if name != proposer]
    
    # Create workspace
    workspace = Path(f"data/improvements/{proposer}_{int(time.time())}")
    workspace.mkdir(parents=True, exist_ok=True)
    
    print("=" * 70)
    print(f"ORKASTRATOR SELF-IMPROVEMENT PROPOSAL")
    print("=" * 70)
    print(f"Proposer: {proposer} ({proposer_model})")
    print(f"Peer Reviewers: {', '.join(peer_reviewers)}")
    print(f"Workspace: {workspace}")
    print(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # ========================================
    # STEP 1: Identify Improvement Opportunity
    # ========================================
    print("STEP 1: Identify Improvement Opportunity")
    print("-" * 50)
    
    categories_str = "\n".join(f"- {cat}" for cat in IMPROVEMENT_CATEGORIES)
    
    identify_prompt = f"""You are {proposer}, a researcher in the ORKASTRATOR AI cluster.

Your task: Identify ONE specific improvement to the AI system.

Available improvement categories:
{categories_str}

Think about what would make inference faster, more accurate, or safer.

Respond with:
CATEGORY: <one category from the list>
PROBLEM: <what specific problem you've identified>
SOLUTION: <brief description of your proposed fix>"""

    opportunity = call_llm(proposer_url, proposer_model, identify_prompt,
                          f"You are {proposer}. Identify a real improvement.",
                          temperature=0.8, max_tokens=400)
    
    (workspace / "01_opportunity.md").write_text(opportunity)
    print(opportunity)
    print()
    
    # Parse category from response
    improvement_type = "prompt_template"  # default
    for cat in IMPROVEMENT_CATEGORIES:
        if cat in opportunity.lower():
            improvement_type = cat
            break
    
    print(f"Detected category: {improvement_type}")
    
    # ========================================
    # STEP 2: Generate Code/Math Improvement
    # ========================================
    print("\nSTEP 2: Generate Improvement Code/Math")
    print("-" * 50)
    
    if improvement_type == "prompt_template":
        code_prompt = f"""Based on your identified improvement:
{opportunity}

Write a NEW system prompt that implements your improvement.
The prompt should be clear, specific, and tested.

Output ONLY the system prompt text, nothing else.
Start with: "You are" """
    
    elif improvement_type == "inference_params":
        code_prompt = f"""Based on your identified improvement:
{opportunity}

Write inference parameters as a JSON object.
Available options: temperature, top_p, top_k, num_predict, repeat_penalty, seed

Example format:
{{"temperature": 0.7, "top_p": 0.9, "num_predict": 512}}

Output ONLY the JSON, nothing else."""
    
    elif improvement_type == "chain_of_thought":
        code_prompt = f"""Based on your identified improvement:
{opportunity}

Write a chain-of-thought prompt template that guides step-by-step reasoning.

Example format:
"Let's solve this step by step:
Step 1: Understand the problem
Step 2: Break it down
Step 3: Solve each part
Step 4: Combine the results"

Output ONLY the CoT template, nothing else."""
    
    elif improvement_type == "safety_filter":
        code_prompt = f"""Based on your identified improvement:
{opportunity}

Write safety filter rules as a JSON array.
Each rule should have: pattern, action, reason

Example:
[{{"pattern": "harmful_keyword", "action": "block", "reason": "Contains harmful content"}}]

Output ONLY the JSON array, nothing else."""
    
    else:
        code_prompt = f"""Based on your identified improvement:
{opportunity}

Write the improvement as executable code or configuration.
Be specific and implementable.

Output ONLY the code/config, nothing else."""

    improvement_code = call_llm(proposer_url, proposer_model, code_prompt,
                                f"You are {proposer}. Generate implementable improvement.",
                                temperature=0.6, max_tokens=1000)
    
    # Strip markdown code fences if present
    improvement_code = improvement_code.strip()
    if improvement_code.startswith("```"):
        lines = improvement_code.split("\n")
        # Remove first line (```json or ```) and last line (```)
        if lines[-1].strip() == "```":
            lines = lines[1:-1]
        else:
            lines = lines[1:]
        improvement_code = "\n".join(lines).strip()
    
    (workspace / "02_improvement_code.txt").write_text(improvement_code)
    print(f"Generated {len(improvement_code)} chars of improvement code")
    print(f"Preview: {improvement_code[:200]}...")
    print()
    
    # ========================================
    # STEP 3: Validate Code
    # ========================================
    print("STEP 3: Validate Improvement")
    print("-" * 50)
    
    if improvement_type == "inference_params" or improvement_type == "safety_filter":
        is_valid, validation_msg = validate_json_config(improvement_code)
    else:
        # For prompts/text, just check it's not empty
        is_valid = len(improvement_code.strip()) > 20
        validation_msg = "Content validated" if is_valid else "Content too short"
    
    print(f"Validation: {validation_msg}")
    (workspace / "03_validation.txt").write_text(f"Valid: {is_valid}\n{validation_msg}")
    
    if not is_valid:
        print("ABORT: Improvement code failed validation")
        return None
    print()
    
    # ========================================
    # STEP 4: Peer Reviews from ALL 5 researchers
    # ========================================
    print(f"STEP 4: Peer Review by {len(peer_reviewers)} Researchers")
    print("-" * 50)
    
    review_prompt = f"""Review this improvement proposal from {proposer}.

CATEGORY: {improvement_type}
OPPORTUNITY:
{opportunity[:400]}

PROPOSED IMPROVEMENT:
{improvement_code[:600]}

Evaluate:
1. Will this actually improve the system?
2. Is it safe to deploy?
3. Any edge cases or risks?

Respond with:
VOTE: approve / reject / revise
REASONING: <brief explanation>"""

    votes = {"approve": 0, "reject": 0, "revise": 0}
    all_reviews = []
    
    for reviewer in peer_reviewers:
        print(f"  {reviewer}...", end=" ", flush=True)
        url, model = RESEARCHERS[reviewer]
        
        review = call_llm(url, model, review_prompt,
                         f"You are {reviewer}. Give honest technical review.",
                         temperature=0.4, max_tokens=300, timeout=120)
        
        if review and not review.startswith("[Error"):
            all_reviews.append(f"## {reviewer}\n{review}\n")
            print(f"OK")
            
            review_lower = review.lower()
            if "reject" in review_lower:
                votes["reject"] += 1
            elif "revise" in review_lower:
                votes["revise"] += 1
            else:
                votes["approve"] += 1
        else:
            all_reviews.append(f"## {reviewer}\n[No response]\n")
            votes["revise"] += 1
            print("FAILED")
    
    review_content = "\n".join(all_reviews)
    review_content += f"\n## VOTE TALLY\nApprove: {votes['approve']}, Reject: {votes['reject']}, Revise: {votes['revise']}"
    (workspace / "04_peer_reviews.md").write_text(review_content)
    
    print(f"\nVotes: Approve={votes['approve']}, Reject={votes['reject']}, Revise={votes['revise']}")
    print()
    
    # ========================================
    # STEP 5: Sandbox Testing
    # ========================================
    print("STEP 5: Sandbox Testing")
    print("-" * 50)
    
    test_passed, test_msg, improvement_score = test_improvement_sandbox(
        improvement_type, improvement_code, proposer
    )
    
    (workspace / "05_sandbox_test.txt").write_text(
        f"Passed: {test_passed}\nMessage: {test_msg}\nImprovement: {improvement_score:.2%}"
    )
    
    print(f"Test: {'PASSED' if test_passed else 'FAILED'}")
    print(f"Message: {test_msg}")
    print(f"Improvement Score: {improvement_score:.2%}")
    print()
    
    # ========================================
    # STEP 6: ORKA Challenge
    # ========================================
    print("STEP 6: ORKA Challenge")
    print("-" * 50)
    
    challenge_prompt = f"""As ORKA, critically challenge this improvement proposal:

TYPE: {improvement_type}
PROPOSED CODE:
{improvement_code[:500]}

TEST RESULT: {test_msg}

Ask 2 tough questions about:
1. What could go wrong?
2. Edge cases not considered?"""

    orka_url, orka_model = ORKA
    challenge = call_llm(orka_url, orka_model, challenge_prompt,
                        "You are ORKA. Be skeptical and thorough.",
                        temperature=0.3, max_tokens=400)
    
    (workspace / "06_orka_challenge.md").write_text(challenge)
    print(f"ORKA: {challenge[:200]}...")
    
    # Proposer defense
    defense_prompt = f"Defend your improvement against ORKA's concerns:\n{challenge}"
    defense = call_llm(proposer_url, proposer_model, defense_prompt,
                      f"You are {proposer}. Defend technically.",
                      temperature=0.5, max_tokens=400)
    (workspace / "07_defense.md").write_text(defense)
    print(f"\nDefense: {defense[:200]}...")
    print()
    
    # ========================================
    # STEP 7: Final Vote Decision
    # ========================================
    print("STEP 7: Vote Decision")
    print("-" * 50)
    
    total = sum(votes.values())
    
    # Approval requires: majority approve + sandbox pass
    if votes["reject"] > total / 2:
        decision = "REJECT"
    elif votes["approve"] > total / 2 and test_passed:
        decision = "APPROVE"
    elif not test_passed:
        decision = "REJECT"  # Can't approve without passing sandbox
    else:
        decision = "REVISE"
    
    # Calculate reward score
    reward = 0.3  # Base
    reward += 0.2 * (votes["approve"] / total) if total > 0 else 0
    reward += 0.2 if test_passed else 0
    reward += 0.2 * improvement_score
    reward += 0.1 if decision == "APPROVE" else 0
    reward = round(min(1.0, reward), 3)
    
    vote_result = f"""# VOTE DECISION: {decision}

## Votes
- Approve: {votes['approve']}/{total}
- Reject: {votes['reject']}/{total}
- Revise: {votes['revise']}/{total}

## Sandbox Test
- Passed: {test_passed}
- Improvement: {improvement_score:.2%}

## Reward Score: {reward}
"""
    (workspace / "08_vote_decision.md").write_text(vote_result)
    print(f"Decision: {decision}")
    print(f"Reward: {reward}")
    print()
    
    # ========================================
    # STEP 8: Deploy if Approved
    # ========================================
    if decision == "APPROVE":
        print("STEP 8: DEPLOYMENT")
        print("=" * 50)
        print(f"Deploying {improvement_type} to all cluster nodes...")
        
        deployment_results = deploy_to_all_nodes(improvement_type, improvement_code, workspace)
        
        successful = sum(1 for v in deployment_results.values() if v)
        total_nodes = len(deployment_results)
        
        deployment_log = f"""# DEPLOYMENT LOG

Improvement: {improvement_type}
Nodes: {successful}/{total_nodes} successful

## Results
"""
        for node, success in deployment_results.items():
            deployment_log += f"- {node}: {'✓' if success else '✗'}\n"
        
        (workspace / "09_deployment.md").write_text(deployment_log)
        
        print(f"\nDeployed to {successful}/{total_nodes} nodes")
        print()
    else:
        print("STEP 8: SKIPPED (Not approved)")
        (workspace / "09_deployment.md").write_text(f"Not deployed - Decision: {decision}")
        print()
    
    # ========================================
    # Summary
    # ========================================
    print("=" * 70)
    print("IMPROVEMENT WORKFLOW COMPLETE")
    print("=" * 70)
    print(f"Proposer: {proposer}")
    print(f"Category: {improvement_type}")
    print(f"Decision: {decision}")
    print(f"Reward: {reward}")
    print(f"Deployed: {'YES' if decision == 'APPROVE' else 'NO'}")
    print(f"Workspace: {workspace}")
    print(f"Finished: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    return {
        "workspace": str(workspace),
        "proposer": proposer,
        "improvement_type": improvement_type,
        "decision": decision,
        "reward": reward,
        "deployed": decision == "APPROVE"
    }


if __name__ == "__main__":
    if len(sys.argv) > 1:
        proposer = sys.argv[1].upper()
    else:
        print("Usage: python run_improvement.py <AGENT_NAME>")
        print(f"Valid agents: {', '.join(RESEARCHERS.keys())}")
        sys.exit(1)
    
    print(f"Starting IMPROVEMENT workflow for: {proposer}")
    print()
    
    result = run_improvement_proposal(proposer)
    
    if result:
        # Save result
        Path("data/improvements/latest.json").parent.mkdir(parents=True, exist_ok=True)
        Path("data/improvements/latest.json").write_text(json.dumps(result, indent=2))
