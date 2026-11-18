from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from sqlite3 import Connection as DBConnection

from alembic import command
from alembic.config import Config
from sqlalchemy import URL, Connection, Engine, create_engine, event

BACKEND = Path(__file__).resolve().parents[2]


def make_engine(path: Path) -> Engine:
    engine = create_engine(
        URL.create("sqlite", database=str(path.resolve())),
        hide_parameters=True,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def configure(connection: DBConnection, record: object) -> None:
        connection.isolation_level = None
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")

    @event.listens_for(engine, "begin")
    def begin(connection: Connection) -> None:
        immediate = connection.get_execution_options().get("immediate", False)
        connection.exec_driver_sql("BEGIN IMMEDIATE" if immediate else "BEGIN")

    return engine


@contextmanager
def write_transaction(engine: Engine) -> Iterator[Connection]:
    with engine.connect().execution_options(immediate=True) as conn, conn.begin():
        yield conn


def migrate(engine: Engine) -> None:
    cfg = Config(str(BACKEND / "alembic.ini"))
    with write_transaction(engine) as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
