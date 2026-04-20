"""add_snapshot_isolation_and_atomic_flip

Revision ID: b1b2c3d4e5f6
Revises: a0a725601d8a
Create Date: 2026-04-19 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1b2c3d4e5f6'
down_revision: Union[str, None] = 'a0a725601d8a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create repo_snapshots table
    op.create_table(
        'repo_snapshots',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('repository_id', sa.String(length=36), nullable=False),
        sa.Column('branch_name', sa.String(length=255), nullable=False),
        sa.Column('commit_sha', sa.String(length=100), nullable=True),
        sa.Column('local_path', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_repo_snapshots_repository_id'), 'repo_snapshots', ['repository_id'], unique=False)

    # 2. Add active_snapshot_id to repositories
    op.add_column('repositories', sa.Column('active_snapshot_id', sa.String(length=36), nullable=True))
    op.create_foreign_key(
        'fk_repositories_active_snapshot', 'repositories', 'repo_snapshots',
        ['active_snapshot_id'], ['id'], ondelete='SET NULL'
    )

    # 3. Add snapshot_id to dependency_edges
    op.add_column('dependency_edges', sa.Column('snapshot_id', sa.String(length=36), nullable=True))
    op.create_foreign_key(
        'fk_dependency_edges_snapshot', 'dependency_edges', 'repo_snapshots',
        ['snapshot_id'], ['id'], ondelete='CASCADE'
    )
    op.create_index(op.f('ix_dependency_edges_snapshot_id'), 'dependency_edges', ['snapshot_id'], unique=False)

    # 4. Add snapshot_id to embedding_chunks
    op.add_column('embedding_chunks', sa.Column('snapshot_id', sa.String(length=36), nullable=True))
    op.create_foreign_key(
        'fk_embedding_chunks_snapshot', 'embedding_chunks', 'repo_snapshots',
        ['snapshot_id'], ['id'], ondelete='CASCADE'
    )
    op.create_index(op.f('ix_embedding_chunks_snapshot_id'), 'embedding_chunks', ['snapshot_id'], unique=False)

    # 5. Add snapshot_id to files
    op.add_column('files', sa.Column('snapshot_id', sa.String(length=36), nullable=True))
    op.create_foreign_key(
        'fk_files_snapshot', 'files', 'repo_snapshots',
        ['snapshot_id'], ['id'], ondelete='CASCADE'
    )
    op.create_index(op.f('ix_files_snapshot_id'), 'files', ['snapshot_id'], unique=False)

    # 6. Add snapshot_id to repo_intelligence
    op.add_column('repo_intelligence', sa.Column('snapshot_id', sa.String(length=36), nullable=True))
    op.create_foreign_key(
        'fk_repo_intelligence_snapshot', 'repo_intelligence', 'repo_snapshots',
        ['snapshot_id'], ['id'], ondelete='CASCADE'
    )
    op.create_index(op.f('ix_repo_intelligence_snapshot_id'), 'repo_intelligence', ['snapshot_id'], unique=False)

    # 7. Add snapshot_id to symbols
    op.add_column('symbols', sa.Column('snapshot_id', sa.String(length=36), nullable=True))
    op.create_foreign_key(
        'fk_symbols_snapshot', 'symbols', 'repo_snapshots',
        ['snapshot_id'], ['id'], ondelete='CASCADE'
    )
    op.create_index(op.f('ix_symbols_snapshot_id'), 'symbols', ['snapshot_id'], unique=False)


def downgrade() -> None:
    # Drop snapshot_id from all tables
    op.drop_index(op.f('ix_symbols_snapshot_id'), table_name='symbols')
    op.drop_constraint('fk_symbols_snapshot', 'symbols', type_='foreignkey')
    op.drop_column('symbols', 'snapshot_id')

    op.drop_index(op.f('ix_repo_intelligence_snapshot_id'), table_name='repo_intelligence')
    op.drop_constraint('fk_repo_intelligence_snapshot', 'repo_intelligence', type_='foreignkey')
    op.drop_column('repo_intelligence', 'snapshot_id')

    op.drop_index(op.f('ix_files_snapshot_id'), table_name='files')
    op.drop_constraint('fk_files_snapshot', 'files', type_='foreignkey')
    op.drop_column('files', 'snapshot_id')

    op.drop_index(op.f('ix_embedding_chunks_snapshot_id'), table_name='embedding_chunks')
    op.drop_constraint('fk_embedding_chunks_snapshot', 'embedding_chunks', type_='foreignkey')
    op.drop_column('embedding_chunks', 'snapshot_id')

    op.drop_index(op.f('ix_dependency_edges_snapshot_id'), table_name='dependency_edges')
    op.drop_constraint('fk_dependency_edges_snapshot', 'dependency_edges', type_='foreignkey')
    op.drop_column('dependency_edges', 'snapshot_id')

    op.drop_constraint('fk_repositories_active_snapshot', 'repositories', type_='foreignkey')
    op.drop_column('repositories', 'active_snapshot_id')

    op.drop_index(op.f('ix_repo_snapshots_repository_id'), table_name='repo_snapshots')
    op.drop_table('repo_snapshots')
