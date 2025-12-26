"""add last_status to transcription_jobs

Revision ID: 20241224addstatus
Revises: 0f6280dfce9a
Create Date: 2025-12-24 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20241224addstatus'
down_revision = '0f6280dfce9a'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c['name'] for c in insp.get_columns('transcription_jobs')]
    if 'last_status' not in cols:
        op.add_column(
            'transcription_jobs',
            sa.Column('last_status', sa.String(length=255), nullable=False, server_default='Queued')
        )


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c['name'] for c in insp.get_columns('transcription_jobs')]
    if 'last_status' in cols:
        op.drop_column('transcription_jobs', 'last_status')
