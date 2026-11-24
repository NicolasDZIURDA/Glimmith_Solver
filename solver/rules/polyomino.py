import json
from . import Rule
from ..shapes import get_shape_variants, get_shape_signature


def _parse(raw):
    """Renvoie une liste de (forme, [cases]) à partir de l'une des deux écritures :

        "polyomino": {"[[0,0],[0,1],[1,0]]": [[2,3], [4,5]]}
        "polyomino": [{"shape": [[0,0],[0,1],[1,0]], "cells": [[2,3], [4,5]]}]

    Une position seule ([2,3]) est acceptée à la place d'une liste de positions.
    """
    if isinstance(raw, dict):
        pairs = []
        for key, cells in raw.items():
            try:
                pairs.append((json.loads(key), cells))
            except json.JSONDecodeError:
                raise ValueError(
                    f"Clé de forme illisible : {key!r} (attendu : '[[0,0],[0,1]]')")
    elif isinstance(raw, list):
        try:
            pairs = [(item["shape"], item["cells"]) for item in raw]
        except (KeyError, TypeError):
            raise ValueError('Chaque entrée de "polyomino" doit avoir "shape" et "cells".')
    else:
        raise ValueError('"polyomino" doit être un objet ou une liste.')

    entries = []
    for shape, cells in pairs:
        shape = [tuple(cell) for cell in shape]
        if not shape or len(set(shape)) != len(shape):
            raise ValueError(f"Forme vide ou avec des cases en double : {shape}")
        if not _connected(shape):
            raise ValueError(f"Une forme doit être connexe : {shape}")
        if cells and isinstance(cells[0], int):          # une seule position
            cells = [cells]
        entries.append((shape, [tuple(cell) for cell in cells]))
    return entries


def _connected(shape):
    cells, todo, seen = set(shape), [shape[0]], {shape[0]}
    while todo:
        r, c = todo.pop()
        for nxt in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
            if nxt in cells and nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    return len(seen) == len(cells)


class PolyominoRule(Rule):
    """Une case donnée doit appartenir à une région qui a une forme donnée
    (rotations et miroirs autorisés, comme pour shape_bank).

    Cette règle contraint des régions sans les définir : elle se combine avec
    symbols, precision ou shape_bank."""

    #defines_regions = False

    def __init__(self, ctx, entries):
        self.ctx = ctx
        self.required = {}                  # case -> signature de la forme imposée
        self.constrained = 0
        for shape, cells in entries:
            sig = get_shape_signature(shape)
            for cell in cells:
                i = ctx.idx.get(cell)
                if i is None or not (ctx.valid_mask >> i & 1):
                    self.unsatisfiable = True          # case hors grille
                    continue
                if self.required.setdefault(i, sig) != sig:
                    self.unsatisfiable = True          # deux formes différentes pour une case
                self.constrained |= ctx.bit[i]
        self.preferred_cells = self.constrained     # peu de régions possibles : on commence par là
        self.clue_cells = self.constrained
        self._sig = {}
        self._placements = {}               # signature -> masques des placements possibles

    # --- outils ---------------------------------------------------------------
    def _signature(self, mask):
        sig = self._sig.get(mask)
        if sig is None:
            sig = get_shape_signature(
                [self.ctx.cells[i] for i in range(self.ctx.n) if mask >> i & 1])
            self._sig[mask] = sig
        return sig

    def _placements_of(self, sig):
        """Placements de la forme dans la grille, calculés au premier usage (après
        que les autres règles ont enregistré leurs conflits)."""
        found = self._placements.get(sig)
        if found is not None:
            return found
        ctx = self.ctx
        other = 0                           # cases imposées à une AUTRE forme
        for i, s in self.required.items():
            if s != sig:
                other |= ctx.bit[i]
        found = set()
        for variant in get_shape_variants(sig):
            sh = max(r for r, c in variant) + 1
            sw = max(c for r, c in variant) + 1
            for r0 in range(ctx.height - sh + 1):
                for c0 in range(ctx.width - sw + 1):
                    mask = 0
                    for r, c in variant:
                        mask |= ctx.bit[(r0 + r) * ctx.width + c0 + c]
                    if mask & ~ctx.valid_mask or mask & other:
                        continue
                    m, clash = mask, False
                    while m:
                        low = m & -m
                        if ctx.conflict[low.bit_length() - 1] & mask:
                            clash = True
                            break
                        m ^= low
                    if not clash:
                        found.add(mask)
        self._placements[sig] = found = list(found)
        return found

    # --- construction d'une région : state = (forme imposée ou None, masque) ----
    def start(self, i):
        return self.add((None, 0), i)

    def add(self, state, i):
        req, mask = state
        mask |= self.ctx.bit[i]
        need = self.required.get(i)
        if need is not None:
            if req is not None and req != need:
                return None                 # deux formes imposées dans la même région
            req = need
        return (req, mask), 0

    def closed(self, state, count):
        req = state[0]
        return req is not None and count >= len(req)

    def viable(self, state, count, reach):
        req, mask = state
        if req is None:
            return True
        r = reach()
        if r.bit_count() < len(req):
            return False
        # La région doit tenir dans un placement de la forme, lui-même atteignable.
        return any(not mask & ~p and not p & ~r for p in self._placements_of(req))

    def complete(self, state, count):
        req, mask = state
        return req is None or (count == len(req) and self._signature(mask) == req)

    # --- quand une autre règle fournit les régions (shape_bank) -----------------
    def accepts(self, mask):
        m = mask & self.constrained
        if not m:
            return True
        sig = self._signature(mask)
        while m:
            low = m & -m
            if self.required[low.bit_length() - 1] != sig:
                return False
            m ^= low
        return True


def build(ctx):
    raw = ctx.puzzle.get("polyomino")
    return PolyominoRule(ctx, _parse(raw)) if raw else None