from typing import Self

from enum import Enum
from dataclasses import dataclass, field

from nbtlib import Compound, List
from litemapy import Schematic, Region, BlockState

import NBT

class Shading(Enum):
    DARK = 1
    FLAT = 2
    LITE = 3
    DARKER = 4

@dataclass
class ReifiedMapArt:
    blocks: list[list[str | None]]  # SIZE x SIZE grid of block names or None

    # (SIZE + 1) x SIZE positive ints representing height at each (x, z).
    # the first row is the extra row north of the map area
    height_map: list[list[int | None]]
    scaffolding: set[tuple[int, int]] = field(default_factory=set)
    
    @property
    def SIZE(self) -> int:
        return len(self.height_map[0])

    @staticmethod
    def from_nbt_file(schem: Compound, size: int = 128) -> Self:
        palette = NBT.get_palette(schem)
        blocks = NBT.get_blocks(schem)

        # remove air blocks from schematic
        schem['blocks'] = List[Compound]([
            block
            for block in schem['blocks']
            if palette[block['state']] != 'minecraft:air'
        ])

        _grid: list[list[str | None]] = [
            [None for _ in range(size)]
            for _ in range(size)
        ]
        _height_map: list[list[int | None]] = [
            [None for _ in range(size)]
            for _ in range(size + 1)
        ]

        for (x, y, z), block_name in blocks:
            # ensure block is within mapart bounds
            if not (
                0 <= x < size and
                0 <= z < size + 1
            ):
                raise ValueError(f"Block position out of mapart bounds: {(x, y, z)}")
            # set height map
            _height_map[z][x] = int(y)
            # set grid
            if z == 0:
                # the extra row is not part of the grid, so skip it
                continue
            if _grid[z - 1][x] is not None:
                raise ValueError(f"Multiple blocks at mapart position: {(x, z - 1)}")
            _grid[z - 1][x] = block_name
        
        return ReifiedMapArt(_grid, _height_map)

    def to_region(
            self,
            support_block: str='minecraft:netherrack'
    ) -> Region:
        max_height = max(
            height
            for row in self.height_map
            for height in row
            if height is not None
        )
        region = Region(0, 0, -1, self.SIZE, max_height + 1, self.SIZE + 1)

        support_heights, *height_map = self.height_map
        for x, h in enumerate(support_heights):
            if h is None:
                continue
            region[x, h, 0] = BlockState(support_block)

        for z, (block_row, height_row) in enumerate(zip(self.blocks, height_map), start=1):
            for x, (block, height) in enumerate(zip(block_row, height_row)):
                if block is None and height is None:
                    continue
                if block is None or height is None:
                    raise ValueError(f"Inconsistent block and height at {(x, z)}: {block}, {height}")
                region[x, height, z] = BlockState(block)
                if (x, z) in self.scaffolding:
                    region[x, height - 1, z] = BlockState(support_block)
        return region

    def to_schematic(
            self,
            name: str,
            region_name: str | None = None,
            support_block: str = 'minecraft:netherrack'
    ) -> Schematic:
        region = self.to_region(support_block=support_block)
        if region_name is None:
            region_name = name
        return Schematic(name=name, regions={region_name: region})