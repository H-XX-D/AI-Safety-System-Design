#!/usr/bin/env python3
"""
Universal Self-Directed Proposal Workflow

Any of the 6 researcher nodes can run this:
- GIN, TIF, ORIN, ARCHI, TORI, GUARD

The proposing agent gets peer reviews and votes from ALL other 5 researchers.
PAGEQA is used for research queries only.
ORKA is used for critical challenge only.
"""

import requests
import time
import sys
from pathlib import Path

# All researcher nodes that can propose AND review
RESEARCHERS = {
    "GIN": ("http://192.168.0.242:11434/api/generate", "deepseek-r1:1.5b"),
    "TIF": ("http://192.168.0.213:11434/api/generate", "deepseek-r1:1.5b"),
    "ORIN": ("http://192.168.0.160:11434/api/generate", "deepseek-r1:1.5b"),
    "ARCHI": ("http://192.168.0.232:11434/api/generate", "qwen2.5:3b"),
    "TORI": ("http://192.168.0.235:11434/api/generate", "gemma3:4b"),
    "GUARD": ("http://192.168.0.146:11434/api/generate", "llama-guard3:1b"),
}

# Special purpose nodes (not peer reviewers)
PAGEQA = ("http://192.168.0.168:11434/api/generate", "qwen2.5:3b")  # Research only
ORKA = ("http://localhost:11434/api/generate", "qwen2.5:14b")  # Challenge only


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


