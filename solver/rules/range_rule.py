from . import Rule


def _bounds(rules):
    """Lit les paramètres des règles de type range et renvoie (minimum, maximum).

    Chaque règle accepte, au choix ou ensemble :
        "minimum": 3            au moins 3 cases
        "maximum": 6            au plus 6 cases
        "range": [3, 6]         entre 3 et 6 cases
    Plusieurs règles range se cumulent. `maximum` vaut None quand il n'y a pas de limite haute.
    """
    low, high, found = 1, None, False
    for rule in rules:
        if rule.get("type") != "range":
            continue
        unknown = set(rule) - {"type", "minimum", "maximum", "range"}
        if unknown:
            raise ValueError(f"Paramètre inconnu pour range : {sorted(unknown)} "
                             '(attendu : "minimum", "maximum" ou "range")')
        if not {"minimum", "maximum", "range"} & set(rule):
            raise ValueError('range demande "minimum", "maximum" ou "range"')
        found = True
        if "minimum" in rule:
            low = max(low, _size(rule["minimum"], "minimum"))
        if "maximum" in rule:
            value = _size(rule["maximum"], "maximum")
            high = value if high is None else min(high, value)
        if "range" in rule:
            pair = rule["range"]
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise ValueError(f'"range" doit être une paire [minimum, maximum] : {pair!r}')
            a, b = _size(pair[0], "range"), _size(pair[1], "range")
            if a > b:
                raise ValueError(f'"range" : le minimum ({a}) dépasse le maximum ({b})')
            low = max(low, a)
            high = b if high is None else min(high, b)
    if not found:
        return None
    if high is not None and low > high:
        raise ValueError(f"range : le minimum ({low}) dépasse le maximum ({high})")
    return low, high


def _size(value, name):
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f'"{name}" doit être un entier >= 1 : {value!r}')
    return value


class RangeRule(Rule):
    """Chaque région a une taille comprise entre un minimum et un maximum.

    Seule, elle laisse les régions libres dans cette plage ; elle se combine avec toutes les
    autres règles."""

    defines_regions = True

    def __init__(self, ctx, low, high):
        self.low, self.high = low, high
        if low > ctx.valid_mask.bit_count():
            self.unsatisfiable = True               # aucune région ne peut être aussi grande

    def closed(self, state, count):
        return self.high is not None and count >= self.high

    def viable(self, state, count, reach):
        return self.low <= 1 or reach().bit_count() >= self.low

    def complete(self, state, count):
        return count >= self.low

    def accepts(self, mask):
        size = mask.bit_count()
        return size >= self.low and (self.high is None or size <= self.high)

    def region_count(self, comp):
        """Un groupe de cases doit pouvoir se découper en k régions, avec k*minimum <= taille <= k*maximum."""
        size = comp.bit_count()
        if self.high is None:
            return None if size >= self.low else 0
        fewest = -(-size // self.high)                  # plus petit nombre de régions possible
        return None if fewest * self.low <= size else 0


def build(ctx):
    bounds = _bounds(ctx.puzzle["rules"])
    return RangeRule(ctx, *bounds) if bounds else None