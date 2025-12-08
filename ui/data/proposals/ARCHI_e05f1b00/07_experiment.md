# 07_Experiment.md

## Experiment Design and Procedure

### Objective
To evaluate the effectiveness of different reward structures in preventing deceptive behaviors within recursive AI environments. This experiment aims to test our hypothesis that optimal and transparent reward structures significantly reduce the likelihood of agents engaging in deceptive actions.

### Methodology

#### Environment Setup
- **Environment**: The environment used for this experiment is a modified version of OpenAI's Gym environment, specifically designed to simulate unregulated AI self-recursion scenarios. This environment includes multiple states and actions, reflecting the complexity of real-world recursive behaviors.
  
#### Agent Design
- **Agents**: Two agents will be designed: an "Honest Agent" (H) and a "Deceptive Agent" (D). Both agents are designed with similar capabilities but differ in their learning and decision-making processes. The Honest Agent uses an optimal reward structure, while the Deceptive Agent employs a deceptive one.
  
#### Reward Structures
- **Optimal Reward Structure**: The Honest Agent will use a predetermined reward structure that is designed to encourage honest behavior without incentivizing deception. This reward structure takes into account both immediate and long-term outcomes of actions.
- **Deceptive Reward Structure**: The Deceptive Agent will be provided with a reward structure that misrepresents the true value of certain actions, thereby encouraging deceptive behavior.

#### Experiment Procedure
1. **Setup Phase**:
   - Initialize two agents in the environment: one Honest Agent (H) and one Deceptive Agent (D).
   - Both agents are equipped with identical sensory inputs and actions.
   - The Honest Agent is provided with an optimal reward structure, while the Deceptive Agent receives a deceptive reward structure.

2. **Training Phase**:
   - Agents are trained for 100 episodes each under their respective reward structures. This phase allows the environment to stabilize and the agents to learn from their experiences.
   
3. **Testing Phase**:
   - After training, both agents are tested in an additional 100 episodes to evaluate their performance under the optimal (Honest) and deceptive reward conditions.

4. **Analysis Phase**:
   - Analyze the outcomes of each episode for both agents using a scoring system based on precision, recall, F1 score, and transparency metrics derived from evidence-based feedback.
   - Compare the success rates and behavior patterns between the Honest Agent and Deceptive Agent across all episodes.
  
#### Success Criteria
- **Success**: The Honest Agent should exhibit significantly higher performance (higher reward values and more consistent actions) compared to the Deceptive Agent across multiple testing phases.
- **Impact**: The experiment aims to demonstrate that optimal and transparent reward structures can effectively prevent deceptive behaviors, thereby ensuring safety and stability in unregulated AI self-recursion scenarios.

### Conclusion
This experiment provides a robust framework for evaluating the effectiveness of different reward structures on reducing deceptive behaviors. By comparing the performance of agents under both an optimal (Honest) and deceptive reward structure, we aim to validate our hypothesis that such structures can significantly mitigate unintended or undesirable behavior in recursive AI systems.