from __future__ import annotations

import os

from sqlalchemy import create_engine, text


def main() -> None:
    engine = create_engine(
        os.environ["DATABASE_URL"],
        connect_args={"connect_timeout": 3},
        pool_timeout=3,
    )
    try:
        with engine.connect() as connection:
            if connection.execute(text("SELECT 1")).scalar() != 1:
                raise RuntimeError("PostgreSQL SELECT 1 returned an unexpected value")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
