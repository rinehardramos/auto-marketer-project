# Agent Collaboration Protocol

**CRITICAL MANDATE:** ALL agents MUST check this document before starting work and update it when claiming or finishing a task. This prevents race conditions and duplicated effort.

## 🚀 Active Work
*(Format: `[Date] - [Agent ID/Name] - [Task Description] - [Target Files]`)*
- 

## ✅ Recently Completed
*(Format: `[Date] - [Agent ID/Name] - [Task Description] - [PR/Commit if applicable]`)*
- [2026-04-07] - [Gemini CLI] - [Feature: Light Data Export & Personalized Email Generation] - [None]
- [2026-04-07] - [Gemini CLI] - [Feature: Data Export System (JSON, CSV, XLSX)] - [None]
- [2026-04-07] - [Gemini CLI] - [Phase 1 MVP: ReAct Loop for Research Agent] - [None]

## 🔴 BLOCKED / Needs User Input
- 

## 📝 Conventions & Rules
1. Never start a ticket already in `Active Work`.
2. Update this file in the SAME commit as your work.
3. Check `shared/db/src/migrations/` for the highest number and reserve the next number here before creating a migration.
4. Grep for existing routes in a service's `routes/` directory before adding new ones.
5. Run `git show origin/main -- <file>` for key files before writing new code to avoid duplication with merged work.
