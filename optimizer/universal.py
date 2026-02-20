from dataclasses import dataclass
from datetime import timedelta
from itertools import pairwise
import time

import z3
from z3 import If, Int, Or, Sum, sat

from mapart import ReifiedMapArt

@dataclass
class UniversalOptimizationInfo:
    total_hpairs: int
    original_eq_hpairs: int
    final_eq_hpairs: int
    time_taken: timedelta

def optimize(mapart: ReifiedMapArt) -> UniversalOptimizationInfo:
    unoptimized_horizontal_equal_pairs = sum(
        1
        for row in mapart.height_map
        for left, right in pairwise(row)
        if left is not None and
            right is not None and
            left == right
    )
    
    opt = z3.Optimize()
    opt.set('timeout', 10000)

    height_map_augmented = [
        [
            (Int(f"h_{i}_{j}"), cell) if cell is not None else None
            for i, cell in enumerate(row)
        ]
        for j, row in enumerate(mapart.height_map)
    ]
    for row in height_map_augmented:
        for cell in row:
            if cell is None:
                continue
            var, _ = cell
            opt.add(var >= 0)
    
    for column in zip(*height_map_augmented):
        for top, bottom in pairwise(column):
            if top is None or bottom is None:
                continue
            top_var, top_height = top
            bottom_var, bottom_height = bottom
            if top_height == bottom_height:
                opt.add(top_var == bottom_var)
            elif top_height < bottom_height:
                opt.add(top_var < bottom_var)
            else:
                opt.add(top_var > bottom_var)

    horizontal_equal_pairs = []
    for row in height_map_augmented:
        for left, right in pairwise(row):
            if left is not None and right is not None:
                left_var, _ = left
                right_var, _ = right
                condition = Or(left_var == right_var, left_var == 0, right_var == 0)
                horizontal_equal_pairs.append(If(condition, 1, 0))
    total_horizontal_equal_pairs = Int('total_horizontal_equal_pairs')
    opt.add(total_horizontal_equal_pairs == Sum(horizontal_equal_pairs))

    opt.maximize(total_horizontal_equal_pairs)
    all_heights = []
    for row in height_map_augmented:
        for cell in row:
            if cell is None:
                continue
            var, _ = cell
            all_heights.append(var)
    opt.minimize(Sum(all_heights))

    time_start = time.monotonic()
    if opt.check() != sat:
        raise ValueError("Optimization failed: no solution found")
    time_end = time.monotonic()

    model = opt.model()
    values: list[list[int | None]] = [
        [
            model.evaluate(cell[0]).as_long() if cell is not None else None # type: ignore
            for cell in row
        ]
        for row in height_map_augmented
    ]

    mapart.height_map = values
    final_horizontal_equal_pairs = sum(
        1
        for row in mapart.height_map
        for left, right in pairwise(row)
        if left is not None and
            right is not None and
            left == right
    )

    return UniversalOptimizationInfo(
        total_hpairs=len(horizontal_equal_pairs),
        original_eq_hpairs=unoptimized_horizontal_equal_pairs,
        final_eq_hpairs=final_horizontal_equal_pairs,
        time_taken=timedelta(seconds=time_end - time_start),
    )