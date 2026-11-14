def prepare_puzzle(puzzle):
    
    height = len(puzzle["grid"])
    width = len(puzzle["grid"][0])
    rules = {rule["type"] for rule in puzzle["rules"]}
    symbol_positions = {
        name: {tuple(pos) for pos in positions}
        for name, positions in (puzzle.get("symbols") or {}).items()
    }

    return height, width, rules, symbol_positions

def neighbors(cell, height, width, valid_cells, walls):
    """Retourne les voisins accessibles sans franchir de séparation."""
    r, c = cell

    for nr, nc in (
        (r - 1, c),
        (r + 1, c),
        (r, c - 1),
        (r, c + 1),
    ):
        if not (0 <= nr < height and 0 <= nc < width):
            continue

        neighbor = (nr, nc)

        if neighbor not in valid_cells:
            continue

        # Une séparation est indépendante du sens de parcours.
        edge = frozenset((cell, neighbor))

        if edge not in walls:
            yield neighbor
            
def crosses_wall(region, neighbor, walls):
    """Vérifie si l'ajout d'une case viole une séparation."""
    for wall in walls:
        a, b = tuple(wall)

        if (neighbor == a and b in region) or (
            neighbor == b and a in region
        ):
            return True

    return False

def validate_walls(wall_list, valid_cells):
    """Vérifie que les murs séparent bien deux cases adjacentes"""
    walls = set()
    
    for wall in wall_list or []:
        a, b = map(tuple, wall)

        if abs(a[0] - b[0]) + abs(a[1] - b[1]) != 1:
            raise ValueError(f"Séparation invalide : {wall}")

        if a not in valid_cells or b not in valid_cells:
            raise ValueError(f"Séparation hors grille ou sur une case absente : {wall}")

        walls.add(frozenset((a, b)))
        
    return walls