from . import Rule
from puzzle_utils import prepare_puzzle
from collections import defaultdict


class SymbolsRule(Rule):
    def __init__(self, ctx):
        self.ctx = ctx
        self._by_cell = None

    def _placements(self):
        ctx = self.ctx
        height = ctx.height
        width = ctx.width
        bit = ctx.bit
        valid_mask = ctx.valid_mask
        conflict = ctx.conflict

        _, _, _, symbol_positions = prepare_puzzle(ctx.puzzle)

        colors = list(symbol_positions)
        k = len(colors)

        if k < 1:
            self._by_cell = {}
            return

        n = height * width
        color_mask = [0] * k
        symbol_color = {}
        for ci, color in enumerate(colors):
            for r, c in symbol_positions[color]:
                i = r * width + c
                if not (valid_mask & bit[i]):
                    raise ValueError(
                        f"Le symbole {color} en {(r, c)} "
                        "est placé sur une case invalide."
                    )
                if i in symbol_color:
                    raise ValueError(
                        "Une cellule appartient à plusieurs couleurs."
                    )
                symbol_color[i] = ci
                color_mask[ci] |= bit[i]
        ALL = (1 << k) - 1
        shift_masks = defaultdict(int)
        for r in range(height):
            for c in range(width):
                i = r * width + c
                if not (valid_mask & bit[i]):
                    continue
                for nr, nc in (
                    (r - 1, c),
                    (r + 1, c),
                    (r, c - 1),
                    (r, c + 1),
                ):
                    if not (0 <= nr < height and 0 <= nc < width):
                        continue
                    j = nr * width + nc
                    if not (valid_mask & bit[j]):
                        continue
                    if conflict[i] & bit[j]:
                        continue
                    shift_masks[j - i] |= bit[i]
        shift_list = list(shift_masks.items())

        def expand(region):
            out = 0
            for d, mask in shift_list:
                x = region & mask
                out |= (x << d) if d > 0 else (x >> -d)
            return out

        def flood(start, allowed):
            reached = frontier = start
            while frontier:
                frontier = expand(frontier) & allowed & ~reached
                reached |= frontier
            return reached

        all_regions = set()

        def rec(region, forbidden, present):
            if present != ALL:
                reachable = flood(region, ~forbidden | region)
                for ci in range(k):
                    if not (present >> ci & 1):
                        if not (reachable & color_mask[ci]):
                            return

            frontier = expand(region) & ~region & ~forbidden
            if not frontier:
                if present == ALL:
                    all_regions.add(region)
                return
            
            v = frontier & -frontier
            i = v.bit_length() - 1
            forbidden_next = forbidden | conflict[i]
            present_next = present
            ci = symbol_color.get(i)
            if ci is not None:
                forbidden_next |= color_mask[ci] & ~v
                present_next |= 1 << ci
            rec(region | v, forbidden_next, present_next)
            rec(region, forbidden | v, present)
            
        for i in range(n):
            if not (color_mask[0] & bit[i]):
                continue
            forbidden = (
                (color_mask[0] & ~bit[i])
                | conflict[i]
            )
            rec(bit[i], forbidden, 1)
        by_cell = {}
        for mask in all_regions:
            m = mask

            while m:
                low = m & -m
                i = low.bit_length() - 1

                by_cell.setdefault(i, []).append(mask)
                m ^= low
        self._by_cell = by_cell
        print(f"Régions valides avec symboles : {len(all_regions)}")

    def candidates(self, u, comp):
        if self._by_cell is None:
            self._placements()
        for mask in self._by_cell.get(u, ()):
            if mask & ~comp == 0:
                yield mask
                

def build(ctx):
    return SymbolsRule(ctx)


def has_too_many_symbols(region, symbol_positions):
    """Vérifie si une région contient plusieurs symboles du même type."""

    return any(
        sum(cell in positions for cell in region) > 1
        for positions in symbol_positions.values()
    )


def has_one_each_symbol(region, symbol_positions):
    """Vérifie qu'une région contient exactement un symbole de chaque type."""

    return all(
        sum(cell in positions for cell in region) == 1
        for positions in symbol_positions.values()
    )
