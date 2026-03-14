from typing import TypeGuard

from enum import Enum
from dataclasses import dataclass
from itertools import pairwise

from nbtlib import Compound
from mapart.reified import ReifiedMapArt
from mapart.staircased import StaircasedMapArt

__all__ = ["ReifiedMapArt", "StaircasedMapArt"]

import NBT


class Shading(Enum):
    DARK = 1
    FLAT = 2
    LITE = 3
    DARKER = 4  # special unobtainable in vanilla

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
    block_name: str
    shading: Shading

    def __str__(self) -> str:
        name = self.block_name.removeprefix("minecraft:")
        shading = self.shading.name
        return f"Pixel({name}, {shading})"


class ReificationStrategy(Enum):
    SIMPLE = 1
    PAIRWISE = 2
    UNIVERSAL = 3
    TWO_LAYER = 4


type Coords = tuple[int, int]


@dataclass
class MapArt:
    pixels: list[list[Pixel | None]]

    @property
    def size(self) -> int:
        return len(self.pixels[0])

    @classmethod
    def from_nbt_file(cls, schem: Compound, size: int = 128):
        # first row is padding height
        grid: list[list[tuple[str, int] | None]] = [
            [None for _ in range(size)] for _ in range(size + 1)
        ]
        for (x, y, z), block_name in NBT.get_blocks(schem):
            if not (0 <= x <= size and 0 <= z < size + 1):
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

    def reify(self, strategy: ReificationStrategy) -> ReifiedMapArt:
        match strategy:
            case ReificationStrategy.SIMPLE:
                return self._reify_simple()
            case ReificationStrategy.PAIRWISE:
                return self._reify_pairwise()
            case ReificationStrategy.UNIVERSAL:
                return self._reify_universal()
            case ReificationStrategy.TWO_LAYER:
                return self._reify_two_layer()

    def _reify_simple(self) -> ReifiedMapArt:
        raise ValueError("todo")

    def _reify_pairwise(self) -> ReifiedMapArt:
        raise ValueError("todo")

    def _reify_universal(self) -> ReifiedMapArt:
        raise ValueError("todo")

    def _reify_two_layer(self) -> ReifiedMapArt:
        raise ValueError("todo")
