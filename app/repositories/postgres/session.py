from __future__ import annotations
from contextlib import contextmanager
from sqlalchemy import create_engine,text
from sqlalchemy.orm import sessionmaker,Session

class Database:
    def __init__(self,url:str):
        if not url:raise ValueError("DATABASE_URL is required for STORAGE_BACKEND=postgres")
        normalized=url.replace("postgresql://","postgresql+psycopg://",1) if url.startswith("postgresql://") else url
        # PostgreSQL renders timestamptz values in the session timezone.  Keep
        # repository serialization backend-neutral by always reading UTC, as
        # the File backend and public Pydantic contracts do.
        self.engine=create_engine(normalized,pool_pre_ping=True,future=True,connect_args={"options":"-c timezone=UTC"})
        self.session_factory=sessionmaker(self.engine,expire_on_commit=False,class_=Session)
    def health_check(self)->bool:
        try:
            with self.engine.connect() as connection:connection.execute(text("SELECT 1"))
            return True
        except Exception:return False
    def require_healthy(self):
        if not self.health_check():raise ConnectionError("PostgreSQL is unavailable; STORAGE_BACKEND=postgres will not fall back to file")
    @contextmanager
    def session(self):
        session=self.session_factory()
        try:yield session;session.commit()
        except Exception:session.rollback();raise
        finally:session.close()
