from . import Rule

def _rotations(pattern):
    """Le motif et ses trois rotations (nord -> est -> sud -> ouest)."""
    out = {pattern}
    for _ in range(3):
        pattern = ((pattern << 1) | (pattern >> 3)) & 15
        out.add(pattern)
    return out


def _patterns_of(spec):
    """Ensemble des motifs acceptés pour une forme (toutes ses rotations, le sens n'importe pas).

    Un motif est un entier de 4 bits, un bit par côté clôturé : nord = 1, est = 2, sud = 4, ouest = 8.
        fermée  : 4 côtés clôturés          ouverte : aucun côté clôturé
        angle   : 2 côtés contigus          droit   : 2 côtés opposés
        impasse : 3 côtés (un seul ouvert)  t       : 1 seul côté clôturé
    """
    shapes = {"closed": 1 | 2 | 4 | 8, "four_way": 0, "corner": 1 | 2, "straight": 1 | 4,
              "dead_end": 1 | 2 | 4, "tee": 1}
    aliases = {"fermee": "closed", "fermée": "closed", "ouvert": "four_way", "ouverte": "four_way",
               "croix": "four_way", "angle": "corner", "droit": "straight", "droite": "straight",
               "impasse": "dead_end", "cul_de_sac": "dead_end", "t": "tee"}
    key = str(spec).strip().lower().replace("-", "_").replace(" ", "_")
    key = aliases.get(key, key)
    if key not in shapes:
        raise ValueError(
            f"Forme de palissade inconnue : {spec!r} (attendu : closed, four_way, corner, straight, "
            "dead_end ou tee)")
    return _rotations(shapes[key])


def _parse(raw):
    """Renvoie une liste de ((ligne, colonne), motifs acceptés) à partir de l'une des deux écritures :

        "palisade": {"corner": [[0,0], [2,3]], "NE": [[1,1]]}     (indication -> positions)
        "palisade": [[0,0,"corner"], [2,3,"corner"], [1,1,"NE"]]   (ligne, colonne, indication)
    """
    pairs = []
    if isinstance(raw, dict):
        for spec, cells in raw.items():
            patterns = _patterns_of(spec)
            if cells and isinstance(cells[0], int):
                cells = [cells]
            pairs += [(tuple(cell), patterns) for cell in cells]
    elif isinstance(raw, list):
        for item in raw:
            if not isinstance(item, (list, tuple)) or len(item) != 3:
                raise ValueError(f"Entrée de palissade mal formée : {item!r} (attendu : [ligne, colonne, indication])")
            pairs.append(((item[0], item[1]), _patterns_of(item[2])))
    else:
        raise ValueError('"palisade" doit être un objet ou une liste.')
    return pairs


class PalisadeRule(Rule):
    """Une case palissade a, parmi ses 4 côtés, exactement ceux qui sont clôturés : un côté est
    clôturé quand le voisin n'est pas dans la même région (ou n'existe pas).

    Elle contraint des régions sans les définir : elle se combine avec symbols, precision,
    shape_bank, area ou polyomino (seule, les régions restent libres)."""

    defines_regions = False

    def __init__(self, ctx, pairs):
        self.bit = ctx.bit
        directions = [(-1, 0), (0, 1), (1, 0), (0, -1)]
        allowed = {}                                    # case -> motifs encore possibles
        for cell, patterns in pairs:
            i = ctx.idx.get(cell)
            if i is None or not (ctx.valid_mask >> i & 1):
                self.unsatisfiable = True               # case hors grille
                continue
            allowed[i] = allowed[i] & patterns if i in allowed else set(patterns)

        # Voisins (0 si absent : hors grille ou trou) et motifs réellement possibles.
        self.nb, self.fence_nb, self.open_nb, self.allowed = {}, {}, {}, {}
        for i, patterns in allowed.items():
            r, c = ctx.cells[i]
            nb = []
            for dr, dc in directions:
                j = ctx.idx.get((r + dr, c + dc))
                nb.append(ctx.bit[j] if j is not None and ctx.valid_mask >> j & 1 else 0)
            usable = []
            for p in sorted(patterns):
                # Un côté ouvert exige un voisin présent, et non séparé par un mur.
                if all(p >> d & 1 or (nb[d] and not ctx.conflict[i] & nb[d]) for d in range(4)):
                    usable.append(p)
            if not usable:
                self.unsatisfiable = True               # aucun motif réalisable pour cette case
                continue
            self.nb[i] = nb
            self.allowed[i] = usable
            self.fence_nb[i] = {p: sum(nb[d] for d in range(4) if p >> d & 1) for p in usable}
            self.open_nb[i] = {p: sum(nb[d] for d in range(4) if not p >> d & 1) for p in usable}

        self.palmask = 0
        for i in self.allowed:
            self.palmask |= ctx.bit[i]
        # Cases dont l'état peut changer quand on ajoute i à la région : i et ses voisins palissade.
        self.watch = {}
        for i in range(ctx.n):
            r, c = ctx.cells[i]
            near = [i] + [ctx.idx[(r + dr, c + dc)] for dr, dc in directions if (r + dr, c + dc) in ctx.idx]
            self.watch[i] = tuple(j for j in near if j in self.allowed)
        self.clue_cells = self.palmask
        self.preferred_cells = self.palmask

    # --- construction d'une région : state = masque des cases déjà prises -------------
    def start(self, i):
        return self.add(0, i)

    def add(self, region, i):
        region |= self.bit[i]
        forbid = 0
        for c in self.watch[i]:
            if not region & self.bit[c]:
                continue
            fits = [p for p in self.allowed[c] if not self.fence_nb[c][p] & region]
            if not fits:
                return None                             # un voisin clôturé vient d'entrer dans la région
            common = 15
            for p in fits:
                common &= p
            for d in range(4):                          # côtés clôturés dans tous les motifs restants
                if common >> d & 1:
                    forbid |= self.nb[c][d]
        return region, forbid

    def viable(self, region, count, reach):
        r = reach()
        m = region & self.palmask
        while m:
            low = m & -m
            c = low.bit_length() - 1
            m ^= low
            if not any(not self.fence_nb[c][p] & region and not self.open_nb[c][p] & ~r
                       for p in self.allowed[c]):
                return False
        return True

    def complete(self, region, count):
        return self._ok(region)

    def accepts(self, mask):
        return self._ok(mask)

    def _ok(self, region):
        m = region & self.palmask
        while m:
            low = m & -m
            c = low.bit_length() - 1
            m ^= low
            if not any(not self.fence_nb[c][p] & region and not self.open_nb[c][p] & ~region
                       for p in self.allowed[c]):
                return False
        return True


def build(ctx):
    raw = ctx.puzzle.get("palisade")
    return PalisadeRule(ctx, _parse(raw)) if raw else None