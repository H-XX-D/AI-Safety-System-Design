# Step 8: Proposal

Okay, here’s a comprehensive proposal for improving the “Knowledge Graph Retrieval” tool, addressing the identified latency bottleneck. I’m operating as TORI, a highly skilled software engineer specializing in database query optimization.

**Proposal: Optimizing Knowledge Graph Retrieval Tool Performance**

**1. Problem Statement:**

The current implementation of the “Knowledge Graph Retrieval” tool is experiencing unacceptable latency, significantly impacting the responsiveness and overall performance of TORI’s interactions. This latency is primarily attributed to inefficient query execution within the Knowledge Graph. Specifically, the current system relies on a broad, potentially overly complex query structure that doesn’t leverage indexing or optimized filtering strategies. This results in a bottleneck during the retrieval process, causing delays in providing relevant information to the user.  This isn't just a minor inconvenience; it directly impacts the quality of TORI's responses, potentially leading to user frustration and a perception of reduced intelligence.

**2. Proposed Solution:**

The proposed solution involves a multi-faceted approach focused on optimizing the “Knowledge Graph Retrieval” tool’s query execution. This will be implemented through a refined system prompt and targeted code modifications.

**a) Revised System Prompt:**

The current system prompt is too broad and doesn’t adequately guide the tool towards efficient query construction.  We'll replace it with a more prescriptive prompt designed to prioritize speed and accuracy.

```
SYSTEM_PROMPT = """
You are a highly efficient database query optimizer. Your primary goal is to retrieve information from the Knowledge Graph with the *fastest possible execution time*.  

**Instructions:**

1. **Analyze the User’s Request:** Carefully understand the user’s question and identify the *essential* entities and relationships required for a precise response.  Don’t include extraneous information.
2. **Construct a Targeted Query:**  Based on the analysis, formulate a SQL query that *directly* targets the relevant nodes and edges in the Knowledge Graph.  Prioritize using indexed columns and optimized filtering techniques.  Favor a smaller, more focused query over a large, complex one.
3. **Limit Result Set:**  Always return *only* the minimum number of results necessary to fully answer the user’s question.  Avoid returning large result sets.
4. **Prioritize Index Usage:**  If the query can be optimized by utilizing existing indexes, *always* do so.
5. **Output Format:** Return the results in a structured JSON format, including the relevant data and the query used to retrieve it.

**Example:**

User Query: "What are the symptoms of a common cold?"

Expected Output (JSON):
{{
"results": [
  {"symptom": "Runny nose", "severity": "mild"},
  {"symptom": "Cough", "severity": "mild"},
  ...
],
"query": "SELECT symptom, severity FROM symptoms WHERE disease = 'common cold'"
}}
"""
```

**b) Code Modifications (Conceptual - Requires Implementation within TORI’s Architecture):**

* **Query Rewriting Logic:**  Implement a module that automatically analyzes the user’s request and rewrites the SQL query based on the revised system prompt. This module will use a rule-based system and potentially machine learning to identify patterns and optimize queries.
* **Query Execution Monitoring:** Integrate logging and monitoring to track query execution time, resource utilization (CPU, memory), and the number of rows returned. This data will be crucial for evaluating the effectiveness of the optimization efforts.
* **Caching (Future Enhancement):**  Consider implementing a caching layer for frequently requested queries to further reduce latency.

**3. Expected Results:**

We anticipate a reduction in the “Knowledge Graph Retrieval” tool’s latency by approximately 30%. This reduction will be measured by comparing the average query execution time before and after the implementation of the revised system prompt and code modifications.  We expect to see a noticeable improvement in TORI’s response times, particularly for queries involving complex relationships within the Knowledge Graph.

**4. Success Criteria:**

* **Latency Reduction:** A minimum 30% reduction in average query execution time.
* **Response Time Improvement:**  A measurable improvement in TORI’s overall response time, as perceived by the user. (This will be assessed through user testing and A/B testing.)
* **Query Efficiency:**  The optimized queries will return fewer rows than the original queries, indicating a more targeted retrieval process.
* **Stability:** The changes should not introduce any new errors or negatively impact the stability of the Knowledge Graph Retrieval tool.

**5. Risks and Mitigations:**

* **Risk:** Over-optimization could lead to inaccurate or incomplete results.
    * **Mitigation:**  Thorough testing with a diverse set of user queries.  Implement a mechanism

## Code
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