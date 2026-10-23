"""Create all tables from SKYLINE models, handling custom ENUMs and circular FKs."""
import sys
from app import app, db

try:
    import models  # noqa: F401
except Exception as e:
    print("WARN: could not import models:", e)

from sqlalchemy import text, Enum as SAEnum
from sqlalchemy.schema import CreateTable, AddConstraint
from sqlalchemy.dialects import postgresql

with app.app_context():
    metadata = db.metadata
    engine = db.engine
    pg = postgresql.dialect()

    print(f"Metadata has {len(metadata.tables)} tables registered.")
    if len(metadata.tables) == 0:
        print("No tables registered -- models.py not imported by app.py.")
        sys.exit(1)

    # ---------------------------------------------------------------
    # 1. Collect all ENUM types used by any column
    # ---------------------------------------------------------------
    enum_types = {}   # name -> list of values
    for table in metadata.tables.values():
        for col in table.columns:
            coltype = col.type
            if isinstance(coltype, SAEnum) and coltype.name:
                enum_types[coltype.name] = list(coltype.enums)

    print(f"Found {len(enum_types)} enum type(s): {list(enum_types)}")

    # ---------------------------------------------------------------
    # 2. Collect all FKs for later ALTER
    # ---------------------------------------------------------------
    deferred_fks = []
    for table in metadata.tables.values():
        for fk in table.foreign_key_constraints:
            deferred_fks.append((table, fk))

    with engine.begin() as conn:
        # ---- 2a. CREATE TYPE for each enum (idempotent) ----
        for name, values in enum_types.items():
            check = conn.execute(
                text("select 1 from pg_type where typname = :n"),
                {"n": name},
            ).first()
            if check:
                print(f"ENUM  : {name} already exists, skipping")
                continue
            vals = ", ".join("'" + v.replace("'", "''") + "'" for v in values)
            print(f"ENUM  : CREATE TYPE {name} AS ENUM ({vals})")
            conn.execute(text(f'CREATE TYPE "{name}" AS ENUM ({vals})'))

        # ---- 2b. CREATE TABLE without FKs ----
        for table in metadata.sorted_tables:
            fks_backup = list(table.foreign_key_constraints)
            for fk in fks_backup:
                table.constraints.discard(fk)
                for col in fk.columns:
                    col.foreign_keys = set()

            ddl = str(CreateTable(table).compile(dialect=pg))
            print("CREATE:", table.name)
            conn.execute(text(ddl))

            for fk in fks_backup:
                table.append_constraint(fk)

        # ---- 2c. Add FKs ----
        for table, fk in deferred_fks:
            if not fk.name:
                fk.name = f"fk_{table.name}_{'_'.join(c.name for c in fk.columns)}"
            try:
                add_ddl = str(AddConstraint(fk).compile(dialect=pg))
                print("ALTER :", table.name, "->", fk.name)
                conn.execute(text(add_ddl))
            except Exception as e:
                print(f"  [skip] {fk.name}: {e}")

    rows = db.session.execute(
        text("select tablename from pg_tables where schemaname='public' order by tablename")
    ).scalars().all()
    print(f"\nOK: {len(rows)} tables now exist:")
    for t in rows:
        print("  -", t)
