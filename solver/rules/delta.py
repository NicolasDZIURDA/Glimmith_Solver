from ._relation import RelationRule

def build(ctx):
    pairs = ctx.puzzle.get("delta", [])
    return RelationRule(ctx, pairs, same=False) if pairs else None