from typing import TypeGuard, override

from enum import Enum
from dataclasses import dataclass
from itertools import pairwise

import NBT


class Shading(Enum):
    DARK = 1
    FLAT = 2
    LITE = 3
    DARKER = 4  # special value; unobtainable in survival

    @classmethod
    def from_heights(cls, shader: int, height: int) -> Shading:
        if shader > height:
            return cls.DARK
        if shader < height:
            return cls.LITE
        if shader == height:
            return cls.FLAT
        raise ValueError("Should never occur")


@dataclass
class Pixel:
    """A pixel of an abstract map art, consisting of a block and its shading."""

    block_name: str
    shading: Shading

    @override
    def __str__(self) -> str:
        name = self.block_name.removeprefix("minecraft:")
        shading = self.shading.name
        return f"Pixel({name}, {shading})"


type Coords = tuple[int, int]


MAPART_SIZE = 128


@dataclass
class MapArt:
    """
    An abstract mapart consisting of only the pixel data.
    """

    pixels: list[list[Pixel | None]]

    @classmethod
    def from_nbt_file(cls, schem: NBT.MapArtNBT):
        # first row is padding height
        grid: list[list[tuple[str, int] | None]] = [
            [None for _ in range(MAPART_SIZE)] for _ in range(MAPART_SIZE + 1)
        ]
        for (x, y, z), block_name in NBT.get_blocks(schem):
            if not (0 <= x <= MAPART_SIZE and 0 <= z < MAPART_SIZE + 1):
                raise ValueError("Block position out of mapart bounds")
            old_block = grid[z][x]
            if old_block is not None and old_block[1] > y:
                # not overriding block
                continue
            grid[z][x] = (block_name, int(y))

        def no_nones[A](lst: list[list[A | None]]) -> TypeGuard[list[list[A]]]:
            return all(None not in row for row in lst)

        assert no_nones(grid)

        pixels = [
            [
                Pixel(block_name, Shading.from_heights(shader_height, block_height))
                if block_name != "minecraft:air"
                else None
                for ((_, shader_height), (block_name, block_height)) in zip(
                    shader_row, row
                )
            ]
            for (shader_row, row) in pairwise(grid)
        ]
        return cls(pixels)
