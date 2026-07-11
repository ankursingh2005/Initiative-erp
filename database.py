from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# --------------------------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------------------------
# Right now we are using SQLite - a simple database that lives in a
# single file (scheme_erp.db) with ZERO setup required. Perfect for
# learning and testing.
#
# LATER, when you install SQL Server 2022 (as per your SRS), you will
# replace the line below with something like this:
#
# SQLALCHEMY_DATABASE_URL = (
#     "mssql+pyodbc://YOUR_USERNAME:YOUR_PASSWORD@YOUR_SERVER/SchemeERP_Dev"
#     "?driver=ODBC+Driver+18+for+SQL+Server"
# )
#
# You will NOT need to change any other file when you do this switch.
# --------------------------------------------------------------------

SQLALCHEMY_DATABASE_URL = "sqlite:///./scheme_erp.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Gives each API request its own database connection, and closes it
    automatically when the request is done."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()