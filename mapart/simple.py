from collections.abc import Sequence
from itertools import pairwise
from typing import override

from dataclasses import dataclass

from litemapy import BlockState, Region, Schematic

from mapart.mapart import MAPART_SIZE, MapArt, Pixel, Shading
from mapart.reified import ReifiedMapArt


@dataclass
class Block:
    block: str
    height: int


@dataclass
class FillerBlock:
    height: int


type SimplePixel = Block | FillerBlock | None


@dataclass
class SimpleMapArt(ReifiedMapArt):
    """
    A ReifiedMapArt with indepenent staircased columns

    filler_block is either:
    - a string representing a block, or
    - a pair of strings (b0, b1) representing filler blocks
      that go on even and odd positions respectively.
    """

    columns: list[list[SimplePixel]]
    region_name: str
    filler_block: str | tuple[str, str]

    def __post_init__(self) -> None:
        for x, column in enumerate(self.columns):
            if len(column) != 129:
                raise ValueError(f"column {x=} does not have enough entries")
            z0_pixel = column[0]
            if isinstance(z0_pixel, Block):
                raise ValueError(
                    f"z=0 pixel at {x=} cannot be Block, got block='{z0_pixel.block}'"
                )

    @staticmethod
    def pixel_column_to_simplepixels(
        pixels: Sequence[Pixel | None],
    ) -> list[SimplePixel]:
        n = len(pixels)

        # left[i] = min height at position i imposed by constraints to the left
        left = [0] * (n + 1)
        for i, p in enumerate(pixels):
            if p is None:
                left[i + 1] = 0
                continue
            match p.shading:
                case Shading.LITE:
                    left[i + 1] = left[i] + 1
                case Shading.FLAT:
                    left[i + 1] = left[i]
                case Shading.DARK:
                    left[i + 1] = 0
                case Shading.DARKER:
                    raise ValueError("DARKER shading unobtainable in vanilla")

        # right[i] = min height at position i imposed by constraints to the right
        right = [0] * (n + 1)
        for i, p in reversed(list(enumerate(pixels))):
            if p is None:
                right[i] = 0
                continue
            match p.shading:
                case Shading.LITE:
                    right[i] = 0
                case Shading.FLAT:
                    right[i] = right[i + 1]
                case Shading.DARK:
                    right[i] = right[i + 1] + 1
                case Shading.DARKER:
                    raise ValueError("DARKER shading unobtainable in vanilla")

        padding, *heights = [max(l, r) for l, r in zip(left, right, strict=True)]
        tentative_blocks: list[SimplePixel] = [
            FillerBlock(h) if p is None else Block(p.block_name, h)
            for p, h in zip(pixels, heights, strict=True)
        ]
        for i, (top, bot) in enumerate(pairwise([*pixels, None])):
            if top is None and bot is None:
                tentative_blocks[i] = None
        if pixels[0] is None:
            padding_block = None
        else:
            padding_block = FillerBlock(padding)

        return [padding_block, *tentative_blocks]

    @staticmethod
    def from_mapart(
        mapart: MapArt,
        region_name: str,
        filler_block: str | tuple[str, str],
    ) -> SimpleMapArt:
        """
        Create a SimpleMapArt from a MapArt.

        The ReifiedMapArt will have indepenent columns, with all blocks having
        minimal height. This is also known as "valley" staircasing.
        """
        columns: list[tuple[Pixel | None, ...]] = list(zip(*mapart.pixels, strict=True))

        output_columns: list[list[SimplePixel]] = [
            SimpleMapArt.pixel_column_to_simplepixels(col) for col in columns
        ]

        return SimpleMapArt(output_columns, region_name, filler_block)

    def filler_block_at(self, x: int, z: int) -> BlockState:
        match self.filler_block:
            case tuple():
                return BlockState(self.filler_block[(x + z) % 2])
            case str():
                return BlockState(self.filler_block)

    @override
    def to_schematic(
        self,
        name: str,
    ) -> Schematic:
        max_height = max(
            pixel.height for col in self.columns for pixel in col if pixel is not None
        )
        region = Region(0, 0, -1, MAPART_SIZE, max_height + 1, MAPART_SIZE + 1)
        for x, col in enumerate(self.columns):
            for z, pixel in enumerate(col, start=-1):
                match pixel:
                    case None:
                        continue
                    case Block(block_name, height):
                        region[x, height, z] = BlockState(block_name)
                    case FillerBlock(height):
                        region[x, height, z] = self.filler_block_at(x, z)

        return Schematic(name=name, regions={self.region_name: region})
