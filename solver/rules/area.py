from . import Rule

def _parse(raw):
    """Renvoie une liste de ((ligne, colonne), taille) à partir de l'une des deux écritures :

        "area": {"4": [[0,0], [2,3]], "7": [[5,5]]}      (taille -> positions)
        "area": [[0,0,4], [2,3,4], [5,5,7]]               (ligne, colonne, taille)

    Une position seule ([0,0]) est acceptée à la place d'une liste de positions.
    """
    pairs = []
    if isinstance(raw, dict):
        for key, cells in raw.items():
            try:
                size = int(key)
            except ValueError:
                raise ValueError(f'Clé d\'aire illisible : {key!r} (attendu : un nombre, par exemple "4")')
            if cells and isinstance(cells[0], int):
                cells = [cells]
            pairs += [(tuple(cell), size) for cell in cells]
    elif isinstance(raw, list):
        for item in raw:
            if not isinstance(item, (list, tuple)) or len(item) != 3:
                raise ValueError(f"Entrée d'aire mal formée : {item!r} (attendu : [ligne, colonne, taille])")
            pairs.append(((item[0], item[1]), item[2]))
    else:
        raise ValueError('"area" doit être un objet ou une liste.')
    for cell, size in pairs:
        if not isinstance(size, int) or isinstance(size, bool) or size < 1:
            raise ValueError(f"Taille d'aire invalide pour {cell} : {size!r} (attendu : un entier >= 1)")
    return pairs


class AreaRule(Rule):
    """Si une case contient un nombre, la région qui la contient a exactement ce nombre de cases.

    Combinée à symbols, precision ou shape_bank, elle ne fait que contraindre les régions ;
    seule, chaque région doit contenir au moins une case numérotée (voir rules/clue.py)."""

    defines_regions = False

    def __init__(self, ctx, pairs):
        self.required = {}                  # case -> taille imposée
        n_valid = ctx.valid_mask.bit_count()
        for cell, size in pairs:
            i = ctx.idx.get(cell)
            if i is None or not (ctx.valid_mask >> i & 1) or size > n_valid:
                self.unsatisfiable = True   # case hors grille, ou nombre plus grand que la grille
                continue
            if self.required.setdefault(i, size) != size:
                self.unsatisfiable = True   # deux nombres différents sur une même case
        bit = ctx.bit
        self.numbered = 0
        self.by_value = {}                  # taille -> masque des cases portant ce nombre
        for i, size in self.required.items():
            self.numbered |= bit[i]
            self.by_value[size] = self.by_value.get(size, 0) | bit[i]
        top = max(self.required.values(), default=0)
        # lt[s] : cases dont le nombre est < s (inutilisables par une région déjà de taille s)
        self.lt = [0] * (top + 2)
        for s in range(top + 2):
            for i, size in self.required.items():
                if size < s:
                    self.lt[s] |= bit[i]
        self.clue_cells = self.numbered
        self.preferred_cells = self.numbered    # peu de régions possibles : on commence par là

    # --- construction d'une région : state = (taille imposée ou 0, cases déjà prises) ---
    def start(self, i):
        return self.add((0, 0), i)

    def add(self, state, i):
        req, size = state
        size += 1
        need = self.required.get(i, 0)
        if need:
            if (req and req != need) or need < size:
                return None                 # deux nombres différents, ou région déjà trop grande
            req = need
        elif req and size > req:
            return None
        forbid = self.lt[min(size, len(self.lt) - 1)]
        if req:
            forbid |= self.numbered & ~self.by_value[req]       # un autre nombre : pas dans cette région
        return (req, size), forbid

    def closed(self, state, count):
        return bool(state[0]) and count >= state[0]

    def viable(self, state, count, reach):
        req = state[0]
        return not req or reach().bit_count() >= req

    def complete(self, state, count):
        return not state[0] or count == state[0]

    def region_count(self, comp):
        """Un groupe de cases plus petit qu'un des nombres qu'il contient est impossible."""
        m = comp & self.numbered
        if not m:
            return None
        size = comp.bit_count()
        for s, mask in self.by_value.items():
            if s > size and mask & m:
                return 0
        return None

    # --- quand une autre règle fournit les régions (shape_bank) -----------------
    def accepts(self, mask):
        m = mask & self.numbered
        if not m:
            return True
        size = mask.bit_count()
        return all(not mask & v or s == size for s, v in self.by_value.items())


def build(ctx):
    raw = ctx.puzzle.get("area")
    return AreaRule(ctx, _parse(raw)) if raw else None