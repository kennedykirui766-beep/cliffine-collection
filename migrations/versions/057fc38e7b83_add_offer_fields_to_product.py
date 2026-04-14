from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = '057fc38e7b83'
down_revision = 'd1e3d0f276ca'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('products', sa.Column('is_on_offer', sa.Boolean(), nullable=True, server_default=sa.false()))
    op.add_column('products', sa.Column('offer_percentage', sa.Float(), nullable=True))
    op.add_column('products', sa.Column('offer_start', sa.DateTime(), nullable=True))
    op.add_column('products', sa.Column('offer_end', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('products', 'offer_end')
    op.drop_column('products', 'offer_start')
    op.drop_column('products', 'offer_percentage')
    op.drop_column('products', 'is_on_offer')