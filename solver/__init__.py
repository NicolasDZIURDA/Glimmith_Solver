from puzzle_utils import neighbors, validate_walls
from .core import REGISTRY, solve_puzzle


SUPPORTED_RULES = sorted(REGISTRY)      # une règle ajoutée au registre est reconnue partout


def _build_valid(puzzle):
    return {
        (r, c)
        for r, row in enumerate(puzzle["grid"])
        for c, ch in enumerate(row)
        if ch == "."
    }


def solve(puzzle, max_solutions=2, **options):
    valid = _build_valid(puzzle)
    walls = validate_walls(puzzle.get("walls", []), valid)
    return solve_puzzle(puzzle, valid, walls, neighbors, max_solutions, **options)