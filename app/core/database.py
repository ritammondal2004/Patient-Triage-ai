
"""Database engine, session factory and declarative base."""

from collections.abc import Iterator
           
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# FastAPI serves requests on a threadpool.
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    echo=settings.sql_echo,
    future=True,
    pool_pre_ping=True,
    connect_args=connect_args,  
)        

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """FastAPI dependency — one session per request."""
    db = SessionLocal()
    try:
        yield db 
    finally:
        db.close()


def init_db() -> None:
    """Create database (if PostgreSQL) and all tables. No Alembic for this prototype — the ORM is the schema, and
    scripts/export_schema.py dumps it to database/schema.sql for documentation.""" 
    from app.models import orm  
             
    # For PostgreSQL, create the database if it doesn't exist 
    if settings.database_url.startswith("postgresql"):
        from sqlalchemy import text
             
        # Strip any ?sslmode=... etc. before taking the database name.
        base_url, _, _ = settings.database_url.partition("?")
        db_name = settings.database_url.split("/")[-1]
        
        # Connect to postgres system database to create the target database
        admin_url = settings.database_url.rsplit("/", 1)[0] + "/postgres"
        admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

        try:
            with admin_engine.connect() as conn:
                exists = conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": db_name}
                ).scalar()   
                if exists:
                    print(f"[ok] database '{db_name}' already exists")
                else:
                    conn.execute(text(f'CREATE DATABASE "{db_name}";'))
                    print(f"[ok] database '{db_name}' created")
        except Exception as exc:
            print(f"[warn] could not verify/create database '{db_name}': {exc}")
        finally:
            admin_engine.dispose()  
               
    Base.metadata.create_all(bind=engine)


def reset_db() -> None:
    """Drop and recreate everything. Used by seed_data.py and the test fixtures."""
    from app.models import orm  # noqa: F401

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)