"""Compatibility baseline for the invitation/account revision installed locally.

Keep this revision in the chain so databases already at c3d8f7a9b641 can upgrade.
Schema comments and nullable unlimited limits are applied by the next revision.
"""

import sqlalchemy as sa
from alembic import op

revision = "c3d8f7a9b641"
down_revision = "b9410d2ad582"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.add_column("invitations", sa.Column("max_uses", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("invitations", sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"))
    op.execute(sa.text("UPDATE invitations SET used_count = 1 WHERE used_at IS NOT NULL"))


def downgrade():
    op.execute(
        sa.text("UPDATE invitations SET used_at = CURRENT_TIMESTAMP WHERE used_count > 0 AND used_at IS NULL")
    )
    with op.batch_alter_table("invitations") as batch:
        batch.drop_column("used_count")
        batch.drop_column("max_uses")
    op.drop_column("users", "deleted_at")
