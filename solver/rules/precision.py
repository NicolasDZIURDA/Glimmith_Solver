from . import Rule

class PrecisionRule(Rule):
    """Chaque région a exactement `value` cases."""

    def __init__(self, size):
        if size < 1:
            raise ValueError("La taille des régions doit être positive.")
        self.size = size

    def closed(self, state, count):
        return count >= self.size

    def viable(self, state, count, reach):
        return reach().bit_count() >= self.size

    def complete(self, state, count):
        return count == self.size

    def accepts(self, mask):
        return mask.bit_count() == self.size

    def region_count(self, comp):
        cnt = comp.bit_count()
        return cnt // self.size if cnt % self.size == 0 else 0


def build(ctx):
    size = next((r["value"] for r in ctx.puzzle["rules"] if r["type"] == "precision"), None)
    return None if size is None else PrecisionRule(size)