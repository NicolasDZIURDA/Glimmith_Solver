class Rule:
    unsatisfiable = False     # True : le puzzle n'a aucune solution
    preferred_cells = 0     # masque de cases très contraintes : le moteur commence par elles

    def start(self, i):                      return 0, 0           # (état, cases interdites)
    def add(self, state, i):                 return state, 0       # ou None si interdit
    def closed(self, state, count):          return False          # la région ne doit plus grandir
    def viable(self, state, count, reach):   return True           # reach() : cases atteignables
    def complete(self, state, count):        return True           # la région est valide telle quelle
    def region_count(self, comp):            return None           # None, 0 (impossible) ou un entier

    def candidates(self, u, comp):           raise NotImplementedError
    def accepts(self, mask):                 return True

    def region_ok(self, region, chosen):     return True