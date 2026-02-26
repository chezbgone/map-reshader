from collections import deque
from dataclasses import dataclass
from datetime import timedelta
from itertools import pairwise
import time
from typing import Literal

import numpy as np
import z3
from z3 import If, Int, Or, Sum, unsat

from mapart import Coords, StaircasedMapArt


@dataclass
class PairwiseOptimizationInfo:
    total_hpairs: int
    original_eq_hpairs: int
    final_eq_hpairs: int
    time_taken: timedelta


type ScaffoldingKind = Literal["none", "minimal", "all"]


def optimize_monotonically_bright(
    mapart: StaircasedMapArt,
    scaffolding_kind: ScaffoldingKind = "none",
) -> PairwiseOptimizationInfo:
    if scaffolding_kind == "all":
        raise ValueError("'all' scaffolding_kind is not implemented")

    # ensure mapart is monotonic
    for z, (row_top, row_bot) in enumerate(pairwise(mapart.all_heights)):
        for x, (h_t, h_b) in enumerate(zip(row_top, row_bot)):
            if h_t is None or h_b is None:
                continue
            if h_t > h_b:
                raise ValueError(f"Mapart is not monotonic at {(x, z)}")

    all_horizontal_pairs = sum(
        1
        for row in mapart.all_heights
        for left, right in pairwise(row)
        if left is not None and right is not None
    )
    original_horizontal_equal_pairs = sum(
        1
        for row in mapart.all_heights
        for left, right in pairwise(row)
        if left is not None and right is not None and left == right
    )

    columns: list[tuple[int | None, ...]] = list(zip(*mapart.all_heights))

    time_start = time.monotonic()

    # find horizontal pairs to merge
    to_merge: list[tuple[Coords, Coords]] = []
    for x, (left, right) in enumerate(pairwise(columns)):
        opt = z3.Optimize()

        l_vars = []
        r_vars = []
        horizontal_pairs = []

        # create variables and horizontal pair conditions
        for z, (l, r) in enumerate(zip(left, right)):
            l_var = Int(f"l_{z}") if l is not None else None
            r_var = Int(f"r_{z}") if r is not None else None
            l_vars.append(l_var)
            r_vars.append(r_var)
            if l_var is not None:
                opt.add(l_var >= 0)
            if r_var is not None:
                opt.add(r_var >= 0)
            if l_var is not None and r_var is not None:
                condition = Or(l_var == r_var, l_var == 0, r_var == 0)
                horizontal_pairs.append(If(condition, 1, 0))

        # monotonicity constraints
        for z, (l, l_) in enumerate(pairwise(left)):
            if l is None or l_ is None:
                continue
            if l < l_:
                opt.add(l_vars[z] < l_vars[z + 1])
            elif l > l_:
                opt.add(l_vars[z] > l_vars[z + 1])
            else:
                opt.add(l_vars[z] == l_vars[z + 1])

        for z, (r, r_) in enumerate(pairwise(right)):
            if r is None or r_ is None:
                continue
            if r < r_:
                opt.add(r_vars[z] < r_vars[z + 1])
            elif r > r_:
                opt.add(r_vars[z] > r_vars[z + 1])
            else:
                opt.add(r_vars[z] == r_vars[z + 1])

        total_horizontal_pairs = Int("1:total_horizontal_pairs")
        opt.add(total_horizontal_pairs == Sum(horizontal_pairs))
        total_height = Int("2:total_height")
        non_none_vars = [l for l in l_vars if l is not None] + [
            r for r in r_vars if r is not None
        ]
        opt.add(total_height == Sum(non_none_vars))
        opt.maximize(total_horizontal_pairs)
        opt.minimize(total_height)

        if opt.check() == unsat:
            raise ValueError(f"Unsat at column pair {x}")
        model = opt.model()

        for z, (l, r, l_var, r_var) in enumerate(zip(left, right, l_vars, r_vars)):
            if l is None or r is None:
                continue
            model_l = model.evaluate(l_var).as_long()  # type: ignore
            model_r = model.evaluate(r_var).as_long()  # type: ignore
            if model_l == model_r:
                to_merge.append(((z, x), (z, x + 1)))

    # construct graph and perform merges with union-find
    # arr[y * size + x] corresponds to (x, y)
    size = mapart.size
    uf_parents = list(range(size * (size + 1)))
    uf_ranks = [0 for _ in range(size * (size + 1))]

    def id_of(z: int, x: int) -> int:
        return z * size + x

    def coords_of(id: int) -> Coords:
        return (id // size, id % size)

    def uf_find(id: int) -> int:
        if uf_parents[id] != id:
            uf_parents[id] = uf_find(uf_parents[id])
        return uf_parents[id]

    def uf_union(l: int, r: int) -> None:
        root_l = uf_find(l)
        root_r = uf_find(r)
        if root_l == root_r:
            return
        rank_l = uf_ranks[root_l]
        rank_r = uf_ranks[root_r]
        if rank_l < rank_r:
            uf_parents[root_l] = root_r
        elif rank_l > rank_r:
            uf_parents[root_r] = root_l
        else:
            uf_parents[root_r] = root_l
            uf_ranks[root_l] += 1

    # horizontal merges found from z3
    for (lz, lx), (rz, rx) in to_merge:
        uf_union(id_of(lz, lx), id_of(rz, rx))

    # vertical merges from original height map
    for x, column in enumerate(columns):
        for z, (top_height, bottom_height) in enumerate(pairwise(column)):
            if top_height is None or bottom_height is None:
                continue
            top_id = id_of(z, x)
            bottom_id = id_of(z + 1, x)
            if top_height == bottom_height:
                uf_union(top_id, bottom_id)

    # make adjacency list in preparation for topological sort
    parents = {uf_find(i) for i in range(size * (size + 1))}
    adj: dict[int, set[int]] = {parent: set() for parent in parents}
    # add vertical edges to enforce monotonic constraints
    for x, column in enumerate(columns):
        for z, (top_height, bottom_height) in enumerate(pairwise(column)):
            if top_height is None or bottom_height is None:
                continue
            top_id = id_of(z, x)
            bottom_id = id_of(z + 1, x)
            if top_height < bottom_height:
                adj[uf_find(top_id)].add(uf_find(bottom_id))
            elif top_height > bottom_height:
                adj[uf_find(bottom_id)].add(uf_find(top_id))

    # perform a topological sort to determine height assignments
    in_degree = {node: 0 for node in adj}
    for _, neighbors in adj.items():
        for neighbor in neighbors:
            in_degree[neighbor] += 1
    # initialize height of nodes with no incoming edges to 0
    # assign heights to other nodes based on longest path from these nodes
    queue = deque([node for node, degree in in_degree.items() if degree == 0])
    minimal_height = {node: 0 for node in parents}

    while queue:
        node = queue.popleft()
        for neighbor in adj[node]:
            minimal_height[neighbor] = max(
                minimal_height.get(neighbor, 0),
                minimal_height[node] + 1,
            )
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # assign heights back to mapart
    for x, cell in enumerate(mapart.padding_heights):
        if cell is None:
            continue
        mapart.padding_heights[x] = minimal_height[uf_find(id_of(0, x))]
    for z, row in enumerate(mapart.blocks, start=1):
        for x, block in enumerate(row):
            if block is None:
                continue
            block.height = minimal_height[uf_find(id_of(z, x))]

    final_horizontal_equal_pairs = sum(
        1
        for row in mapart.all_heights
        for left, right in pairwise(row)
        if left is not None and right is not None and left == right
    )

    # add scaffolding blocks
    # `scaffolding` is blocks to add scaffolding under
    scaffolding: set[tuple[int, int]] = set()
    if scaffolding_kind == "minimal":
        connected_unions = set()
        for z, (top_row, bottom_row) in enumerate(pairwise(mapart.all_heights)):
            for x, (top_height, bottom_height) in enumerate(zip(top_row, bottom_row)):
                if top_height is None or bottom_height is None:
                    continue
                if top_height + 1 != bottom_height:
                    # no scaffolding needed
                    continue
                if (uf_find(id_of(z, x)), uf_find(id_of(z + 1, x))) in connected_unions:
                    # scaffolding already exists
                    continue
                connected_unions.add((uf_find(id_of(z, x)), uf_find(id_of(z + 1, x))))
                scaffolding.add((x, z + 1))
    mapart.scaffolding = scaffolding

    time_end = time.monotonic()

    return PairwiseOptimizationInfo(
        total_hpairs=all_horizontal_pairs,
        original_eq_hpairs=original_horizontal_equal_pairs,
        final_eq_hpairs=final_horizontal_equal_pairs,
        time_taken=timedelta(seconds=time_end - time_start),
    )
