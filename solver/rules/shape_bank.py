from . import Rule
from solver.shapes import get_shape_variants


class ShapeBankRule(Rule):
    provides_candidates = True
    
    def __init__(self, ctx):
        self.ctx = ctx
        self._by_cell = None
        self.count = 0

    def _placements(self):
        ctx = self.ctx
        height, width, bit, conflict = ctx.height, ctx.width, ctx.bit, ctx.conflict
        masks = set()
        for shape in ctx.puzzle.get("shape_bank", []):
            for variant in get_shape_variants(shape):
                sh = max(r for r, c in variant) + 1
                sw = max(c for r, c in variant) + 1
                for r0 in range(height - sh + 1):
                    for c0 in range(width - sw + 1):
                        mask = 0
                        for r, c in variant:
                            mask |= bit[(r0 + r) * width + c0 + c]
                        if mask & ~ctx.valid_mask:
                            continue
                        m, bad = mask, False
                        while m:                       # aucune paire séparée par un mur
                            low = m & -m
                            if conflict[low.bit_length() - 1] & mask:
                                bad = True
                                break
                            m ^= low
                        if not bad:
                            masks.add(mask)
        self.count = len(masks)
        by_cell = {}
        for mask in masks:
            m = mask
            while m:
                low = m & -m
                by_cell.setdefault(low.bit_length() - 1, []).append(mask)
                m ^= low
        self._by_cell = by_cell

    def candidates(self, u, comp):
        if self._by_cell is None:
            self._placements()
        for mask in self._by_cell.get(u, ()):
            if mask & ~comp == 0:
                yield mask
                
    def info(self):
        return {"placements de la banque": self.count} if self._by_cell is not None else {}
                

def build(ctx):
    return ShapeBankRule(ctx)