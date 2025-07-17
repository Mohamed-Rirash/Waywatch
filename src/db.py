from databases import Database
from sqlalchemy import (Column, DateTime, Float, Integer, MetaData, String,
                        Table, create_engine)

SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./activity.sqlite3"

metadata = MetaData()


engine = create_engine(SQLALCHEMY_DATABASE_URL.replace("+aiosqlite", ""))

session = Database(SQLALCHEMY_DATABASE_URL)


# TODO: Define the model or table

tracker = Table(
    "tracker",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("start", DateTime),
    Column("end", DateTime),
    Column("duration_seconds", Float),
    Column("title", String),
    Column("tab", String),
    Column("Date", DateTime),
)


metadata.create_all(engine)
