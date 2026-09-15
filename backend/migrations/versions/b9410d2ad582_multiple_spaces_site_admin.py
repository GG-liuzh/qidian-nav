"""Multiple spaces, platform administrators and independent account recovery."""
from alembic import op
import sqlalchemy as sa

revision = "b9410d2ad582"
down_revision = "9cbed07c5915"
branch_labels = None
depends_on = None


def upgrade():
    sqlite = op.get_bind().dialect.name == "sqlite"
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("is_superadmin", sa.Boolean(), server_default="0" if sqlite else sa.false(), nullable=False))
        batch.add_column(sa.Column("version", sa.Integer(), server_default="1", nullable=False))
    with op.batch_alter_table("workspaces") as batch:
        batch.add_column(sa.Column("active", sa.Boolean(), server_default="1" if sqlite else sa.true(), nullable=False))
        batch.add_column(sa.Column("version", sa.Integer(), server_default="1", nullable=False))
    with op.batch_alter_table("site_settings") as batch:
        batch.add_column(sa.Column("home_workspace_id", sa.String(32), nullable=True))
        batch.create_foreign_key("fk_site_home_workspace", "workspaces", ["home_workspace_id"], ["id"])
    with op.batch_alter_table("sessions") as batch:
        batch.add_column(sa.Column("active_workspace_id", sa.String(32), nullable=True))
        batch.create_foreign_key("fk_session_active_workspace", "workspaces", ["active_workspace_id"], ["id"])
    op.create_table("account_resets",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_by", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
    )
    connection = op.get_bind()
    connection.execute(sa.text("UPDATE users SET is_superadmin = true WHERE id IN (SELECT owner_user_id FROM site_settings)"))
    connection.execute(sa.text("UPDATE site_settings SET home_workspace_id = (SELECT id FROM workspaces ORDER BY id LIMIT 1)"))
    connection.execute(sa.text("UPDATE sessions SET active_workspace_id = (SELECT workspace_id FROM memberships WHERE memberships.user_id = sessions.user_id AND memberships.active = true ORDER BY workspace_id LIMIT 1)"))
    # Simplifying private team permissions must never publish previously restricted resources.
    connection.execute(sa.text("UPDATE resources SET is_public = false WHERE category_id IN (SELECT id FROM categories WHERE scope = 'team' AND visibility = 'restricted')"))
    connection.execute(sa.text("UPDATE categories SET visibility = 'workspace' WHERE scope = 'team'"))
    connection.execute(sa.text("UPDATE workspaces SET collaboration_mode = 'maintainers'"))


def downgrade():
    op.drop_table("account_resets")
    with op.batch_alter_table("sessions") as batch:
        batch.drop_constraint("fk_session_active_workspace", type_="foreignkey")
        batch.drop_column("active_workspace_id")
    with op.batch_alter_table("site_settings") as batch:
        batch.drop_constraint("fk_site_home_workspace", type_="foreignkey")
        batch.drop_column("home_workspace_id")
    with op.batch_alter_table("workspaces") as batch:
        batch.drop_column("version")
        batch.drop_column("active")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("version")
        batch.drop_column("is_superadmin")
