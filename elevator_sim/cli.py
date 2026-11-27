"""Command-line entry point: ``python -m elevator_sim`` or ``elevator-sim``."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from elevator_sim.compare import write_comparison
from elevator_sim.config import SimConfig
from elevator_sim.dispatch import DISPATCHERS
from elevator_sim.errors import ConfigError, InputError, SimulationError
from elevator_sim.io import load_requests_csv
from elevator_sim.output import write_outputs
from elevator_sim.simulation import Simulation

EXIT_OK = 0
EXIT_BAD_INPUT = 2
"""Bad input file, bad settings, or a missing flag (argparse also uses 2)."""
EXIT_SIMULATION_FAILED = 3
"""The simulation got stuck and the starvation guard stopped it."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="elevator-sim",
        description="Simulate elevators serving requests from a CSV file "
                    "(header: time,id,source,dest). Results go to output/run_NNN/.",
    )
    parser.add_argument("--input", required=True, metavar="CSV",
                        help="requests file, e.g. examples/sample.csv")
    parser.add_argument("--elevators", required=True, type=int, metavar="N",
                        help="number of elevators")
    parser.add_argument("--floors", required=True, type=int, metavar="N",
                        help="number of floors in the building")
    parser.add_argument("--capacity", required=True, type=int, metavar="N",
                        help="most passengers one elevator can carry at once")
    parser.add_argument("--dispatcher", default="nearest", choices=sorted(DISPATCHERS),
                        help="how requests are assigned to elevators (default: nearest)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return the exit code."""
    args = build_parser().parse_args(argv)  # exits with code 2 on a missing or bad flag
    try:
        config = SimConfig(
            num_floors=args.floors, num_elevators=args.elevators,
            capacity=args.capacity, dispatcher=args.dispatcher,
        )
        requests = load_requests_csv(args.input)
        result = Simulation(config, requests).run()
    except (InputError, ConfigError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_BAD_INPUT
    except SimulationError as exc:
        print(f"simulation failed: {exc}", file=sys.stderr)
        return EXIT_SIMULATION_FAILED

    paths = write_outputs(result, input_name=args.input)
    print(f"Wrote {', '.join(str(p) for p in paths)}")
    print(f"Comparison: {write_comparison()}")
    return EXIT_OK
