from . import Rule

class ClueRule(Rule):
    """Ajoutée automatiquement par le moteur quand les seules règles actives sont des règles à
    indications (area, polyomino) : rien d'autre ne dit à quoi ressemblent les régions, donc
    chaque région doit contenir au moins une case indiquée."""

    def __init__(self, clues):
        self.clues = clues

    def start(self, i):
        return self.add(0, i)

    def add(self, has, i):
        return (1 if has or self.clues >> i & 1 else 0), 0

    def viable(self, has, count, reach):
        return bool(has) or bool(reach() & self.clues)

    def complete(self, has, count):
        return bool(has)

    def accepts(self, mask):
        return bool(mask & self.clues)

    def region_count(self, comp):
        return None if comp & self.clues else 0         # un groupe sans indication est impossible