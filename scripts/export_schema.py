
"""Export the ORM schema to database/schema.sql for documentation."""

import sys
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.schema import CreateTable, CreateIndex

from app.core.database import Base
from app.models import orm  # noqa: F401  — registers all models

OUTPUT = Path(__file__).resolve().parent.parent / "database" / "schema.sql"


def export() -> None:
    """Render every table + index as DDL and write to schema.sql."""
    engine = create_engine("sqlite://", echo=False)
    buf = StringIO()
    buf.write("-- Auto-generated from ORM models via scripts/export_schema.py\n")
    buf.write("-- Do NOT edit by hand; re-run this script after changing orm.py.\n\n")

    for table in Base.metadata.sorted_tables:
        buf.write(str(CreateTable(table).compile(engine)))
        buf.write(";\n\n")
        for index in table.indexes:
            buf.write(str(CreateIndex(index).compile(engine)))
            buf.write(";\n")
        buf.write("\n")

    OUTPUT.write_text(buf.getvalue(), encoding="utf-8")
    print(f"[ok] wrote {OUTPUT} ({len(Base.metadata.sorted_tables)} tables)")


if __name__ == "__main__":
    export()
