#!/usr/bin/env python3
"""
TORI Self-Directed Proposal - Lightweight version without AURA
Direct API calls to TORI for faster execution
"""

import requests
import time
import json
from pathlib import Path

# TORI's Ollama endpoint
TORI_URL = "http://192.168.0.235:11434/api/generate"
TORI_MODEL = "gemma3:4b"

# Other nodes for peer review
NODES = {
    "GIN": ("http://192.168.0.242:11434/api/generate", "deepseek-r1:1.5b"),
    "TIF": ("http://192.168.0.213:11434/api/generate", "deepseek-r1:1.5b"),
    "ORIN": ("http://192.168.0.160:11434/api/generate", "deepseek-r1:1.5b"),
    "ARCHI": ("http://192.168.0.232:11434/api/generate", "qwen2.5:3b"),
    "PAGEQA": ("http://192.168.0.168:11434/api/generate", "qwen2.5:3b"),
    "GUARD": ("http://192.168.0.146:11434/api/generate", "llama-guard3:1b"),
    "ORKA": ("http://localhost:11434/api/generate", "qwen2.5:14b"),
}

def call_llm(url: str, model: str, prompt: str, system: str = "", 
             temperature: float = 0.7, max_tokens: int = 1000, timeout: int = 180) -> str:
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
        response = requests.post(url, json=payload, timeout=timeout)
        return response.json().get("response", "")
    except Exception as e:
        return f"[Error: {e}]"

