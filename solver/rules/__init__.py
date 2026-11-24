class Rule:
    unsatisfiable = False
    provides_candidates = False
    defines_regions = True
    preferred_cells = 0     # masque de cases très contraintes : le moteur commence par elles
    clue_cells = 0

    def start(self, i):                      return 0, 0
    def add(self, state, i):                 return state, 0
    def closed(self, state, count):          return False
    def viable(self, state, count, reach):   return True
    def complete(self, state, count):        return True
    def region_count(self, comp):            return None
    def candidates(self, u, comp):           raise NotImplementedError
    def accepts(self, mask):                 return True
    def region_ok(self, region, chosen):     return True
    def leftover_ok(self, state, leftover):  return True

    def info(self):
        """Chiffres à afficher dans le bilan (dict nom -> entier)."""
        return {}