from . import Rule
from ..shapes import get_shape_signature, get_shape_variants


class ShapeSetRule(Rule):
    """Moteur commun de match et mismatch : compare les formes de toutes les régions.

        same=True  (match)    : toutes les régions ont la même forme ;
        same=False (mismatch) : toutes les régions ont des formes différentes deux à deux.

    Rotations et miroirs comptent comme la même forme, comme pour gémeaux et delta.
    Elle compare des régions sans les définir : elle se combine avec symbols, precision,
    shape_bank, area ou polyomino."""

    def __init__(self, ctx, same):
        self.same = same
        self.cells = ctx.cells
        self.n = ctx.n
        self._sig = {}

    def _signature(self, mask):
        sig = self._sig.get(mask)
        if sig is None:
            sig = get_shape_signature([self.cells[i] for i in range(self.n) if mask >> i & 1])
            self._sig[mask] = sig
        return sig

    def region_ok(self, region, chosen):
        """Compare la région aux régions déjà choisies."""
        if not chosen:
            return True
        sig = self._signature(region)
        if self.same:
            return sig == self._signature(chosen[0])
        return all(sig != self._signature(m) for m in chosen)


class SameShapeRule(ShapeSetRule):
    """Version de match : une fois la première région posée, la forme des suivantes est connue,
    on les construit donc directement à cette forme (au lieu de les refuser après coup)."""

    def __init__(self, ctx):
        super().__init__(ctx, same=True)
        self.ctx = ctx
        self.required = None                # forme de la première région, si elle est déjà posée
        self._placements = {}               # forme -> masques de ses placements possibles

    def begin(self, chosen):
        """Appelé par le moteur juste avant de construire une région."""
        self.required = self._signature(chosen[0]) if chosen else None

    def _placements_of(self, sig):
        found = self._placements.get(sig)
        if found is not None:
            return found
        ctx = self.ctx
        found = set()
        for variant in get_shape_variants(sig):
            height = max(r for r, c in variant) + 1
            width = max(c for r, c in variant) + 1
            for r0 in range(ctx.height - height + 1):
                for c0 in range(ctx.width - width + 1):
                    mask = 0
                    for r, c in variant:
                        mask |= ctx.bit[(r0 + r) * ctx.width + c0 + c]
                    if mask & ~ctx.valid_mask:
                        continue
                    m, clash = mask, False
                    while m:
                        low = m & -m
                        if ctx.conflict[low.bit_length() - 1] & mask:
                            clash = True
                            break
                        m ^= low
                    if not clash:
                        found.add(mask)
        self._placements[sig] = found = list(found)
        return found

    # --- construction d'une région : state = (forme imposée ou None, cases déjà prises) ---
    def start(self, i):
        return self.add((self.required, 0), i)

    def add(self, state, i):
        required, mask = state
        return (required, mask | self.ctx.bit[i]), 0

    def closed(self, state, count):
        required = state[0]
        return required is not None and count >= len(required)

    def viable(self, state, count, reach):
        required, mask = state
        if required is None:
            return True
        r = reach()
        if r.bit_count() < len(required):
            return False
        # La région doit tenir dans un placement de la forme, lui-même atteignable.
        return any(not mask & ~p and not p & ~r for p in self._placements_of(required))

    def complete(self, state, count):
        required, mask = state
        return required is None or (count == len(required) and self._signature(mask) == required)