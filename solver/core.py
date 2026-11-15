"""Moteur commun : il ne connaît AUCUNE règle, il appelle leurs hooks."""
from collections import defaultdict
from types import SimpleNamespace
from solver.rules import Rule, symbols, gemini, delta, shape_bank, precision, polyomino, mingle_shape
from puzzle_utils import prepare_puzzle

REGISTRY = {
    "symbols": symbols.build,
    "gemini": gemini.build,
    "delta": delta.build,
    "shape_bank": shape_bank.build,
    "precision": precision.build,
    "polyomino": polyomino.build,
    "mingle_shape": mingle_shape.build,
}


def build_context(puzzle, valid, walls, neighbors):
    height, width, rule_types, symbol_positions = prepare_puzzle(puzzle)
    n = height * width
    bit = [1 << i for i in range(n)]
    cells = [(r, c) for r in range(height) for c in range(width)]
    idx = {cell: i for i, cell in enumerate(cells)}

    adj = [() if cell not in valid else tuple(
        idx[x] for x in neighbors(cell, height, width, valid, walls)) for cell in cells]

    # Un mur sépare deux cases : elles ne peuvent pas être dans la même région.
    conflict = [0] * n
    for wall in walls:
        a, b = tuple(wall)
        conflict[idx[a]] |= bit[idx[b]]
        conflict[idx[b]] |= bit[idx[a]]

    # Préparation des bitmasks pour identifier les cases compatibles à un déplacement dans chacune des quatre directions
    shifts = defaultdict(int)
    for i, nbrs in enumerate(adj):
        for j in nbrs:
            shifts[j - i] |= bit[i]
    shift_list = list(shifts.items())

    def expand(f):
        out = 0
        for d, m in shift_list:
            x = f & m
            out |= (x << d) if d > 0 else (x >> -d)
        return out

    def flood(start, allowed):
        reached = frontier = start
        while frontier:
            frontier = expand(frontier) & allowed & ~reached
            reached |= frontier
        return reached

    return SimpleNamespace(
        puzzle=puzzle, height=height, width=width, rule_types=rule_types,
        symbol_positions=symbol_positions, n=n, bit=bit, cells=cells, idx=idx,
        adj=adj, conflict=conflict, expand=expand, flood=flood,
        valid_mask=sum(bit[idx[c]] for c in valid))


def solve_puzzle(puzzle, valid, walls, neighbors, max_solutions=2):
    ctx = build_context(puzzle, valid, walls, neighbors)

    unknown = ctx.rule_types - set(REGISTRY)
    if unknown:
        raise ValueError(f"Règles sans module : {sorted(unknown)}")
    rules = [r for t in sorted(ctx.rule_types) if (r := REGISTRY[t](ctx)) is not None]
    if not rules or any(r.unsatisfiable for r in rules):
        return []
    sources = [
        r for r in rules
        if type(r).candidates is not Rule.candidates
    ]

    def overriding(name):
        base = getattr(Rule, name)
        return [(j, r) for j, r in enumerate(rules) if getattr(type(r), name) is not base]
    closers, viabler = overriding("closed"), overriding("viable")
    completers, adders = overriding("complete"), overriding("add")
    #acceptors = [r for _, r in overriding("accepts") if r is not source]
    relaters = [r for _, r in overriding("region_ok")]

    n, bit, conflict, expand, flood = ctx.n, ctx.bit, ctx.conflict, ctx.expand, ctx.flood
    NB = [sum(bit[j] for j in ctx.adj[i]) for i in range(n)]

    def components(rem):
        out = []
        while rem:
            c = flood(rem & -rem, rem)
            out.append(c)
            rem &= ~c
        return out

    def component_ok(comp):
        """Les règles doivent s'accorder sur le nombre de régions de la composante."""
        want = None
        for r in rules:
            c = r.region_count(comp)
            if c is None:
                continue
            if c == 0 or (want is not None and c != want):
                return False
            want = c
        return True

    def regions_containing(u, comp):
        if sources:
            # Générer les candidats de chaque règle.
            candidates = set(sources[0].candidates(u, comp))

            # Ne conserver que les candidats communs.
            for r in sources[1:]:
                candidates.intersection_update(r.candidates(u, comp))

            # Vérifier les éventuelles autres contraintes.
            for mask in candidates:
                if all(r.accepts(mask) for r in rules):
                    yield mask

            return
        forbidden = ~comp | conflict[u]
        states = []
        for r in rules:
            s, f = r.start(u)
            states.append(s)
            forbidden |= f

        def rec(region, forbidden, states, count):
            for j, r in closers:
                if r.closed(states[j], count):
                    if all(c.complete(states[jj], count) for jj, c in completers):
                        yield region
                    return

            if viabler:
                cache = []
                def reach():
                    if not cache:
                        cache.append(flood(region, ~forbidden | region))
                    return cache[0]
                for j, r in viabler:
                    if not r.viable(states[j], count, reach):
                        return

            frontier = expand(region) & ~region & ~forbidden
            if not frontier:
                if all(c.complete(states[jj], count) for jj, c in completers):
                    yield region
                return

            v = frontier & -frontier
            i = v.bit_length() - 1

            # Branche 1 : v est dans la région.
            f2, new_states = forbidden | conflict[i], list(states)
            for j, r in adders:
                res = r.add(states[j], i)
                if res is None:
                    break
                new_states[j] = res[0]
                f2 |= res[1]
            else:
                yield from rec(region | v, f2, new_states, count + 1)

            # Branche 2 : v est exclue pour la suite.
            yield from rec(region, forbidden | v, states, count)

        yield from rec(bit[u], forbidden, states, 1)

    solutions, dead = [], set()
    # Le cache « état sans solution » n'est valable que si la validité d'une région
    # ne dépend pas des régions déjà choisies (ce qu'introduisent gemini/delta).
    memo = not relaters

    def search(rem, chosen):
        if not rem:
            solutions.append([frozenset(ctx.cells[i] for i in range(n) if m >> i & 1)
                              for m in chosen])
            return True
        if memo and rem in dead:
            return False

        comp = min(components(rem), key=lambda c: c.bit_count())
        best, u, m = 99, None, comp
        while m:                         # case de départ la plus contrainte
            low = m & -m
            i = low.bit_length() - 1
            m ^= low
            deg = (NB[i] & comp).bit_count()
            if deg < best:
                best, u = deg, i

        found = False
        for region in regions_containing(u, comp):
            new_rem = rem & ~region
            if (all(r.region_ok(region, chosen) for r in relaters)
                    and all(component_ok(c) for c in components(new_rem))):
                found |= search(new_rem, chosen + [region])
                if len(solutions) >= max_solutions:
                    return True
        if memo and not found:
            dead.add(rem)
        return found

    if all(component_ok(c) for c in components(ctx.valid_mask)):
        search(ctx.valid_mask, [])
    return solutions