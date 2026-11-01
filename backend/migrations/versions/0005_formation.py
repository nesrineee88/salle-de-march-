"""formation : progression et lecons desactivees

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-31 22:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspecteur = sa.inspect(op.get_bind())
    if not inspecteur.has_table('formation_progres'):
        op.create_table('formation_progres',
        sa.Column('utilisateur_id', sa.Integer(), nullable=False),
        sa.Column('lecon_id', sa.String(length=30), nullable=False),
        sa.Column('meilleur_score', sa.Float(), nullable=False),
        sa.Column('dernier_score', sa.Float(), nullable=False),
        sa.Column('tentatives', sa.Integer(), nullable=False),
        sa.Column('reussie_le', sa.DateTime(timezone=True), nullable=True),
        sa.Column('derniere_tentative', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['utilisateur_id'], ['utilisateurs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('utilisateur_id', 'lecon_id')
        )
    if not inspecteur.has_table('formation_lecons_desactivees'):
        op.create_table('formation_lecons_desactivees',
        sa.Column('lecon_id', sa.String(length=30), nullable=False),
        sa.PrimaryKeyConstraint('lecon_id')
        )


def downgrade() -> None:
    op.drop_table('formation_lecons_desactivees')
    op.drop_table('formation_progres')
