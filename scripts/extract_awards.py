"""Turn PPIP release packages in data/ into the compact award snapshot the tools search.

To download fresh packages first, run `python -m awardline refresh` instead.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from awardline.snapshot import build_snapshot  # noqa: E402


def main() -> None:
    result = build_snapshot()
    print(f"wrote {result['award_count']} awards to {result['path']}")


if __name__ == "__main__":
    main()
