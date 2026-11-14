def get_shape_variants(shape):
    """Retourne toutes les rotations et symétries normalisées."""

    transformations = [
        lambda r, c: (r, c),
        lambda r, c: (r, -c),
        lambda r, c: (-r, c),
        lambda r, c: (-r, -c),
        lambda r, c: (c, r),
        lambda r, c: (c, -r),
        lambda r, c: (-c, r),
        lambda r, c: (-c, -r),
    ]

    variants = set()

    for transform in transformations:
        transformed = [
            transform(r, c) for r, c in shape
        ]

        min_r = min(r for r, c in transformed)
        min_c = min(c for r, c in transformed)

        variant = tuple(sorted(
            (r - min_r, c - min_c)
            for r, c in transformed
        ))

        variants.add(variant)

    return variants


def get_shape_signature(region):
    """Retourne une signature indépendante des rotations et miroirs."""

    return min(get_shape_variants(region))