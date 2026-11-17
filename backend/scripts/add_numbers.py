"""Load rented virtual numbers into the assistant-number pool.

    python -m scripts.add_numbers --provider exotel +918047491899 +918047491900

Each user gets one number from this pool when they set up forwarding. Numbers released by a
user rest for 30 days before anyone else can get them.
"""

import argparse
import asyncio

from app.db import create_all, sessionmaker
from app.models import NumberPoolEntry
from app.phone import normalize


async def add(numbers: list[str], provider: str, region: str) -> None:
    await create_all()
    async with sessionmaker()() as session:
        for raw in numbers:
            number = normalize(raw, region)
            if not number:
                print(f"skipped invalid number: {raw}")
                continue
            if await session.get(NumberPoolEntry, number):
                print(f"already in pool: {number}")
                continue
            session.add(NumberPoolEntry(number=number, provider=provider, region=region))
            print(f"added {number} ({provider})")
        await session.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("numbers", nargs="+")
    parser.add_argument("--provider", choices=["exotel", "plivo", "twilio"], required=True)
    parser.add_argument("--region", default="IN")
    args = parser.parse_args()
    asyncio.run(add(args.numbers, args.provider, args.region))


if __name__ == "__main__":
    main()
