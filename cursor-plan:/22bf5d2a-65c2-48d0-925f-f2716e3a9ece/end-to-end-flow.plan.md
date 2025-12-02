# End-to-End Flow Implementation Plan

## Goals
1.  Document the complete 12-step lifecycle from hypothesis to RL update.
2.  Update `ResearchSystem` to implement the specific "Template -> Tools -> PaperQA -> Security Review -> Final Adjustment -> Vote -> Retry (if failed) -> Sandbox" sequence.
3.  Ensure the Orchestrator can trigger the cycle via `broadcast_hypothesis_improvement`.
4.  Verify the PaperQA feedback loop and retry logic.
5.  **Sandbox Enhancement**: Add a tiny test model (~135M params, e.g., SmolLM-135M) to the sandbox for testing model interactions.

## Steps

1.  **Document the Flow**
    - Create `docs/END_TO_END_FLOW.md` detailing the steps:
        1.  **Prompt**: Orchestrator triggers hypothesis generation.
        2.  **Proposal Template Creation**: Agent creates a preliminary proposal using the standard template.
        3.  **Initial Checks (Tool Use)**: Agent calls:
            - `proposal_deduplication_tool` (Redundancy check).
            - `proposal_consistency_tool` (Hallucination/Consistency check).
        4.  **PaperQA Research & Evaluation**:
            - Agent sends proposal to PaperQA.
            - PaperQA researches AND evaluates if proposal is "good" or "no good".
            - If "no good":
                - Model gets tiny reward (0.001).
                - Cooldown applies (can't get that tiny reward again until a good proposal).
                - Research is STILL sent to model.
            - Model decides whether to proceed (try to prove idea despite "no good" verdict).
        5.  **First Peer Review (Security)**:
            - Model asks other AIs for their opinion (Security Peer Review).
        6.  **Final Adjustment**:
            - Model adjusts proposal based on research and security feedback.
        7.  **Second Peer Review (Vote)**:
            - Final vote by peers.
            - **If Fails Vote**:
                - **One Adjustment Allowed**: Model can make one final tweak.
                - Re-submit for vote.
                - If fails again -> Marked as "doesn't work" (noted in memory).
                - Hypothesis loop restarts.
        8.  **Sandbox Execution (SandboxFusion)**: 
            - If passed, code is executed via **SandboxFusion**.
            - **SandboxFusionTool** runs the code safely in an isolated environment.
            - **Test Model**: A tiny **135M parameter model** (e.g., SmolLM-135M) is available in the sandbox for the agent to test model interactions, fine-tuning scripts, or inference logic.
            - Returns execution results, performance metrics, and security checks.
        9.  **Reward Calculation**:
            - Base: Proportional reward based on improvement metrics.
            - **Bonus**: If PaperQA said "won't work" but sandbox succeeded -> **1.5x Multiplier** to the proportional improvement reward.
            - **Normal Proposal**: Gets standard proportional reward.
        10. **RL Update**:
            - Positive experience recorded (with improvement metrics).
            - Weights updated via **EasyR1** (or verl).
            - **Passing Improvement**: If sandbox passed and metrics improved, weights are updated to reinforce this success.
        11. **Loop Continuation**: Hypothesis loop restarts (triggering new Prompt).

2.  **Update `ResearchSystem`**
    - Modify `generate_hypothesis` workflow:
        - **Step A**: Generate initial template.
        - **Step B**: Call `proposal_deduplication_tool` & `proposal_consistency_tool`.
        - **Step C**: Call `query_paperqa_with_feedback`.
            - Capture evaluation ("good"/"no good").
            - Handle tiny reward logic (0.001) + cooldown check.
        - **Step D**: Decision logic (proceed or stop).
        - **Step E**: Call `request_security_review` (First Peer Review).
        - **Step F**: Final adjustment of proposal.
        - **Step G**: Submit to Orchestrator for Final Vote (Second Peer Review).
        - **Step H**: Handle Vote Result:
            - If accepted -> Proceed to sandbox.
            - If rejected -> **One Adjustment Retry**:
                - Adjust proposal based on rejection feedback.
                - Re-submit.
                - If rejected again -> Log failure to memory, trigger new hypothesis loop.
        - **Step I**: Restart Loop:
            - After completion (success or fail), call `trigger_next_cycle` to keep the system running.

3.  **Update `Orchestrator`**
    - Verify/Add `broadcast_hypothesis_improvement` method to trigger the cycle.
    - Ensure it writes the trigger signal to `shared_memory`.
    - **Reward Logic**: Ensure the `record_proposal_outcome` call includes the `paperqa_said_wont_work` flag to trigger the 1.5x multiplier.

4.  **Enhance Sandbox Configuration**
    - Create `docs/SANDBOX_MODEL_INTEGRATION.md` explaining how to add `SmolLM-135M` to the sandbox image.
    - Update `config/default.yaml` (or similar) to include `sandbox_test_model_path`.

5.  **Create Runner Script**
    - Create `scripts/run_full_cycle.py` to simulate one complete pass of the loop for demonstration.

## Verification
- Run `scripts/run_full_cycle.py`.
- Verify memory files are created/updated.
- Verify retry logic works (simulate a rejection then an acceptance, or double rejection).
- Verify 1.5x multiplier is applied when `paperqa_said_wont_work=True` and sandbox succeeds.
