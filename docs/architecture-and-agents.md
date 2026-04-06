# System Architecture & Multi-Agent Design

## Core Components
1. **PostgreSQL:** The absolute source of truth. Stores raw profile JSON, research state, analytical conclusions, and user grades.
2. **Qdrant:** The vector database. Stores embeddings for semantic search (finding profiles conceptually similar to a target persona) and episodic memory (storing past user feedback).
3. **Redis (Planned):** Task queue for managing asynchronous, slow web research tasks across multiple worker agents.
4. **Local LLM (LM Studio):** The inference engine for text embeddings and analytical decision making.

## Agent Roles
- **Ingestion Agent (`ingest.py`):** Fetches data from Apify, saves to Postgres, embeds text, and saves to Qdrant. Enqueues research tasks (future).
- **Research Agent (`research_agent.py`):** Dequeues tasks, performs OSINT (DuckDuckGo, Scraping), and saves analysis and rationale to Postgres.
- **Critic Agent (Planned):** Reviews the Research Agent's output against historical user feedback before finalizing.
- **Grading/Eval System (`evaluate_grading.py`):** Allows users to grade research interactively. Calculates alignment between system confidence and human truth.

## Current Schema (PostgreSQL `linkedin_profiles`)
- `id` (VARCHAR PK)
- `first_name` (VARCHAR)
- `last_name` (VARCHAR)
- `headline` (TEXT)
- `about` (TEXT)
- `raw_data` (JSONB)
- `research_status` (VARCHAR)
- `is_smb` (BOOLEAN)
- `needs_outsourcing_prob` (DECIMAL)
- `needs_cheap_labor_prob` (DECIMAL)
- `searching_vendors_prob` (DECIMAL)
- `research_summary` (TEXT)
- `system_confidence_score` (INT)
- `confidence_rationale` (TEXT)
- `search_queries_used` (TEXT)
- `user_grade` (INT)
- `user_feedback` (TEXT)
