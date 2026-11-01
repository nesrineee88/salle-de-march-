"""scenarios de crise et actualites

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-31 09:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotente : le serveur de développement peut avoir déjà créé les tables (create_all).
    inspecteur = sa.inspect(op.get_bind())
    if not inspecteur.has_table('scenarios'):
        op.create_table('scenarios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nom', sa.String(length=120), nullable=False),
        sa.Column('description', sa.String(length=600), nullable=False),
        sa.Column('date_debut', sa.Date(), nullable=False),
        sa.Column('portee_type', sa.String(length=12), nullable=False),
        sa.Column('portee_valeurs', sa.JSON(), nullable=False),
        sa.Column('choc', sa.Float(precision=53), nullable=False),
        sa.Column('recuperation', sa.Float(precision=53), nullable=False),
        sa.Column('duree_recuperation_jours', sa.Integer(), nullable=False),
        sa.Column('actif', sa.Boolean(), nullable=False),
        sa.Column('cree_par', sa.Integer(), nullable=True),
        sa.Column('cree_le', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('scenarios', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_scenarios_actif'), ['actif'], unique=False)
            batch_op.create_index(batch_op.f('ix_scenarios_date_debut'), ['date_debut'], unique=False)
    if not inspecteur.has_table('actualites'):
        op.create_table('actualites',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('titre', sa.String(length=200), nullable=False),
        sa.Column('texte', sa.String(length=1200), nullable=False),
        sa.Column('symboles', sa.JSON(), nullable=False),
        sa.Column('type_source', sa.String(length=12), nullable=False),
        sa.Column('note_source', sa.String(length=300), nullable=False),
        sa.Column('actif', sa.Boolean(), nullable=False),
        sa.Column('scenario_id', sa.Integer(), nullable=True),
        sa.Column('cree_le', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('actualites', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_actualites_date'), ['date'], unique=False)
            batch_op.create_index(batch_op.f('ix_actualites_scenario_id'), ['scenario_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_actualites_type_source'), ['type_source'], unique=False)


def downgrade() -> None:
    op.drop_table('actualites')
    op.drop_table('scenarios')
