"""Seed the synthetic drafts once without replacing edits made in the demo."""

import json
import sys
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.domain.models import VendorData  # noqa: E402
from app.persistence import repositories  # noqa: E402
from app.persistence.database import make_engine, migrate, write_transaction  # noqa: E402
from app.persistence.tables import vendor_request  # noqa: E402


def main() -> None:
    fixtures = json.loads(
        (ROOT / "sample_data" / "requests.json").read_text(encoding="utf-8")
    )
    engine = make_engine(Settings().database_path)
    try:
        migrate(engine)
        with write_transaction(engine) as connection:
            for fixture in fixtures:
                data = VendorData.model_validate(fixture)
                key = uuid5(NAMESPACE_URL, f"urn:vendorflow:demo:{data.vendor_name}")
                exists = connection.scalar(
                    select(vendor_request.c.id).where(vendor_request.c.id == str(key))
                )
                if not exists:
                    repositories.create(connection, key, data)
                print(f"{'existing' if exists else 'created'} {key} {data.vendor_name}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
