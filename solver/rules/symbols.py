from . import Rule


def _bits(mask):
    out = []
    while mask:
        low = mask & -mask
        out.append(low.bit_length() - 1)
        mask ^= low
    return out


def _perfect_matching(options):
    """options[a] = liste des partenaires possibles de a ; vrai si tous les a peuvent être appariés."""
    owner = {}

    def augment(a, seen):
        for b in options[a]:
            if b in seen:
                continue
            seen.add(b)
            if b not in owner or augment(owner[b], seen):
                owner[b] = a
                return True
        return False

    return all(augment(a, set()) for a in range(len(options)))


class SymbolsRule(Rule):
    def __init__(self, ctx, colors, positions):
        self.k = len(colors)
        self.ALL = (1 << self.k) - 1
        self.color_of = {}
        self.mask = [0] * self.k
        self.flood = ctx.flood
        self.nb = [sum(ctx.bit[j] for j in ctx.adj[i]) for i in range(ctx.n)]   # voisins d'une case
        for ci, color in enumerate(colors):
            for pos in positions[color]:
                i = ctx.idx[pos]
                if i in self.color_of:
                    raise ValueError("Une cellule appartient à plusieurs couleurs.")
                self.color_of[i] = ci
                self.mask[ci] |= ctx.bit[i]

    def start(self, i):
        return self.add(0, i)

    def add(self, present, i):
        ci = self.color_of.get(i)
        if ci is None:
            return present, 0
        return present | (1 << ci), self.mask[ci] & ~(1 << i)

    def viable(self, present, count, reach):
        if present == self.ALL:
            return True
        r = reach()
        return all(present >> ci & 1 or r & self.mask[ci] for ci in range(self.k))

    def complete(self, present, count):
        return present == self.ALL

    def leftover_ok(self, present, leftover):
        """`leftover` : un groupe connexe de cases hors de la région en cours de construction.
        Si la région a déjà un symbole de chaque couleur, elle ne peut plus en absorber :
        les symboles de ce groupe sont définitifs, ils doivent déjà être équilibrés et appariables.
        Un groupe sans aucun symbole reste possible : la région peut encore l'absorber."""
        if present != self.ALL:
            return True
        if not any(leftover & m for m in self.mask):
            return True
        return self.region_count(leftover) != 0

    def accepts(self, mask):
        return all((mask & m).bit_count() == 1 for m in self.mask)

    def region_count(self, comp):
        n0 = (comp & self.mask[0]).bit_count()
        if n0 == 0 or any((comp & m).bit_count() != n0 for m in self.mask):
            return 0
        if n0 > 1 and not self._pairable(comp):
            return 0
        return n0

    def _pairable(self, comp):
        """Chaque symbole de la couleur 0 doit pouvoir être apparié à un symbole de chaque autre
        couleur c (appariement parfait), car chaque région a un symbole de chaque couleur.

        Deux symboles (couleur 0 et couleur c) ne peuvent se retrouver dans la même région que
        s'ils sont voisins, ou s'ils touchent une même zone connexe de cases qui ne contient
        aucun autre symbole de ces deux couleurs. (Un symbole d'une troisième couleur peut, lui,
        servir de passage : la région en contient un.)"""
        first = _bits(comp & self.mask[0])
        for other_mask in self.mask[1:]:
            both = self.mask[0] | other_mask
            free = comp & ~both
            zones = []
            while free:
                z = self.flood(free & -free, free)
                zones.append(z)
                free &= ~z

            def touching(i):
                t, nbm = 0, self.nb[i]
                for j, z in enumerate(zones):
                    if nbm & z:
                        t |= 1 << j
                return t

            other = _bits(comp & other_mask)
            t_other = {b: touching(b) for b in other}
            options = []
            for a in first:
                ta, nba = touching(a), self.nb[a]
                options.append([b for b in other if ta & t_other[b] or nba >> b & 1])
            if not _perfect_matching(options):
                return False
        return True


def build(ctx):
    positions = ctx.symbol_positions
    return SymbolsRule(ctx, list(positions), positions) if positions else None