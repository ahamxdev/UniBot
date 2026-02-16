import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from urllib.parse import quote_plus


# Load environment variables from .env file
load_dotenv()


# Database configuration from environment or defaults
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")

# Validate required configuration early
_missing = [
    name
    for name, value in [
        ("DB_USER", DB_USER),
        ("DB_PASS", DB_PASS),
        ("DB_NAME", DB_NAME),
        ("DB_HOST", DB_HOST),
        ("DB_PORT", DB_PORT),
    ]
    if not value
]
if _missing:
    raise RuntimeError(f"Missing database environment variables: {', '.join(_missing)}")

# URL-encode password to safely include in connection string
DB_PASS_ENCODED = quote_plus(DB_PASS)

# Construct the PostgreSQL connection string
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS_ENCODED}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create a SQLAlchemy engine for connecting to the database
engine = create_engine(
    DATABASE_URL,
    echo=False,       # Set to True to log SQL queries for debugging
    future=True       # Enables use of SQLAlchemy 2.0-style API
)

# Create a session factory for interacting with the database
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True
)

# Base class for all ORM models
Base = declarative_base()

def init_db():
    """
    Initializes the database by creating all tables 
    defined in models if they do not already exist.
    """
    # Ensure models are imported so they are registered on Base.metadata
    from db import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    # Base.metadata.drop_all(bind=engine)
