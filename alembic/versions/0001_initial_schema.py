"""
alembic/versions/0001_initial_schema.py
=======================================
Initial schema migration: ResolutionModel + RawAddressStagingModel.

Derived from persistence/models.py via alembic autogenerate —
no hand-written SQL.  Includes the review_status column added in Stage 4
so this serves as the unified baseline for Postgres deployments.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------------------------------------------
    # resolutions — permanent non-PII resolution records
    # -----------------------------------------------------------------
    op.create_table(
        "resolutions",
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("parsed", sa.JSON(), nullable=False),
        sa.Column("digipin", sa.String(15), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("needs_human_review", sa.Boolean(), nullable=False),
        sa.Column(
            "review_status",
            sa.String(20),
            nullable=False,
            server_default="auto_confirmed",
        ),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("pipeline_trace", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("ttl_for_raw_retention", sa.String(50), nullable=False),
        sa.PrimaryKeyConstraint("request_id"),
    )
    op.create_index("ix_resolutions_request_id", "resolutions", ["request_id"])
    op.create_index("ix_resolutions_review_status", "resolutions", ["review_status"])

    # -----------------------------------------------------------------
    # raw_address_staging — short-lived PII, TTL-purged
    # -----------------------------------------------------------------
    op.create_table(
        "raw_address_staging",
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("raw_address", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("purge_after", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["request_id"], ["resolutions.request_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("request_id"),
    )
    op.create_index(
        "ix_raw_staging_purge_after", "raw_address_staging", ["purge_after"]
    )
    op.create_index(
        "ix_raw_address_staging_request_id",
        "raw_address_staging",
        ["request_id"],
    )

    # -----------------------------------------------------------------
    # corrections — human-review feedback dataset
    # -----------------------------------------------------------------
    op.create_table(
        "corrections",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("reviewer_id", sa.String(128), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original_lat", sa.Float(), nullable=True),
        sa.Column("original_lng", sa.Float(), nullable=True),
        sa.Column("corrected_lat", sa.Float(), nullable=True),
        sa.Column("corrected_lng", sa.Float(), nullable=True),
        sa.Column("original_parsed", sa.JSON(), nullable=False),
        sa.Column("corrected_parsed", sa.JSON(), nullable=True),
        sa.Column("correction_notes", sa.Text(), nullable=True),
        sa.Column("turnaround_seconds", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["request_id"], ["resolutions.request_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_corrections_request_id", "corrections", ["request_id"])
    op.create_index("ix_corrections_reviewed_at", "corrections", ["reviewed_at"])


def downgrade() -> None:
    op.drop_table("corrections")
    op.drop_table("raw_address_staging")
    op.drop_table("resolutions")
