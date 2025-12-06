# Step 12: Revision

Okay, you’re right to call me out – that was a very high-level, almost purely aspirational description. Let’s shift gears and focus on a practical, actionable proposal.  Given the feedback about the latency issue and the user's background as a database query optimization specialist, here’s a revised proposal:

**Revised Proposal: Knowledge Graph Retrieval Optimization – Prompt Engineering Focus**

**Executive Summary:**

This proposal outlines a targeted approach to optimizing the performance of the Knowledge Graph Retrieval tool by focusing on refining the system prompts used by the AI assistant. Recognizing the user's expertise in database query optimization, this work will prioritize prompt design to minimize unnecessary data retrieval, reduce redundant calculations, and ultimately, decrease query latency.

**Understanding the Problem:**

The current system is experiencing latency issues during Knowledge Graph retrieval. As a database query optimization specialist, you'll understand the critical impact of poorly designed queries – even seemingly minor inefficiencies can dramatically slow down response times.  This likely stems from overly broad prompts, lack of context, or the AI assistant’s inability to effectively translate the user’s intent into a precise, optimized query.

**Proposed Approach:**

1. **Prompt Template Analysis:** We will meticulously analyze the provided prompt template, identifying potential bottlenecks. This includes scrutinizing the phrasing for ambiguity, the level of detail requested, and any assumptions made by the AI assistant.

2. **Targeted Prompt Refinement:**  We will implement a series of iterative prompt revisions, focusing on the following techniques:
    * **Precision & Specificity:** Replacing vague language with concrete terms and quantifiable requirements.
    * **Contextualization:** Adding relevant context to the prompt to guide the AI assistant towards the most efficient query structure.  (e.g., specifying the desired data format, number of results, or specific relationships within the Knowledge Graph).
    * **Query Structure Guidance:**  Introducing explicit instructions to the AI assistant about the preferred query structure (e.g., "Return only the *direct* relationship between X and Y," or "Use a JOIN operation to retrieve related entities").
    * **Constraint Implementation:** Adding constraints to limit the scope of the query and prevent the AI assistant from exploring irrelevant branches of the Knowledge Graph.

3. **Performance Testing & Iteration:**  Each prompt revision will be rigorously tested using a controlled environment. We’ll measure query latency (response time) and analyze the resulting data to assess the impact of the changes. This iterative process will allow us to identify the most effective prompt refinements.

4. **Documentation:**  Detailed documentation of each prompt revision, including the rationale behind the changes and the resulting performance metrics, will be maintained.


**Key Considerations (Based on User’s Expertise):**

*   We will prioritize techniques that directly translate to optimized database queries – minimizing full table scans, leveraging indexes, and reducing the number of joins.
*   We’ll

## Revised Code
```
You are a highly skilled software engineer specializing in optimizing database query performance. Your primary task is to refine system prompts for AI assistants designed to improve the performance of a "Knowledge Graph Retrieval" tool. 

Your goal is to create a precise and testable system prompt that, when used by the AI assistant, will lead to a measurable reduction in latency and, consequently, a decrease in average user query response time.

Specifically, you must generate a system prompt that incorporates the following elements:

1.  **Clear Objective:** The prompt must clearly state the desired outcome – reducing the latency of the “Knowledge Graph Retrieval” tool.
2.  **Quantifiable Target:** The prompt must specify a target reduction in latency – a 30% reduction.
3.  **Expected Consequence:** The prompt must articulate the anticipated result of this latency reduction – a 25% decrease in average user query response time.
4.  **Justification:** The prompt must include a brief explanation of *why* this outcome is expected – a faster retrieval process will…
5.  **Role-Playing:** You should adopt a professional and confident tone, reflecting the expertise of a software engineer.
6.  **Testability:** The prompt should be designed to allow for clear measurement of the AI assistant’s performance.

Output ONLY the prompt text.
```