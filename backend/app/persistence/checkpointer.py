import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver


@contextmanager
def open_checkpointer(path: Path) -> Iterator[SqliteSaver]:
    with closing(
        sqlite3.connect(path, check_same_thread=False, timeout=5)
    ) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        saver = SqliteSaver(connection)
        saver.setup()
        yield saver
