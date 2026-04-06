# Email generation & prompts

`auto-marketer` uses a single, focused LLM agent to generate personalized outreach. The research logic (ReAct loop, critic, memory) has been offloaded to the sibling `info-broker` service.

## Email generation agent

The agent takes a prospect profile (retrieved from `info-broker`) and a campaign's goal and tone to craft a personalized message.

### Core prompts

The system prompt is designed to ensure the output is valid JSON, facilitating automated parsing and storage.

**System Prompt Example:**
```text
You are a senior marketing specialist. You will be provided with a 
prospect's profile and a campaign goal and tone. Your task is to 
craft a personalized cold email that is professional, concise, 
and directly addresses the prospect's background.

You MUST respond in JSON format with exactly two keys: "subject" 
and "body".
```

**Human Prompt Example:**
```text
Goal: {goal}
Tone: {tone}

Prospect Profile:
{profile_text}
```

## JSON parsing & safety

The `EmailGenerator` class includes logic to:
1. **Strip Markdown:** Clean LLM responses of ` ```json ` blocks.
2. **NUL-byte scrubbing:** Remove NUL bytes to prevent PostgreSQL storage errors.
3. **Fallback Handling:** If the LLM fails to provide valid JSON after a retry, the generation for that specific profile is marked as failed.

## Batching

Email generation is parallelized using a `ThreadPoolExecutor`. The `workers` count can be adjusted via the API or CLI to tune performance based on your LLM provider's rate limits.
