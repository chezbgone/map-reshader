from collections import deque
from dataclasses import dataclass
from datetime import timedelta
from itertools import pairwise
import time
from typing import Literal

from mapart import ReifiedMapArt

@dataclass
class PairwiseOptimizationInfo:
    total_hpairs: int
    original_eq_hpairs: int
    final_eq_hpairs: int
    time_taken: timedelta

def optimize_monotonic(mapart: ReifiedMapArt) -> PairwiseOptimizationInfo:
    # ensure mapart is monotonic
    raw_columns: list[tuple[int | None]] = list(zip(*mapart.height_map))
    for j, column in enumerate(raw_columns):
        for (i, h), (_, h_) in pairwise(enumerate(column)):
            if h is None or h_ is None:
                continue
            if h > h_:
                raise ValueError(f"Mapart is not monotonic at {(i, j)}")

    all_horizontal_pairs = sum(
        1
        for row in mapart.height_map
        for left, right in pairwise(row)
        if left is not None and
            right is not None
    )
    original_horizontal_equal_pairs = sum(
        1
        for row in mapart.height_map
        for left, right in pairwise(row)
        if left is not None and
            right is not None and
            left == right
    )

    columns: list[tuple[int | None]] = list(zip(*mapart.height_map))

    time_start = time.monotonic()

    # find horizontal pairs to merge
    to_merge: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for x, (left, right) in enumerate(pairwise(columns)):
        pass

    # construct graph and perform merges with union-find
    # arr[y * size + x] corresponds to (x, y)
    size = mapart.SIZE
    uf_parents = list(range(size * (size + 1)))
    uf_ranks = [0 for _ in range(size * (size + 1))]

    def id_of(y: int, x: int) -> int:
        return y * size + x
    def coords_of(id: int) -> tuple[int, int]:
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
    for (ly, lx), (ry, rx) in to_merge:
        uf_union(id_of(ly, lx), id_of(ry, rx))

    # vertical merges from original height map
    for x, column in enumerate(columns):
        for y, (top, bottom) in enumerate(pairwise(column)):
            if top is None or bottom is None:
                continue
            top_id = id_of(y, x)
            bottom_id = id_of(y + 1, x)
            if top == bottom:
                uf_union(top_id, bottom_id)

    # make adjacency list in preparation for topological sort
    parents = {uf_find(i) for i in range(size * (size + 1))}
    adj: dict[int, set[int]] = {
        parent: set()
        for parent in parents
    }
    # add vertical edges to enforce monotonic constraints
    for x, column in enumerate(columns):
        for y, (top, bottom) in enumerate(pairwise(column)):
            if top is None or bottom is None:
                continue
            top_id = id_of(y, x)
            bottom_id = id_of(y + 1, x)
            if top < bottom:
                adj[uf_find(top_id)].add(uf_find(bottom_id))
            elif top > bottom:
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
    mapart.height_map = [
        [
            None if cell is None else minimal_height[uf_find(id_of(y, x))]
            for x, cell in enumerate(row)
        ]
        for y, row in enumerate(mapart.height_map)
    ]
    final_horizontal_equal_pairs = sum(
        1
        for row in mapart.height_map
        for left, right in pairwise(row)
        if left is not None and
            right is not None and
            left == right
    )

    time_end = time.monotonic()
    
    return PairwiseOptimizationInfo(
        total_hpairs=all_horizontal_pairs,
        original_eq_hpairs=original_horizontal_equal_pairs,
        final_eq_hpairs=final_horizontal_equal_pairs,
        time_taken=timedelta(seconds=time_end - time_start),
    )