from . import Rule
from ..shapes import get_shape_signature


class MingleShapeRule(Rule):
    """Deux régions voisines (qui partagent un côté) n'ont pas la même forme.
    Rotations et miroirs comptent comme la même forme, comme pour gémeaux/delta.

    Cette règle compare des régions sans les définir : elle se combine avec
    symbols, precision ou shape_bank."""

    defines_regions = False

    def __init__(self, ctx):
        self.cells = ctx.cells
        self.n = ctx.n
        # Voisinage géométrique : deux régions se touchent même séparées par un mur.
        self.touch = [0] * ctx.n
        for i, (r, c) in enumerate(ctx.cells):
            if not (ctx.valid_mask >> i & 1):
                continue
            for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                j = ctx.idx.get((nr, nc))
                if j is not None and ctx.valid_mask >> j & 1:
                    self.touch[i] |= ctx.bit[j]
        self._sig = {}
        self._nb = {}

    def _signature(self, mask):
        sig = self._sig.get(mask)
        if sig is None:
            sig = get_shape_signature([self.cells[i] for i in range(self.n) if mask >> i & 1])
            self._sig[mask] = sig
        return sig

    def _neighbors(self, mask):
        """Cases extérieures à la région qui la touchent."""
        nb = self._nb.get(mask)
        if nb is None:
            nb, m = 0, mask
            while m:
                low = m & -m
                nb |= self.touch[low.bit_length() - 1]
                m ^= low
            nb &= ~mask
            self._nb[mask] = nb
        return nb

    def region_ok(self, region, chosen):
        nb = self._neighbors(region)
        sig = None
        for m in chosen:
            if m & nb:
                if sig is None:
                    sig = self._signature(region)
                if self._signature(m) == sig:
                    return False
        return True


def build(ctx):
    return MingleShapeRule(ctx) if "mingle_shape" in ctx.rule_types else None