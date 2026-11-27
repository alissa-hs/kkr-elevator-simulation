"""Generate examples/busy.csv: an office day in a 100-floor building.

Run from the project folder:  python examples/generate_busy.py
The seed is fixed, so the file is the same every time. Floor 1 is the lobby.

  Morning arrival   ticks 0-59     300 passengers  lobby -> random floor 2-100
  Daytime           ticks 60-539   150 passengers  random floor -> random other floor
  Evening departure ticks 540-599  300 passengers  random floor 2-100 -> lobby

Suggested settings: --elevators 10 --floors 100 --capacity 10
"""

import csv
import random
from pathlib import Path

SEED = 2026
FLOORS = 100
LOBBY = 1
OUT = Path(__file__).parent / "busy.csv"


def main() -> None:
    rng = random.Random(SEED)
    rows = []

    for i in range(300):  # morning: everyone arrives at the lobby
        rows.append((rng.randint(0, 59), f"am{i:03d}", LOBBY, rng.randint(2, FLOORS)))

    for i in range(150):  # daytime: meetings, lunch, visits between floors
        source = rng.randint(1, FLOORS)
        dest = rng.choice([f for f in range(1, FLOORS + 1) if f != source])
        rows.append((rng.randint(60, 539), f"day{i:03d}", source, dest))

    for i in range(300):  # evening: everyone heads back down to the lobby
        rows.append((rng.randint(540, 599), f"pm{i:03d}", rng.randint(2, FLOORS), LOBBY))

    rows.sort(key=lambda r: r[0])  # by time; same-time rows keep generation order
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["time", "id", "source", "dest"])
        writer.writerows(rows)
    print(f"Wrote {len(rows)} requests to {OUT}")


if __name__ == "__main__":
    main()
