from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# SQLite DB 파일 경로 (프로젝트 루트에 생성됨)
DATABASE_URL = "sqlite:///./utility_belt.db"

# connect_args={"check_same_thread": False}는 SQLite에서만 필요함
# (FastAPI 등 멀티스레드 환경에서 한 스레드만 접근하는 제약을 풀기 위해)
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """
    DB 세션을 생성하고 반환하는 제너레이터 (Dependency Injection용)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
