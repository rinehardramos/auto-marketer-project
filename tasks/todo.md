# Auto Marketer: Phase Implementation TODO

This document details the roadmap for making the Auto Marketer AI agent self-improving. Multiple agents can work on these tickets in parallel, provided they update `tasks/agent-collab.md` first.

## Phase 1: Iterative Search & Self-Correction (Immediate)
- **Goal:** Implement a ReAct (Reason + Act) loop. The LLM should choose search queries dynamically instead of using a hardcoded search.
- **Tasks:**
  - Update `research_agent.py` to allow the LLM to call the `search_web` tool dynamically.
  - Wrap the search/analysis phase in a loop.
  - Ensure the agent evaluates if it has enough context before finalizing the JSON.
- **Dependencies:** None.

## Phase 2: Episodic Memory via Qdrant (Short-Term)
- **Goal:** Give the agent memory of its past mistakes using the vector database.
- **Tasks:**
  - Create a new Qdrant collection for `user_feedback`.
  - Write logic so that when a profile is graded (especially low grades), the profile context + feedback text is embedded and saved to Qdrant.
  - In `research_agent.py`, query Qdrant for similar past profiles before sending the prompt to the LLM.
  - Append relevant past feedback to the system prompt as "Warnings from past mistakes".
- **Dependencies:** Depends on grading data existing in Postgres.

## Phase 3: Dynamic Few-Shot Prompting (Medium-Term)
- **Goal:** Inject 5/5 and 1/5 examples into the prompt dynamically.
- **Tasks:**
  - Write a query in `research_agent.py` to fetch one perfect example and one failed example from Postgres.
  - Append these examples to the system prompt.
  - Ensure token limits are respected.
- **Dependencies:** Depends on graded data existing in Postgres.

## Phase 4: Multi-Agent Debate / Critic Pattern (Medium-Term)
- **Goal:** Introduce a secondary LLM call to double-check the work against historical feedback.
- **Tasks:**
  - Create a Critic Agent function that takes the Researcher's JSON and historical feedback as input.
  - The Critic should output a boolean (Approve/Reject) and a rationale.
  - Implement a retry loop (max 1-2 times) if the Critic rejects the initial analysis.
- **Dependencies:** Best implemented after Phase 2 or 3.

## Phase 5: Automated Fine-Tuning (Long-Term)
- **Goal:** Train the underlying model weights using highly graded data.
- **Tasks:**
  - Create a script (`export_dataset.py`) to dump 4/5 and 5/5 profiles into JSONL format.
  - Document the fine-tuning process.
  - Create an evaluation script to run the fine-tuned model against the base model using the `test_grading.py` suite.
- **Dependencies:** Requires a significant dataset of graded profiles (100+).
