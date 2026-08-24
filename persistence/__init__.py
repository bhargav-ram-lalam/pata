"""
Persistence package for Pata.
Provides SQLAlchemy database models, repository operations, and TTL purging.
"""

from persistence.database import get_db_session, init_db, SessionLocal
from persistence.models import ResolutionModel, RawAddressStagingModel
from persistence.repository import (
    save_resolution,
    get_resolution_by_id,
    purge_expired_raw_addresses,
)

__all__ = [
    "get_db_session",
    "init_db",
    "SessionLocal",
    "ResolutionModel",
    "RawAddressStagingModel",
    "save_resolution",
    "get_resolution_by_id",
    "purge_expired_raw_addresses",
]
