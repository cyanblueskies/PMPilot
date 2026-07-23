-- Read-only role for NL2SQL query execution (FR-D1).
--
-- This is defence layer 2 in .claude/rules/security.md: the SELECT-only whitelist
-- can be bypassed by a clever generated statement, but this role has no grant to
-- bypass. It must exist even though the whitelist is already there.
--
-- Runs once, when the volume is first initialised. To re-run after editing:
--   docker compose down -v ; docker compose up -d

CREATE ROLE pmpilot_ro LOGIN PASSWORD 'pmpilot_ro_dev';

GRANT CONNECT ON DATABASE pmpilot TO pmpilot_ro;
GRANT USAGE ON SCHEMA public TO pmpilot_ro;

-- Existing tables (none at init time, but harmless and correct if re-run).
GRANT SELECT ON ALL TABLES IN SCHEMA public TO pmpilot_ro;

-- Tables Alembic creates later, as the pmpilot role, are covered automatically.
-- Without this line every new migration silently makes its table unreadable to
-- NL2SQL until someone re-grants by hand.
ALTER DEFAULT PRIVILEGES FOR ROLE pmpilot IN SCHEMA public
    GRANT SELECT ON TABLES TO pmpilot_ro;
