from ._relation import RelationRule

def build(ctx):
    pairs = ctx.puzzle.get("gemini", [])
    return RelationRule(ctx, pairs, same=True) if pairs else None