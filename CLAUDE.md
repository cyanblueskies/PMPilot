# Project: AI-Powered Agile Project Decision Support Platform

## Overview
Birmingham University CS Final Year Project. AI decision support platform
for agile/Jira-style project management, combining statistical anomaly
detection with LLM-based grounded generation and NL2SQL querying.

Full product spec: see `docs/PRD.md`
Full technical spec (architecture, FR list, data model, evaluation plan): see `docs/Project_Requirements.md`

## Stack
- Frontend: React + TypeScript (Vite), Recharts for charts
- Backend: FastAPI (Python), SQLAlchemy + Alembic
- Database: PostgreSQL
- LLM: via API (see docs/Project_Requirements.md section 5.4 for the two-engine design)

## Commands
- Frontend dev: `cd frontend; npm run dev`
- Backend dev: `cd backend; .\venv\Scripts\Activate.ps1; uvicorn app.main:app --reload`
- Backend tests: `cd backend; pytest`
- DB migration: `cd backend; alembic revision --autogenerate -m "message"`

## Conventions
- Backend follows layered structure: api/ (routes) -> services/ (business logic) -> models/ (ORM)
- LLM must only receive precomputed KPI/anomaly JSON, never raw issue tables directly (see grounded generation design)
