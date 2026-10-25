"""Isolated benchmark: never re-embeds or deletes the user's indexed documents."""

from run_full import main


if __name__ == "__main__":
    main(embedding_only=True)
