import string
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.collections import LineCollection
from pathlib import Path

def display_solution(puzzle, solution):
    """Affiche les régions dans le terminal et crée solution.png."""
    grid = [list(row) for row in puzzle["grid"]]
    height = len(grid)
    width = len(grid[0])

    fig, ax = plt.subplots(figsize=(width, height))
    cmap = plt.colormaps["tab20"]
    
    valid_cells = {
    (r, c)
    for r in range(height)
    for c in range(width)
    if grid[r][c] == "."
    }

    contours = []

    for r, c in valid_cells:
        # Bord supérieur
        if (r - 1, c) not in valid_cells:
            contours.append([(c, height - r), (c + 1, height - r)])

        # Bord inférieur
        if (r + 1, c) not in valid_cells:
            contours.append([
                (c, height - 1 - r),
                (c + 1, height - 1 - r)
            ])

        # Bord gauche
        if (r, c - 1) not in valid_cells:
            contours.append([
                (c, height - 1 - r),
                (c, height - r)
            ])

        # Bord droit
        if (r, c + 1) not in valid_cells:
            contours.append([
                (c + 1, height - 1 - r),
                (c + 1, height - r)
            ])

    ax.add_collection(
        LineCollection(contours, colors="black", linewidths=4)
    )

    walls = {
        frozenset((tuple(a), tuple(b)))
        for a, b in (puzzle.get("walls", []) or [])
    }
    
    for index, region in enumerate(solution):

        for r, c in region:
            ax.add_patch(Rectangle(
                (c, height - 1 - r),
                1, 1,
                facecolor=cmap(index % 20),
                edgecolor="black",
                linewidth=1,
            ))

    for r in range(height):
        for c in range(width):
            if grid[r][c] == "#":
                x = c
                y = height - 1 - r

                ax.add_patch(Rectangle(
                    (x, y),
                    1, 1,
                    facecolor="lightgray",
                    edgecolor="black",
                ))

                # Croix dans la case
                ax.plot(
                    [x, x + 1],
                    [y, y + 1],
                    color="black",
                    linewidth=1.5
                )

                ax.plot(
                    [x, x + 1],
                    [y + 1, y],
                    color="black",
                    linewidth=1.5
                )
                
    for wall in walls:
        a, b = tuple(wall)
        r1, c1 = a
        r2, c2 = b

        if r1 == r2:
            # Séparation verticale entre deux colonnes.
            x = max(c1, c2)
            y = height - 1 - r1
            ax.plot(
                [x, x], [y, y + 1],
                color="black", linewidth=4,
                solid_capstyle="butt",
            )
        else:
            # Séparation horizontale entre deux lignes.
            x = c1
            y = height - max(r1, r2)
            ax.plot(
                [x, x + 1], [y, y],
                color="black", linewidth=4,
                solid_capstyle="butt",
            )
    
    draw_special_walls(ax, puzzle)
            
    symbols = puzzle.get("symbols") or {}
    symbol_chars = {
        "red": "R",
        "blue": "B",
        "yellow": "Y",
        "green": "G",
        "purple": "P"
    }
            
    for symbol_type, positions in symbols.items():
        char = symbol_chars.get(symbol_type, "?")

        for r, c in positions:
            ax.text(
                c + 0.5,
                height - r - 0.5,
                char,
                ha="center",
                va="center",
                fontsize=16,
                fontweight="bold"
            )
            
    # Affichage des polyominos imposés
    for rule in puzzle.get("polyomino", []):
        shape = rule["shape"]

        for cell in rule["cells"]:
            draw_polyomino(
                ax,
                tuple(cell),
                shape,
                height
            )

    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.set_aspect("equal")
    ax.axis("off")
    
    Path("solutions").mkdir(parents=True, exist_ok=True)

    plt.savefig(
        f"./solutions/solution_{puzzle.get('name', 'sans_nom')}.png",
        dpi=200,
        bbox_inches="tight",
        pad_inches=0
    )
    plt.close(fig)
    
def draw_special_walls(ax, puzzle):
    height = len(puzzle["grid"])
    active_rules = {rule["type"] for rule in puzzle["rules"]}

    symbols = {
        "gemini": "♊",
        "delta": "δ",
    }

    for rule_type, symbol in symbols.items():
        if rule_type not in active_rules:
            continue

        # Style selon le type de mur
        if rule_type == "gemini":
            text_color = "black"
            background_color = "white"
        else:
            text_color = "white"
            background_color = "black"

        for wall in puzzle.get(rule_type, []):
            (r1, c1), (r2, c2) = wall

            x = (c1 + c2) / 2 + 0.5
            y = height - ((r1 + r2) / 2 + 0.5)

            ax.text(
                x,
                y,
                symbol,
                ha="center",
                va="center",
                fontsize=9,
                color=text_color,
                fontweight="bold",
                bbox=dict(
                    facecolor=background_color,
                    edgecolor="black",
                    linewidth=2,
                    boxstyle="square,pad=0.5"
                ),
                zorder=10
            )

            if r1 == r2:
                # Mur vertical
                ax.plot(
                    [x, x],
                    [y - 0.5, y + 0.5],
                    color="black",
                    linewidth=4,
                    solid_capstyle="butt",
                    zorder=9
                )
            else:
                # Mur horizontal
                ax.plot(
                    [x - 0.5, x + 0.5],
                    [y, y],
                    color="black",
                    linewidth=4,
                    solid_capstyle="butt",
                    zorder=9
                )

def draw_polyomino(ax, cell, shape, height, color="black"):
    r, c = cell

    x0 = c
    y0 = height - 1 - r

    max_r = max(p[0] for p in shape) + 1
    max_c = max(p[1] for p in shape) + 1

    # Taille maximale pour conserver une marge dans la cellule
    scale = min(0.6 / max_c, 0.6 / max_r)

    shape_width = max_c * scale
    shape_height = max_r * scale

    offset_x = x0 + (1 - shape_width) / 2
    offset_y = y0 + (1 - shape_height) / 2

    for sr, sc in shape:
        ax.add_patch(Rectangle(
        (
            offset_x + sc * scale,
            offset_y + (max_r - 1 - sr) * scale
        ),
        scale,
        scale,
        facecolor="white",
        edgecolor="black",
        linewidth=0.5,
        zorder=5
    ))