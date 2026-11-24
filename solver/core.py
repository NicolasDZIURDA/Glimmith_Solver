"""Moteur commun : il ne connaît AUCUNE règle, il appelle leurs hooks."""
from collections import defaultdict
from types import SimpleNamespace
from solver.rules import Rule, symbols, gemini, delta, shape_bank, precision, polyomino, mingle_shape, area
from puzzle_utils import prepare_puzzle
import time

REGISTRY = {
    "symbols": symbols.build,
    "gemini": gemini.build,
    "delta": delta.build,
    "shape_bank": shape_bank.build,
    "precision": precision.build,
    "polyomino": polyomino.build,
    "mingle_shape": mingle_shape.build,
    "area": area.build,
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


class _Stop(Exception):
    """Interne : arrêt demandé par le chronomètre."""


def _fmt(n):
    return f"{n:,}".replace(",", " ")


def solve_puzzle(puzzle, valid, walls, neighbors, max_solutions,
                 time_limit=None, verbose=False, stats=None, progress_every=2.0):
    """Renvoie la liste des solutions trouvées (au plus `max_solutions`).

    time_limit     secondes avant arrêt (None : pas de limite). À l'arrêt, on renvoie les
                   solutions déjà trouvées ; `stats["timed_out"]` vaut alors True.
    verbose        affiche la progression (toutes les `progress_every` s) et un bilan.
    stats          dict optionnel, rempli avec : seconds, timed_out, interrupted, solutions,
                   search_nodes, growth_steps, generated, explored.
    Ctrl+C arrête aussi proprement la recherche (stats["interrupted"]).
    """
    if stats is None:
        stats = {}
    stats.update(seconds=0.0, timed_out=False, interrupted=False, solutions=0,
                 search_nodes=0, growth_steps=0, generated=0, explored=0)
    start = time.perf_counter()

    ctx = build_context(puzzle, valid, walls, neighbors)

    unknown = ctx.rule_types - set(REGISTRY)
    if unknown:
        raise ValueError(f"Règles sans module : {sorted(unknown)}")
    rules = [r for t in sorted(ctx.rule_types) if (r := REGISTRY[t](ctx)) is not None]
    if not rules or any(r.unsatisfiable for r in rules):
        return []
    if not any(r.defines_regions for r in rules) and not any(r.clue_cells for r in rules):
        raise ValueError(
            "Les règles " + ", ".join(sorted(ctx.rule_types)) + " contraignent des régions "
            "mais n'en définissent pas : ajoute symbols, precision, shape_bank, area ou polyomino.")
    # Sinon, seules des règles à indications (area, polyomino) : une région sans indication est libre.
    # Garde-fou : une règle qui ne surcharge aucune méthode de Rule ne contraint rien, et le
    # moteur renverrait des résultats faux sans le dire (par exemple une région unique).
    hooks = ("start", "add", "closed", "viable", "complete", "accepts",
             "region_ok", "region_count", "candidates")
    for r in rules:
        if not any(getattr(type(r), h) is not getattr(Rule, h) for h in hooks):
            raise ValueError(
                f"La règle {type(r).__name__} ne surcharge aucune méthode de Rule "
                f"({', '.join(hooks)}) : elle ne contraindrait rien. "
                "Vérifie le nom et le fichier de ses méthodes.")
    sources = [r for r in rules if r.provides_candidates]
    if len(sources) > 1:
        raise ValueError("Une seule règle peut fournir les régions candidates.")
    source = sources[0] if sources else None

    def overriding(name):
        base = getattr(Rule, name)
        return [(j, r) for j, r in enumerate(rules) if getattr(type(r), name) is not base]
    closers, viabler = overriding("closed"), overriding("viable")
    completers, adders = overriding("complete"), overriding("add")
    acceptors = [r for _, r in overriding("accepts") if r is not source]
    relaters = [r for _, r in overriding("region_ok")]
    lefters = overriding("leftover_ok")

    n, bit, conflict, expand, flood = ctx.n, ctx.bit, ctx.conflict, ctx.expand, ctx.flood
    NB = [sum(bit[j] for j in ctx.adj[i]) for i in range(n)]
    preferred = 0
    for r in rules:
        preferred |= r.preferred_cells

    # --- chronomètre et compteurs ------------------------------------------------
    # cnt = [nœuds de recherche, pas de croissance, régions générées, régions explorées]
    cnt = [0, 0, 0, 0]
    solutions = []
    deadline = None if time_limit is None else start + time_limit
    next_report = [start + progress_every]

    def report(elapsed):
        print(f"  [{elapsed:6.1f} s] nœuds {_fmt(cnt[0])} | pas de croissance {_fmt(cnt[1])} | "
              f"régions générées {_fmt(cnt[2])} | explorées {_fmt(cnt[3])} | "
              f"solutions {len(solutions)}", flush=True)

    def tick():
        """Appelé à chaque pas de construction ; vérifie l'heure tous les 4096 pas."""
        cnt[1] += 1
        if cnt[1] & 4095:
            return
        now = time.perf_counter()
        if deadline is not None and now >= deadline:
            raise _Stop
        if verbose and now >= next_report[0]:
            report(now - start)
            next_report[0] = now + progress_every

    def components(rem):
        out = []
        while rem:
            c = flood(rem & -rem, rem)
            out.append(c)
            rem &= ~c
        return out

    def component_ok(comp):
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
        if source is not None:
            for mask in source.candidates(u, comp):
                tick()
                if all(r.accepts(mask) for r in acceptors):
                    yield mask
            return
        forbidden = ~comp | conflict[u]
        states = []
        for r in rules:
            s, f = r.start(u)
            states.append(s)
            forbidden |= f

        def rec(region, forbidden, states, count):
            tick()
            for j, r in closers:
                if r.closed(states[j], count):
                    if all(c.complete(states[jj], count) for jj, c in completers):
                        yield region
                    return

            cache = []
            def reach():
                if not cache:
                    cache.append(flood(region, ~forbidden | region))
                return cache[0]
            for j, r in viabler:
                if not r.viable(states[j], count, reach):
                    return

            if pockets:
                # Les cases que la région ne pourra plus jamais atteindre resteront en dehors.
                # Si un groupe de ces cases n'est voisin d'aucune case encore incertaine, il est
                # déjà « scellé » : il formera une composante à lui seul et doit être valide.
                rch = reach()
                outside = comp & ~rch
                while outside:
                    q = flood(outside & -outside, outside)
                    outside &= ~q
                    if not (expand(q) & rch & ~region) and not component_ok(q):
                        return

            if lefters:
                # Ce qui n'est pas dans la région forme déjà des groupes de cases ; certaines
                # règles savent dire qu'un tel groupe est perdu quoi que la région devienne.
                left = comp & ~region
                while left:
                    q = flood(left & -left, left)
                    left &= ~q
                    for j, r in lefters:
                        if not r.leftover_ok(states[j], q):
                            return

            frontier = expand(region) & ~region & ~forbidden
            if not frontier:
                if all(c.complete(states[jj], count) for jj, c in completers):
                    yield region
                return

            v = frontier & -frontier
            i = v.bit_length() - 1

            f2, new_states = forbidden | conflict[i], list(states)
            for j, r in adders:
                res = r.add(states[j], i)
                if res is None:
                    break
                new_states[j] = res[0]
                f2 |= res[1]
            else:
                yield from rec(region | v, f2, new_states, count + 1)

            yield from rec(region, forbidden | v, states, count)

        yield from rec(bit[u], forbidden, states, 1)

    # L'élagage « poches scellées » n'a de sens que si une règle sait dire si un groupe de
    # cases peut être découpé en régions valides (region_count).
    pockets = any(type(r).region_count is not Rule.region_count for r in rules)
    dead = set()
    # Le cache « état sans solution » n'est valable que si la validité d'une région
    # ne dépend pas des régions déjà choisies (ce qu'introduisent gemini/delta/mingle_shape).
    memo = not relaters

    def search(rem, chosen):
        cnt[0] += 1
        if not rem:
            solutions.append([frozenset(ctx.cells[i] for i in range(n) if m >> i & 1)
                              for m in chosen])
            return True
        if memo and rem in dead:
            return False

        comps = components(rem)
        comp = min([c for c in comps if c & preferred] or comps, key=lambda c: c.bit_count())
        best, u, m = 99, None, comp & preferred or comp     # cases contraintes d'abord
        while m:
            low = m & -m
            i = low.bit_length() - 1
            m ^= low
            deg = (NB[i] & comp).bit_count()
            if deg < best:
                best, u = deg, i

        found = False
        for region in regions_containing(u, comp):
            cnt[2] += 1
            new_rem = rem & ~region
            if (all(r.region_ok(region, chosen) for r in relaters)
                    and all(component_ok(c) for c in components(new_rem))):
                cnt[3] += 1
                found |= search(new_rem, chosen + [region])
                if len(solutions) >= max_solutions:
                    return True
        if memo and not found:
            dead.add(rem)
        return found

    try:
        if all(component_ok(c) for c in components(ctx.valid_mask)):
            search(ctx.valid_mask, [])
    except _Stop:
        stats["timed_out"] = True
    except KeyboardInterrupt:
        stats["interrupted"] = True
    finally:
        elapsed = time.perf_counter() - start
        stats.update(seconds=elapsed, solutions=len(solutions), search_nodes=cnt[0],
                     growth_steps=cnt[1], generated=cnt[2], explored=cnt[3])
        if verbose:
            if stats["timed_out"]:
                status = f"ARRÊT : limite de {time_limit} s atteinte"
            elif stats["interrupted"]:
                status = "ARRÊT : interrompu (Ctrl+C)"
            else:
                status = "Recherche terminée"
            print(f"  {status} après {elapsed:.1f} s | nœuds {_fmt(cnt[0])} | "
                  f"pas de croissance {_fmt(cnt[1])} | régions générées {_fmt(cnt[2])} | "
                  f"explorées {_fmt(cnt[3])} | solutions {len(solutions)}", flush=True)
            for r in rules:
                for key, value in r.info().items():
                    print(f"  {type(r).__name__} : {key} = {_fmt(value)}", flush=True)
    return solutions