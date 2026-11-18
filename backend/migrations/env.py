from alembic import context
from sqlalchemy import Connection

from app.core.config import Settings
from app.persistence.database import make_engine, write_transaction
from app.persistence.tables import metadata


def run(connection: Connection) -> None:
    context.configure(
        connection=connection, target_metadata=metadata, render_as_batch=True
    )
    with context.begin_transaction():
        context.run_migrations()


connection = context.config.attributes.get("connection")
if connection is None:
    engine = make_engine(Settings().database_path)
    try:
        with write_transaction(engine) as conn:
            run(conn)
    finally:
        engine.dispose()
else:
    run(connection)