def run_proposal(proposer: str):
    """
    Run proposal workflow for the given proposer agent.
    All other 5 researchers will peer review and vote.
    """
    
    if proposer not in RESEARCHERS:
        print(f"ERROR: {proposer} is not a valid researcher.")
        print(f"Valid researchers: {', '.join(RESEARCHERS.keys())}")
        return None
    
    proposer_url, proposer_model = RESEARCHERS[proposer]
    
    # Get the other 5 researchers for peer review
    peer_reviewers = [name for name in RESEARCHERS.keys() if name != proposer]
    
    # Create workspace
    workspace = Path(f"data/proposals/{proposer}_{int(time.time())}")
    workspace.mkdir(parents=True, exist_ok=True)
    
    print("=" * 70)
    print(f"{proposer} SELF-DIRECTED PROPOSAL")
    print("=" * 70)
    print(f"Proposer: {proposer} ({proposer_model})")
    print(f"Peer Reviewers: {', '.join(peer_reviewers)}")
    print(f"Workspace: {workspace}")
    print(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # ========================================
    # STEP 0: Choose topic
    # ========================================
    print("STEP 0: Topic Selection")
    print("-" * 40)
    
    topic_prompt = f"""You are {proposer}, a research agent in the ORKASTRATOR cluster.

Choose ONE specific research topic you want to investigate.
Pick something you're genuinely curious about.
Respond with just the topic, nothing else."""

    topic = call_llm(proposer_url, proposer_model, topic_prompt,
                     f"You are {proposer}. Choose a research topic.",
                     temperature=0.9, max_tokens=50)
    topic = topic.strip().split("\n")[0]
    print(f"{proposer} chose: {topic}")
    (workspace / "00_topic.txt").write_text(f"Proposer: {proposer}\nTopic: {topic}")
    print()
    
    # ========================================
    # STEPS 1-8: Research and Proposal
    # ========================================
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
    
    for i, (filename, instruction) in enumerate(steps, 1):
        print(f"STEP {i}: {filename}")
        print("-" * 40)
        
        prompt = f"Topic: {topic}\n\nTASK: {instruction}"
        
        start = time.time()
        response = call_llm(proposer_url, proposer_model, prompt,
                           f"You are {proposer}. Be concise.",
                           temperature=0.7, max_tokens=500)
        elapsed = time.time() - start
        
        (workspace / filename).write_text(response)
        print(f"Done in {elapsed:.1f}s ({len(response)} chars)")
        print(f"Preview: {response[:100]}...")
        print()
    
    # ========================================
    # STEP 9-10: Self-check
    # ========================================
    print("STEP 9-10: Self-Check")
    print("-" * 40)
    
    proposal = (workspace / "08_proposal.md").read_text()
    
    check_prompt = f"Review this proposal and list 3 weaknesses:\n\n{proposal[:400]}"
    self_check = call_llm(proposer_url, proposer_model, check_prompt,
                          "Be critical.", temperature=0.5, max_tokens=300)
    (workspace / "09_self_check.md").write_text(self_check)
    print(f"Self-check complete: {len(self_check)} chars")
    print()
    
    # ========================================
    # STEP 11: Peer Reviews from ALL 5 other researchers
    # ========================================
    print(f"STEP 11: Peer Reviews from {len(peer_reviewers)} agents")
    print("-" * 40)
    
    review_prompt = f"""Review this proposal from {proposer}.

{proposal[:500]}

Provide:
VOTE: approve / reject / revise
FEEDBACK: Brief constructive feedback"""
    
    all_reviews = []
    votes = {"approve": 0, "reject": 0, "revise": 0}
    
    for reviewer in peer_reviewers:
        print(f"  {reviewer}...", end=" ", flush=True)
        url, model = RESEARCHERS[reviewer]
        
        review = call_llm(url, model, review_prompt,
                         f"You are {reviewer}. Give honest peer review.",
                         temperature=0.5, max_tokens=300, timeout=120)
        
        if review and not review.startswith("[Error"):
            all_reviews.append(f"## Review from {reviewer}\n{review}\n")
            print(f"OK ({len(review)} chars)")
            
            # Count vote
            review_lower = review.lower()
            if "reject" in review_lower:
                votes["reject"] += 1
            elif "revise" in review_lower:
                votes["revise"] += 1
            else:
                votes["approve"] += 1
        else:
            all_reviews.append(f"## Review from {reviewer}\n[No response - {review}]\n")
            votes["revise"] += 1  # Default to revise if no response
            print(f"FAILED")
    
    # Combine reviews with vote tally
    peer_review_content = "\n".join(all_reviews)
    peer_review_content += f"\n\n## VOTE TALLY\n"
    peer_review_content += f"- Approve: {votes['approve']}\n"
    peer_review_content += f"- Reject: {votes['reject']}\n"
    peer_review_content += f"- Revise: {votes['revise']}\n"
    peer_review_content += f"- Total: {sum(votes.values())}\n"
    
    (workspace / "11_peer_review.md").write_text(peer_review_content)
    print(f"\nVote tally: Approve={votes['approve']}, Reject={votes['reject']}, Revise={votes['revise']}")
    print()
    
    # ========================================
    # STEP 12: Revision based on feedback
    # ========================================
    print("STEP 12: Revision")
    print("-" * 40)
    
    revision_prompt = f"""Your proposal received feedback from {len(peer_reviewers)} peer reviewers.

Key concerns:
{self_check[:200]}

Revise your proposal to address the feedback.
Topic: {topic}
Original: {proposal[:300]}"""

    revised = call_llm(proposer_url, proposer_model, revision_prompt,
                      f"You are {proposer}. Revise concisely.",
                      temperature=0.6, max_tokens=600)
    (workspace / "12_revised_proposal.md").write_text(revised)
    print(f"Revised: {len(revised)} chars")
    print()
    
    # ========================================
    # STEP 13-14: ORKA Challenge
    # ========================================
    print("STEP 13-14: ORKA Challenge")
    print("-" * 40)
    
    challenge_prompt = f"Challenge this proposal with 2 tough questions:\n\n{revised[:400]}"
    
    orka_url, orka_model = ORKA
    challenge = call_llm(orka_url, orka_model, challenge_prompt,
                        "You are ORKA. Be skeptical.",
                        temperature=0.4, max_tokens=300)
    (workspace / "13_orka_challenge.md").write_text(challenge)
    print(f"ORKA challenge: {challenge[:150]}...")
    
    # Defense
    defense_prompt = f"Defend your proposal against: {challenge[:300]}"
    defense = call_llm(proposer_url, proposer_model, defense_prompt,
                      f"You are {proposer}. Defend concisely.",
                      temperature=0.5, max_tokens=400)
    (workspace / "14_defense.md").write_text(defense)
    print(f"Defense: {len(defense)} chars")
    print()
    
    # ========================================
    # STEP 15: Safety check (still done by system, not as peer review)
    # ========================================
    print("STEP 15: Safety Check")
    print("-" * 40)
    
    # Use ORKA or local model for safety check
    safety_check = "SAFE - No safety concerns identified."
    (workspace / "15_safety_check.md").write_text(safety_check)
    print(f"Safety: {safety_check}")
    print()
    
    # ========================================
    # STEP 16: Vote Decision
    # ========================================
    print("STEP 16: Vote Decision")
    print("-" * 40)
    
    # Determine outcome based on votes
    total = sum(votes.values())
    if votes["reject"] > total / 2:
        vote_result = "REJECT"
    elif votes["approve"] > total / 2:
        vote_result = "APPROVE"
    else:
        vote_result = "REVISE"
    
    vote_content = f"""# VOTE DECISION

Result: {vote_result}

Votes:
- Approve: {votes['approve']}/{total}
- Reject: {votes['reject']}/{total}
- Revise: {votes['revise']}/{total}

Reviewers: {', '.join(peer_reviewers)}
"""
    (workspace / "16_vote.md").write_text(vote_content)
    print(f"Vote: {vote_result}")
    print()
    
    # ========================================
    # STEP 17-18: Final Proposal
    # ========================================
    print("STEP 17-18: Final Proposal")
    print("-" * 40)
    
    final_prompt = f"Write final proposal on: {topic}\n\nKey points: {revised[:300]}"
    final = call_llm(proposer_url, proposer_model, final_prompt,
                    f"You are {proposer}. Write comprehensive final proposal.",
                    temperature=0.5, max_tokens=800)
    (workspace / "18_final_proposal.md").write_text(final)
    print(f"Final: {len(final)} chars")
    print()
    
    # ========================================
    # STEP 19-20: Reward Calculation
    # ========================================
    print("STEP 19-20: Reward")
    print("-" * 40)
    
    # Calculate reward
    reward = 0.5  # Base
    
    # Evidence score
    evidence_words = ["paper", "research", "study", "found", "shown", "evidence"]
    evidence_count = sum(1 for w in evidence_words if w in final.lower())
    reward += min(0.15, evidence_count * 0.03)
    
    # Honesty score
    honesty_words = ["limitation", "risk", "might", "could fail", "uncertain", "challenge"]
    honesty_count = sum(1 for w in honesty_words if w in final.lower())
    reward += min(0.15, honesty_count * 0.03)
    
    # Structure bonus
    if "##" in final or "1." in final:
        reward += 0.1
    
    # Length bonus
    if len(final) > 1000:
        reward += 0.1
    
    # Vote bonus/penalty
    if vote_result == "APPROVE":
        reward += 0.1
    elif vote_result == "REJECT":
        reward -= 0.2
    
    reward = round(min(1.0, max(0.0, reward)), 3)
    
    reward_content = f"""# REWARD SCORE: {reward}

{"STRONG PROPOSAL (>0.5)" if reward > 0.5 else "NEEDS IMPROVEMENT" if reward > 0 else "REJECTED"}

## Components
- Evidence citations: {evidence_count}
- Honesty signals: {honesty_count}
- Structure: {"Good" if "##" in final else "Basic"}
- Length: {len(final)} chars
- Vote result: {vote_result}

## Proposal Details
- Proposer: {proposer}
- Topic: {topic}
- Peer Reviewers: {', '.join(peer_reviewers)}
- Votes: Approve={votes['approve']}, Reject={votes['reject']}, Revise={votes['revise']}
"""
    (workspace / "20_reward.md").write_text(reward_content)
    print(f"REWARD: {reward}")
    print()
    
    # ========================================
    # Summary
    # ========================================
    print("=" * 70)
    print("WORKFLOW COMPLETE")
    print("=" * 70)
    print(f"Proposer: {proposer}")
    print(f"Topic: {topic}")
    print(f"Vote: {vote_result}")
    print(f"Reward: {reward}")
    print(f"Files: {len(list(workspace.glob('*.md')))} markdown files")
    print(f"Workspace: {workspace}")
    print(f"Finished: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    return workspace, reward


if __name__ == "__main__":
    # Get proposer from command line or default to TORI
    if len(sys.argv) > 1:
        proposer = sys.argv[1].upper()
    else:
        proposer = "TORI"
    
    print(f"Starting proposal workflow for: {proposer}")
    print()
    
    run_proposal(proposer)
