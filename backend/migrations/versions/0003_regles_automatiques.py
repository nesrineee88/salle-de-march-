"""regles automatiques et origine des ordres

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-30 14:10:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotente : si le serveur de développement a déjà créé la table (create_all), on ne la recrée pas.
    inspecteur = sa.inspect(op.get_bind())
    if inspecteur.has_table('bacs_regles'):
        _ajouter_origine(inspecteur)
        return
    op.create_table('bacs_regles',
    sa.Column('utilisateur_id', sa.Integer(), nullable=False),
    sa.Column('regle_id', sa.Integer(), nullable=False),
    sa.Column('symbole', sa.String(length=20), nullable=False),
    sa.Column('type', sa.String(length=24), nullable=False),
    sa.Column('seuil', sa.Float(precision=53), nullable=False),
    sa.Column('part', sa.Float(precision=53), nullable=False),
    sa.Column('statut', sa.String(length=12), nullable=False),
    sa.Column('cree_le', sa.DateTime(), nullable=True),
    sa.Column('declenchee_le', sa.DateTime(), nullable=True),
    sa.Column('plus_haut', sa.Float(precision=53), nullable=True),
    sa.Column('motif', sa.String(length=300), nullable=True),
    sa.ForeignKeyConstraint(['utilisateur_id'], ['utilisateurs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('utilisateur_id', 'regle_id')
    )
    with op.batch_alter_table('bacs_regles', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_bacs_regles_statut'), ['statut'], unique=False)

    _ajouter_origine(inspecteur)


def _ajouter_origine(inspecteur) -> None:
    if 'origine' in {c['name'] for c in inspecteur.get_columns('bacs_ordres')}:
        return
    with op.batch_alter_table('bacs_ordres', schema=None) as batch_op:
        batch_op.add_column(sa.Column('origine', sa.String(length=40), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('bacs_ordres', schema=None) as batch_op:
        batch_op.drop_column('origine')

    with op.batch_alter_table('bacs_regles', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_bacs_regles_statut'))

    op.drop_table('bacs_regles')
