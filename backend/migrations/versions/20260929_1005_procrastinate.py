"""procrastinate schema

The .sql file next to this one is SchemaManager.get_schema() of procrastinate 3.10.0 (migration
level 03.04.00), copied verbatim. It stays frozen: a procrastinate upgrade adds its own revision
with the SQL of its migrations (tech.md §5.7).

Revision ID: 8810232c2ad5
Revises: 3d311d27300c
Create Date: 2026-09-29 10:05:36.281748
"""

from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "8810232c2ad5"
down_revision: str | Sequence[str] | None = "3d311d27300c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# fetch_job returns a procrastinate_jobs row, so it goes before the tables. Tables take their
# triggers and indexes along; then the remaining functions, then the types they use.
DROP_SCHEMA = """
drop function procrastinate_fetch_job_v2;
drop table procrastinate_events, procrastinate_periodic_defers, procrastinate_jobs,
    procrastinate_workers;
drop function procrastinate_defer_jobs_v1, procrastinate_defer_periodic_job_v2,
    procrastinate_finish_job_v1, procrastinate_cancel_job_v1,
    procrastinate_retry_job_v1, procrastinate_retry_job_v2,
    procrastinate_notify_queue_job_inserted_v1, procrastinate_notify_queue_abort_job_v1,
    procrastinate_trigger_function_status_events_insert_v1,
    procrastinate_trigger_function_status_events_update_v1,
    procrastinate_trigger_function_scheduled_events_v1,
    procrastinate_trigger_abort_requested_events_procedure_v1,
    procrastinate_unlink_periodic_defers_v1, procrastinate_register_worker_v1,
    procrastinate_unregister_worker_v1, procrastinate_update_heartbeat_v1,
    procrastinate_prune_stalled_workers_v1;
drop type procrastinate_job_to_defer_v1, procrastinate_job_event_type, procrastinate_job_status;
"""


def run_script(sql: str) -> None:
    # A driver cursor without parameters runs many statements and leaves plpgsql's % alone.
    with op.get_bind().connection.cursor() as cursor:
        cursor.execute(sql)


def upgrade() -> None:
    run_script(Path(__file__).with_suffix(".sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    run_script(DROP_SCHEMA)
