"""Initial migration - create voices table

Revision ID: 001
Revises:
Create Date: 2025-01-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'voices',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('original_format', sa.String(length=10), nullable=False),
        sa.Column('duration_seconds', sa.Float(), nullable=False),
        sa.Column('sample_rate', sa.Integer(), nullable=False),
        sa.Column('processed_audio_path', sa.String(length=512), nullable=False),
        sa.Column('chatterbox_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('orpheus_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('language', sa.String(length=10), nullable=False, server_default='en'),
        sa.Column('tags', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('processing_status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_voices_name'), 'voices', ['name'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_voices_name'), table_name='voices')
    op.drop_table('voices')