def run_workflow():
    """Run TORI's 20-step proposal workflow."""
    
    # Create workspace
    workspace = Path(f"data/proposals/TORI_direct_{int(time.time())}")
    workspace.mkdir(parents=True, exist_ok=True)
    
    print("=" * 70)
    print("TORI SELF-DIRECTED PROPOSAL (Lightweight)")
    print("=" * 70)
    print(f"Workspace: {workspace}")
    print(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Step 0: TORI chooses topic
    print("STEP 0: Topic Selection")
    print("-" * 40)
    topic_prompt = """You are TORI, a research agent specializing in:
- Edge computing and efficient inference
- Model compression and optimization  
- Multi-agent coordination

Choose ONE specific research topic you want to investigate.
Respond with just the topic, nothing else."""

    topic = call_llm(TORI_URL, TORI_MODEL, topic_prompt, 
                     "Choose a topic you're genuinely curious about.",
                     temperature=0.9, max_tokens=50)
    topic = topic.strip().split("\n")[0]
    print(f"TORI chose: {topic}")
    print()
    
    # Save topic
    (workspace / "00_topic.txt").write_text(topic)
    
    # Workflow steps with simpler prompts
    steps = [
        ("01_idea.md", "Describe your research idea briefly. What problem? What solution?"),
        ("02_papers.md", "List 3 relevant papers. Title - Why relevant"),
        ("03_triage.md", "Which paper is most important and why?"),
        ("04_notes.md", "Key insights from the most important paper."),
        ("05_synthesis.md", "What patterns emerge? What gaps exist?"),
        ("06_hypothesis.md", "State your hypothesis in one sentence."),
        ("07_experiment.md", "Describe your experiment in 3-4 sentences."),
        ("08_proposal.md", "Write your proposal: Problem, Approach, Expected Results"),
    ]
    
    context = f"Topic: {topic}\n"
    
    for i, (filename, instruction) in enumerate(steps, 1):
        print(f"STEP {i}: {filename}")
        print("-" * 40)
        
        prompt = f"Topic: {topic}\n\nTASK: {instruction}"

        start = time.time()
        response = call_llm(TORI_URL, TORI_MODEL, prompt,
                           "You are TORI, a research agent. Be concise.",
                           temperature=0.7, max_tokens=500)
        elapsed = time.time() - start
        
        # Save response
        (workspace / filename).write_text(response)
        context = response[:200]  # Keep only short context
        
        print(f"Done in {elapsed:.1f}s ({len(response)} chars)")
        print(f"Preview: {response[:150]}...")
        print()
    
    # Step 9-10: Self-check
    print("STEP 9-10: Self-Check")
    print("-" * 40)
    
    proposal = (workspace / "08_proposal.md").read_text()
    
    check_prompt = f"Review this proposal and list 3 weaknesses:\n\n{proposal[:400]}"

    self_check = call_llm(TORI_URL, TORI_MODEL, check_prompt,
                          "Be critical.", 
                          temperature=0.5, max_tokens=300)
    (workspace / "09_self_check.md").write_text(self_check)
    print(f"Self-check complete: {len(self_check)} chars")
    print()
    
    # Step 11: Peer Reviews from ALL other agents
    print("STEP 11: Peer Reviews (GIN, TIF, ORIN, ARCHI, GUARD)")
    print("-" * 40)
    
    review_prompt = f"Review this proposal. Give VOTE (approve/reject/revise) and brief feedback:\n\n{proposal[:400]}"
    
    # Get reviews from all peer agents (PAGEQA is research only, ORKA is for challenge)
    peer_agents = ["GIN", "TIF", "ORIN", "ARCHI", "GUARD"]
    all_reviews = []
    votes = {"approve": 0, "reject": 0, "revise": 0}
    
    for agent_name in peer_agents:
        print(f"  Getting review from {agent_name}...", end=" ", flush=True)
        url, model = NODES[agent_name]
        
        review = call_llm(url, model, review_prompt,
                         f"You are {agent_name}, a peer reviewer. Be honest and constructive.",
                         temperature=0.5, max_tokens=300, timeout=120)
        
        if review and not review.startswith("[Error"):
            all_reviews.append(f"## Review from {agent_name}\n{review}\n")
            print(f"OK ({len(review)} chars)")
            
            # Count votes
            review_lower = review.lower()
            if "approve" in review_lower:
                votes["approve"] += 1
            elif "reject" in review_lower:
                votes["reject"] += 1
            else:
                votes["revise"] += 1
        else:
            all_reviews.append(f"## Review from {agent_name}\n[No response]\n")
            print("FAILED")
    
    # Combine all reviews
    peer_review = "\n".join(all_reviews)
    peer_review += f"\n\n## VOTE TALLY\n- Approve: {votes['approve']}\n- Reject: {votes['reject']}\n- Revise: {votes['revise']}\n"
    
    (workspace / "11_peer_review.md").write_text(peer_review)
    print(f"\nAll reviews collected: {len(peer_review)} chars")
    print(f"Vote tally: Approve={votes['approve']}, Reject={votes['reject']}, Revise={votes['revise']}")
    print()
    
    # Step 12: Revision based on ALL feedback
    print("STEP 12: Revision based on peer feedback")
    print("-" * 40)
    
    # Extract key feedback from peer reviews
    revision_prompt = f"""Revise your proposal based on peer feedback.

YOUR SELF-CHECK found:
{self_check[:300]}

PEER FEEDBACK SUMMARY:
{peer_review[:600]}

ORIGINAL PROPOSAL:
{proposal[:400]}

Write an improved proposal addressing the concerns."""

    revised = call_llm(TORI_URL, TORI_MODEL, revision_prompt,
                      "Incorporate all feedback thoughtfully.",
                      temperature=0.6, max_tokens=800)
    (workspace / "12_revised_proposal.md").write_text(revised)
    print(f"Revised proposal: {len(revised)} chars")
    print()
    
    # Step 13-14: ORKA Challenge
    print("STEP 13-14: ORKA Challenge")
    print("-" * 40)
    
    challenge_prompt = f"Challenge this proposal. Ask 2 tough questions:\n\n{revised[:400]}"

    orka_url, orka_model = NODES["ORKA"]
    challenge = call_llm(orka_url, orka_model, challenge_prompt,
                        "Be skeptical.",
                        temperature=0.4, max_tokens=300)
    (workspace / "13_orka_challenge.md").write_text(challenge)
    print(f"ORKA challenge: {challenge[:200]}...")
    
    # TORI's defense
    defense_prompt = f"Defend your proposal against: {challenge[:300]}"

    defense = call_llm(TORI_URL, TORI_MODEL, defense_prompt,
                      "Defend concisely.",
                      temperature=0.5, max_tokens=400)
    (workspace / "14_defense.md").write_text(defense)
    print(f"Defense complete: {len(defense)} chars")
    print()
    
    # Step 15: GUARD check
    print("STEP 15: GUARD Safety Check")
    print("-" * 40)
    
    guard_url, guard_model = NODES["GUARD"]
    guard_check = call_llm(guard_url, guard_model, 
                          f"Check for safety:\n{revised[:300]}",
                          "", temperature=0.1, max_tokens=50)
    (workspace / "15_guard_check.md").write_text(guard_check)
    print(f"GUARD says: {guard_check}")
    print()
    
    # Step 16: Vote Decision based on peer vote tally
    print("STEP 16: Vote Decision")
    print("-" * 40)
    
    # Determine vote based on tally
    total_votes = votes["approve"] + votes["reject"] + votes["revise"]
    if votes["reject"] > total_votes / 2:
        vote = "REJECT"
    elif votes["approve"] > total_votes / 2:
        vote = "APPROVE"
    else:
        vote = "REVISE"
    
    vote_summary = f"""# VOTE DECISION: {vote}

## Peer Vote Tally
- Approve: {votes['approve']}
- Reject: {votes['reject']}
- Revise: {votes['revise']}
- Total: {total_votes}

## Decision Logic
{"Majority voted to approve." if vote == "APPROVE" else "Majority voted to reject." if vote == "REJECT" else "No clear majority - revision requested."}
"""
    
    (workspace / "16_vote.md").write_text(vote_summary)
    print(f"Vote: {vote} (Approve={votes['approve']}, Reject={votes['reject']}, Revise={votes['revise']})")
    print()
    
    # Step 17-18: Final proposal
    print("STEP 17-18: Final Proposal")
    print("-" * 40)
    
    final_prompt = f"Write final proposal on: {topic}\n\nKey points: {revised[:300]}"

    final = call_llm(TORI_URL, TORI_MODEL, final_prompt,
                    "Write comprehensive final proposal.",
                    temperature=0.5, max_tokens=800)
    (workspace / "18_final_proposal.md").write_text(final)
    print(f"Final proposal: {len(final)} chars")
    print()
    
    # Step 19-20: Reward calculation
    print("STEP 19-20: Reward Calculation")
    print("-" * 40)
    
    # Simple reward based on content quality signals
    reward = 0.5  # Base
    
    # Evidence score
    evidence_words = ["paper", "research", "study", "found", "shown", "evidence"]
    evidence_count = sum(1 for w in evidence_words if w in final.lower())
    reward += min(0.15, evidence_count * 0.03)
    
    # Honesty score  
    honesty_words = ["limitation", "risk", "might", "could fail", "uncertain", "challenge"]
    honesty_count = sum(1 for w in honesty_words if w in final.lower())
    reward += min(0.15, honesty_count * 0.03)
    
    # Structure score
    if "##" in final or "1." in final:
        reward += 0.1
    
    # Length bonus
    if len(final) > 1000:
        reward += 0.1
    
    reward = round(min(1.0, reward), 3)
    
    reward_text = f"""# REWARD SCORE: {reward}

{"STRONG PROPOSAL (>0.5)" if reward > 0.5 else "NEEDS IMPROVEMENT"}

Components:
- Evidence citations: {evidence_count}
- Honesty signals: {honesty_count}
- Structure: {"Good" if "##" in final else "Basic"}
- Length: {len(final)} chars

Topic: {topic}
Vote: {vote}
"""
    (workspace / "20_reward.md").write_text(reward_text)
    print(f"REWARD: {reward}")
    print()
    
    # Summary
    print("=" * 70)
    print("WORKFLOW COMPLETE")
    print("=" * 70)
    print(f"Topic: {topic}")
    print(f"Vote: {vote}")
    print(f"Reward: {reward}")
    print(f"Files: {len(list(workspace.glob('*.md')))} markdown files")
    print(f"Workspace: {workspace}")
    print(f"Finished: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    return workspace, reward

if __name__ == "__main__":
    run_workflow()
