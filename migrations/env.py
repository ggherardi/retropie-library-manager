from alembic import context

from backend.db import Base, make_engine

engine = context.config.attributes.get("engine") or make_engine()
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()
