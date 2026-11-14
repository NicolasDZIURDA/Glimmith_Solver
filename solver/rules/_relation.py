from . import Rule
from solver.shapes import get_shape_signature


class RelationRule(Rule):
    """Pour chaque paire (a, b) : régions différentes, et formes identiques
    (same=True : gémeaux) ou différentes (same=False : delta)."""

    def __init__(self, ctx, pairs, same):
        self.same = same
        self.cells = ctx.cells
        self.pairs = []
        self._sig = {}
        for a, b in pairs:
            a, b = tuple(a), tuple(b)
            ia, ib = ctx.idx.get(a), ctx.idx.get(b)
            if ia is None or ib is None or not (ctx.valid_mask >> ia & 1) \
                    or not (ctx.valid_mask >> ib & 1):
                self.unsatisfiable = True       # case hors grille : aucune solution
                continue
            ctx.conflict[ia] |= ctx.bit[ib]
            ctx.conflict[ib] |= ctx.bit[ia]
            self.pairs.append((ctx.bit[ia], ctx.bit[ib]))

    def _signature(self, mask):
        sig = self._sig.get(mask)
        if sig is None:
            sig = get_shape_signature(
                [self.cells[i] for i in range(len(self.cells)) if mask >> i & 1])
            self._sig[mask] = sig
        return sig

    def region_ok(self, region, chosen):
        for ba, bb in self.pairs:
            other = bb if region & ba else ba if region & bb else 0
            if not other:
                continue
            for m in chosen:
                if m & other:
                    if (self._signature(region) == self._signature(m)) != self.same:
                        return False
                    break
        return True