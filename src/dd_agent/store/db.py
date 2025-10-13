from __future__ import annotations
import os
from contextlib import contextmanager
from typing import Iterator, Optional

try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
except Exception:
    create_engine = None
    sessionmaker = None


_engine = None
_Session = None


def configure(db_url: Optional[str]) -> None:
    global _engine, _Session
    if not db_url or not create_engine:
        _engine = None
        _Session = None
        return
    _engine = create_engine(db_url, future=True)
    _Session = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)


@contextmanager
def session_scope() -> Iterator:
    if _Session is None:
        yield None
        return
    s = _Session()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
