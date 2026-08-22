"""Clear one account's run allowance.

    python -m app.scripts.reset_quota you@example.com

This exists because a demo owner has to be able to run the demo. The limit is deliberate
and enforced server-side, so there is no in-app way to lift it — which is the point. This
is the out-of-band key, and it needs shell access to the machine holding the database.

To lift the limit for everyone instead, set FREE_RUN_LIMIT=0 and restart.
"""

from __future__ import annotations

import asyncio
import sys

from dotenv import load_dotenv


async def main(email: str) -> int:
    load_dotenv()
    from app.db import repo
    from app.db.engine import session_factory

    async with session_factory()() as db:
        user = await repo.get_user_by_email(db, repo.normalise_email(email))
        if user is None:
            print(f"No account for {email}.", file=sys.stderr)
            return 1
        before = await repo.count_runs_for_user(db, user.id)
        cleared = await repo.reset_runs_for_user(db, user.id)
        print(f"{email}: cleared {cleared} run(s) (was {before} used).")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(asyncio.run(main(sys.argv[1])))
