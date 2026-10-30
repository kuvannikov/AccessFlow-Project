from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker


def database_is_available(session_factory: sessionmaker[Session]) -> bool:
    try:
        with session_factory() as session:
            session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    return True
