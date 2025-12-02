# End-to-End Hypothesis Improvement Flow

This document outlines the complete 12-step lifecycle of an improvement proposal, from initial hypothesis to reinforcement learning update.

## The Cycle

### 1. Prompt & Trigger
The **Orchestrator** initiates the cycle by broadcasting a "hypothesis improvement" signal to the research agents. This can be triggered manually, on a schedule, or after a successful sandbox execution.

### 2. Proposal Template Creation
The **Research Agent** starts by creating a preliminary proposal using the standard system template. This structure ensures all necessary sections (Motivation, Changes, Risks) are present.

### 3. Initial Checks (Tool Use)
The agent uses internal tools to self-verify the proposal before proceeding:
-   **`proposal_deduplication_tool`**: Checks if this idea has been tried before or is currently active.
-   **`proposal_consistency_tool`**: Checks for hallucinations, logical inconsistencies, and internal contradictions.

### 4. PaperQA Research & Evaluation
If initial checks pass, the agent queries **PaperQA** for evidence-grounded research.
-   **Research**: PaperQA retrieves relevant papers and technical documentation.
-   **Evaluation**: PaperQA evaluates if the proposal is "good" (supported by evidence) or "no good" (contradicts evidence/won't work).
-   **"No Good" Feedback**:
    -   Agent receives a **tiny reward** (0.001) for checking.
    -   A **cooldown** is applied (cannot get this tiny reward again until a good proposal is submitted).
    -   Research findings are still returned to the agent.
-   **Decision**: The agent decides whether to stop or **proceed anyway** (taking a risk to prove the evidence wrong/incomplete).

### 5. First Peer Review (Security)
The agent requests a **Security Peer Review** from other agents. This focuses specifically on safety, side effects, and security implications.

### 6. Final Adjustment
Based on the research findings and security feedback, the agent makes final adjustments to the proposal.

### 7. Second Peer Review (Vote)
The refined proposal is submitted to the Orchestrator for a formal **Peer Vote**.
-   **If Accepted**: Proceed to Sandbox.
-   **If Rejected**:
    -   **One Adjustment Allowed**: The agent can make one final tweak based on rejection feedback.
    -   **Re-submit**: The proposal is voted on again.
    -   **If Fails Again**: Marked as "doesn't work" (noted in long-term memory) and the hypothesis loop restarts.

### 8. Sandbox Execution
If the vote passes, the code is executed in an isolated **Sandbox Environment**.
-   **Tests**: Regression tests, new feature tests, performance benchmarks.
-   **Verification**: The system verifies if the claimed improvements (speed, accuracy) were actually achieved.

### 9. Reward Calculation
The **Reward Computer** calculates the final reward signal:
-   **Base Reward**: Proportional to the improvement metrics (e.g., +10% speed = +1.0 reward).
-   **Bonus Multiplier**: If PaperQA said "won't work" but the sandbox execution SUCCEEDED, a **1.5x Multiplier** is applied to the reward.
-   **Normal Proposal**: Gets standard proportional reward.

### 10. RL Update
The experience (Prompt, Response, Reward) is recorded.
-   **Training**: The system uses **verl** (Volcano Engine Reinforcement Learning) to update the model weights.
-   **Reinforcement**:
    -   **Passing Improvement**: Weights are updated to reinforce the behaviors that led to success.
    -   **Failures**: Weights are updated to avoid behaviors that led to rejection/failure.

### 11. Loop Continuation
The cycle completes. The Orchestrator triggers the next hypothesis loop, ensuring continuous recursive self-improvement.

## System Components

-   **Orchestrator**: Manages workflow, voting, and triggers.
-   **ResearchSystem**: The agent generating and refining proposals.
-   **PaperQA**: Evidence engine and "AI Gatekeeper".
-   **AIMemorySystem**:
    -   *Short-term*: Current proposal context.
    -   *Long-term*: "Doesn't work" notes, successful patterns.
    -   *Shared*: Global knowledge base.
-   **RLTrainer (verl)**: Handles weight updates.





