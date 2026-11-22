"""jeu : parties de La Salle Obscure

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-22 18:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspecteur = sa.inspect(op.get_bind())
    if not inspecteur.has_table('jeu_parties'):                   # le serveur de développement a pu la créer avant
        op.create_table('jeu_parties',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('utilisateur_id', sa.Integer(), nullable=False),
        sa.Column('film', sa.String(length=20), nullable=False),
        sa.Column('mode', sa.String(length=10), nullable=False),
        sa.Column('difficulte', sa.String(length=15), nullable=False),
        sa.Column('statut', sa.String(length=12), nullable=False),
        sa.Column('premiere', sa.Boolean(), nullable=False),
        sa.Column('seance', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('plan', sa.JSON(), nullable=True),
        sa.Column('presentation', sa.JSON(), nullable=False),
        sa.Column('ordres', sa.JSON(), nullable=False),
        sa.Column('choix', sa.JSON(), nullable=False),
        sa.Column('devine', sa.String(length=20), nullable=True),
        sa.Column('note', sa.Integer(), nullable=True),
        sa.Column('cree_le', sa.DateTime(timezone=True), nullable=False),
        sa.Column('maj_le', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['utilisateur_id'], ['utilisateurs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_jeu_parties_utilisateur_id', 'jeu_parties', ['utilisateur_id'])


def downgrade() -> None:
    op.drop_index('ix_jeu_parties_utilisateur_id', table_name='jeu_parties')
    op.drop_table('jeu_parties')
