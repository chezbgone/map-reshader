from typing import TypedDict

from collections import defaultdict
from enum import Enum
from itertools import chain, pairwise

from litemapy import Schematic, Region, BlockState
from nbtlib import Compound

import NBT
from mapart.reified import ReifiedMapArt, Block, Coords


class Staircasing(Enum):
    FLAT = 1
    UP = 2
    DOWN = 3
    BOTH = 4


class StaircasedMapArtMeta(TypedDict, total=False):
    staircasing: Staircasing
    platforms: set[frozenset[Coords]]


class StaircasedMapArt(ReifiedMapArt):
    blocks: list[list[Block | None]]
    padding_heights: list[int | None]
    scaffolding: set[Coords]
    meta: StaircasedMapArtMeta

    @property
    def all_heights(self) -> list[list[int | None]]:
        """
        returns all heights including the padding row
        """
        return [
            self.padding_heights,
            *(
                [block.height if block is not None else None for block in row]
                for row in self.blocks
            ),
        ]

    @classmethod
    def from_nbt_file(cls, schem: Compound, size: int = 128) -> StaircasedMapArt:
        # list of blocks without air
        block_list = [
            (coords, block_name)
            for (coords, block_name) in NBT.get_blocks(schem)
            if block_name != "minecraft:air"
        ]

        _blocks: list[list[Block | None]] = [
            [None for _ in range(size)] for _ in range(size)
        ]
        _padding_heights: list[int | None] = [None for _ in range(size)]

        for (x, y, z), block_name in block_list:
            if not (0 <= x < size and 0 <= z < size + 1):
                raise ValueError(f"Block position out of mapart bounds: {(x, y, z)}")
            if z == 0:
                _padding_heights[x] = int(y)
                continue
            if _blocks[z - 1][x] is not None:
                raise ValueError(f"Multiple blocks at mapart position: {(x, z - 1)}")
            _blocks[z - 1][x] = Block(block_name, int(y))

        # remove unnecessary padding heights
        for x, block in enumerate(_blocks[0]):
            if block is None:
                _padding_heights[x] = None

        return cls(_blocks, _padding_heights)

    def analyze_staircasing(self):
        def get_height_opt(block_opt: Block | None):
            if block_opt is None:
                return None
            return block_opt.height

        has_up = False
        has_down = False
        for padding_height, column in zip(self.padding_heights, zip(*self.blocks)):
            column_heights: list[int | None] = [
                padding_height,
                *map(get_height_opt, column),
            ]
            for top, bot in pairwise(column_heights):
                if top is None or bot is None:
                    continue
                if top < bot:
                    has_up = True
                if top > bot:
                    has_down = True

        match (has_up, has_down):
            case (True, True):
                self.meta["staircasing"] = Staircasing.BOTH
            case (True, False):
                self.meta["staircasing"] = Staircasing.UP
            case (False, True):
                self.meta["staircasing"] = Staircasing.DOWN
            case (False, False):
                self.meta["staircasing"] = Staircasing.FLAT

    def analyze_platforms(self):
        # initiate union-find to compute platforms
        nonair_coordinates = {
            (x, z)
            for z, row in enumerate(self.blocks)
            for x, block in enumerate(row)
            if block is not None
        } | {
            (x, -1)
            for x, height in enumerate(self.padding_heights)
            if height is not None
        }

        uf_parents = {xz: xz for xz in nonair_coordinates}
        uf_ranks = {xz: 0 for xz in nonair_coordinates}

        def uf_find(xz: Coords) -> Coords:
            if uf_parents[xz] != xz:
                uf_parents[xz] = uf_find(uf_parents[xz])
            return uf_parents[xz]

        def uf_union(left: Coords, right: Coords) -> None:
            root_l = uf_find(left)
            root_r = uf_find(right)
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

        # horizontal edges
        for z, row in enumerate(self.all_heights, start=-1):
            for x, (hl, hr) in enumerate(pairwise(row)):
                if hl is None or hr is None:
                    continue
                if hl == hr:
                    uf_union((x, z), (x + 1, z))

        # vertical edges
        for z, (row_top, row_bot) in enumerate(pairwise(self.all_heights), start=-1):
            for x, (ht, hb) in enumerate(zip(row_top, row_bot)):
                if ht is None or hb is None:
                    continue
                if ht == hb:
                    uf_union((x, z), (x + 1, z))

        inverse_uf_parents: dict[Coords, set[Coords]] = defaultdict(set)
        for block, parent in uf_parents.items():
            inverse_uf_parents[parent].add(block)

        self.meta["platforms"] = {
            frozenset(platform) for platform in inverse_uf_parents.values()
        }

    def to_region(self, support_block: str = "minecraft:resin_block") -> Region:
        all_heights = chain(
            (h for h in self.padding_heights if h is not None),
            (block.height for row in self.blocks for block in row if block is not None),
        )
        max_height = max(all_heights)
        region = Region(0, 0, -1, self.size, max_height + 1, self.size + 1)

        for x, h in enumerate(self.padding_heights):
            if h is None:
                continue
            region[x, h, 0] = BlockState(support_block)

        for z, row in enumerate(self.blocks, start=1):
            for x, block in enumerate(row):
                if block is None:
                    continue
                region[x, block.height, z] = BlockState(block.block_name)
                if (x, z) in self.scaffolding:
                    region[x, block.height - 1, z] = BlockState(support_block)
        return region

    def to_schematic(
        self,
        name: str,
        region_name: str | None = None,
        support_block: str = "minecraft:netherrack",
    ) -> Schematic:
        region = self.to_region(support_block=support_block)
        if region_name is None:
            region_name = name
        return Schematic(name=name, regions={region_name: region})
