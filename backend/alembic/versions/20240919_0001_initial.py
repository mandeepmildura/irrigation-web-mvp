"""initial database schema

Revision ID: 20240919_0001
Revises: 
Create Date: 2024-09-19 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20240919_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "zones",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False, server_default=""),
        sa.UniqueConstraint("name", name="uq_zones_name"),
    )
    op.create_index("ix_zones_id", "zones", ["id"], unique=False)
    op.create_index("ix_zones_name", "zones", ["name"], unique=False)

    op.create_table(
        "schedules",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("zone_id", sa.Integer(), sa.ForeignKey("zones.id"), nullable=False),
        sa.Column("start_time", sa.String(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("days_of_week", sa.String(), nullable=False, server_default="*"),
        sa.Column("skip_if_moisture_over", sa.Float(), nullable=True),
        sa.Column("moisture_lookback_minutes", sa.Integer(), nullable=False, server_default="120"),
        sa.Column("last_run_minute", sa.String(), nullable=True),
    )
    op.create_index("ix_schedules_id", "schedules", ["id"], unique=False)

    op.create_table(
        "sensor_readings",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("zone_name", sa.String(), nullable=False),
        sa.Column("metric", sa.String(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("ts", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_sensor_readings_id", "sensor_readings", ["id"], unique=False)
    op.create_index("ix_sensor_readings_zone_name", "sensor_readings", ["zone_name"], unique=False)
    op.create_index("ix_sensor_readings_metric", "sensor_readings", ["metric"], unique=False)
    op.create_index("ix_sensor_readings_ts", "sensor_readings", ["ts"], unique=False)

    op.create_table(
        "irrigation_runs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("zone_name", sa.String(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("ts", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_irrigation_runs_id", "irrigation_runs", ["id"], unique=False)
    op.create_index("ix_irrigation_runs_zone_name", "irrigation_runs", ["zone_name"], unique=False)
    op.create_index("ix_irrigation_runs_source", "irrigation_runs", ["source"], unique=False)
    op.create_index("ix_irrigation_runs_ts", "irrigation_runs", ["ts"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_irrigation_runs_ts", table_name="irrigation_runs")
    op.drop_index("ix_irrigation_runs_source", table_name="irrigation_runs")
    op.drop_index("ix_irrigation_runs_zone_name", table_name="irrigation_runs")
    op.drop_index("ix_irrigation_runs_id", table_name="irrigation_runs")
    op.drop_table("irrigation_runs")

    op.drop_index("ix_sensor_readings_ts", table_name="sensor_readings")
    op.drop_index("ix_sensor_readings_metric", table_name="sensor_readings")
    op.drop_index("ix_sensor_readings_zone_name", table_name="sensor_readings")
    op.drop_index("ix_sensor_readings_id", table_name="sensor_readings")
    op.drop_table("sensor_readings")

    op.drop_index("ix_schedules_id", table_name="schedules")
    op.drop_table("schedules")

    op.drop_index("ix_zones_name", table_name="zones")
    op.drop_index("ix_zones_id", table_name="zones")
    op.drop_table("zones")
