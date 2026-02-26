from typing import Self, TypedDict

from collections import defaultdict
from enum import Enum
from dataclasses import dataclass, field
from functools import cached_property
from itertools import chain, pairwise

from nbtlib import Compound, List
from litemapy import Schematic, Region, BlockState

import NBT


class Shading(Enum):
    DARK = 1
    FLAT = 2
    LITE = 3
    DARKER = 4  # special unobtainable in vanilla


@dataclass
class Pixel:
    block_name: str
    shading: Shading


class Staircasing(Enum):
    FLAT = 1
    UP = 2
    DOWN = 3
    BOTH = 4


class ReificationStrategy(Enum):
    SIMPLE = 1
    PAIRWISE = 2
    UNIVERSAL = 3


type Coords = tuple[int, int]


@dataclass
class MapArt:
    pixels: list[list[Pixel | None]]

    @property
    def size(self) -> int:
        return len(self.pixels[0])

    @cached_property
    def staircasing(self) -> Staircasing:
        has_up = False
        has_down = False
        for row in self.pixels:
            for pixel in row:
                if pixel is None:
                    continue
                if pixel.shading == Shading.DARK:
                    has_down = True
                if pixel.shading == Shading.LITE:
                    has_up = True
                if has_up and has_down:
                    break
            else:  # if no break
                continue
            break  # up and down already achieved
        match (has_up, has_down):
            case (True, True):
                return Staircasing.BOTH
            case (True, False):
                return Staircasing.UP
            case (False, True):
                return Staircasing.DOWN
            case (False, False):
                return Staircasing.FLAT

    def reify(self, strategy: ReificationStrategy) -> StaircasedMapArt:
        match strategy:
            case ReificationStrategy.SIMPLE:
                return self._reify_simple()
            case ReificationStrategy.PAIRWISE:
                return self._reify_simple()
            case ReificationStrategy.UNIVERSAL:
                return self._reify_simple()

    def _reify_simple(self) -> StaircasedMapArt:
        raise ValueError("todo")

    def _reify_pairwise(self) -> StaircasedMapArt:
        raise ValueError("todo")

    def _reify_universal(self) -> StaircasedMapArt:
        raise ValueError("todo")


@dataclass
class Block:
    block_name: str
    height: int


class StaircasedMapArtMeta(TypedDict, total=False):
    staircasing: Staircasing
    platforms: set[frozenset[Coords]]


@dataclass
class StaircasedMapArt:
    blocks: list[list[Block | None]]
    padding_heights: list[
        int | None
    ]  # the row of auxillary blocks north of the block grid
    scaffolding: set[Coords] = field(default_factory=set)
    meta: StaircasedMapArtMeta = field(default_factory=dict)  # type: ignore[assignment]

    @property
    def size(self) -> int:
        return len(self.blocks[0])

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

    @staticmethod
    def from_nbt_file(schem: Compound, size: int = 128) -> StaircasedMapArt:
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

        return StaircasedMapArt(_blocks, _padding_heights)

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

        def uf_union(l: Coords, r: Coords) -> None:
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
