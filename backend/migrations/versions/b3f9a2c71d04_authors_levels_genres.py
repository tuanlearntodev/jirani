"""authors/levels/genres entities: books FK conversion, drop book_type

Revision ID: b3f9a2c71d04
Revises: 70ee18aafdca  (initial schema)
"""
from alembic import op
import sqlalchemy as sa

revision = "b3f9a2c71d04"
down_revision = "70ee18aafdca"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "authors",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(), nullable=False, unique=True, index=True),
    )
    op.create_table(
        "levels",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(), nullable=False, unique=True, index=True),
    )
    op.create_table(
        "genres",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(), nullable=False, unique=True, index=True),
    )
    op.add_column("books", sa.Column("author_id", sa.Integer(), nullable=True))
    op.add_column("books", sa.Column("level_id", sa.Integer(), nullable=True))
    op.add_column("books", sa.Column("genre_id", sa.Integer(), nullable=True))

    # Backfill authors/levels from DISTINCT trimmed lowercased strings
    op.execute(
        "INSERT INTO authors (name) "
        "SELECT DISTINCT lower(trim(author)) FROM books "
        "WHERE author IS NOT NULL AND trim(author) <> ''"
    )
    op.execute(
        "UPDATE books SET author_id = a.id FROM authors a "
        "WHERE lower(trim(books.author)) = a.name"
    )
    op.execute(
        "INSERT INTO levels (name) "
        "SELECT DISTINCT lower(trim(level)) FROM books "
        "WHERE level IS NOT NULL AND trim(level) <> ''"
    )
    op.execute(
        "UPDATE books SET level_id = l.id FROM levels l "
        "WHERE lower(trim(books.level)) = l.name"
    )
    # Genres: backfill ONLY rows whose book_type is not a junk MIME value.
    # (The old file_type conflation wrote "application/pdf" here; extension already
    #  carries the format, so junk is discarded, per spec §4.)
    op.execute(
        "INSERT INTO genres (name) "
        "SELECT DISTINCT lower(trim(book_type)) FROM books "
        "WHERE book_type IS NOT NULL AND trim(book_type) <> '' "
        "AND book_type NOT LIKE '%/%'"
    )
    op.execute(
        "UPDATE books SET genre_id = g.id FROM genres g "
        "WHERE lower(trim(books.book_type)) = g.name"
    )

    op.drop_column("books", "author")
    op.drop_column("books", "level")
    op.drop_column("books", "book_type")

    op.create_foreign_key("fk_books_author_id_authors", "books", "authors", ["author_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_books_level_id_levels", "books", "levels", ["level_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_books_genre_id_genres", "books", "genres", ["genre_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.add_column("books", sa.Column("author", sa.String(length=255), nullable=True))
    op.add_column("books", sa.Column("level", sa.String(length=100), nullable=True))
    op.add_column("books", sa.Column("book_type", sa.String(length=100), nullable=True))
    op.execute("UPDATE books SET author = a.name FROM authors a WHERE a.id = books.author_id")
    op.execute("UPDATE books SET level = l.name FROM levels l WHERE l.id = books.level_id")
    op.execute("UPDATE books SET book_type = g.name FROM genres g WHERE g.id = books.genre_id")
    op.drop_constraint("fk_books_author_id_authors", "books", type_="foreignkey")
    op.drop_constraint("fk_books_level_id_levels", "books", type_="foreignkey")
    op.drop_constraint("fk_books_genre_id_genres", "books", type_="foreignkey")
    op.drop_column("books", "author_id")
    op.drop_column("books", "level_id")
    op.drop_column("books", "genre_id")
    op.drop_table("genres")
    op.drop_table("levels")
    op.drop_table("authors")
