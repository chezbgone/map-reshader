from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Literal, override

from litemapy import BlockState, Schematic

from mapart.mapart import MapArt, Pixel, Shading
from mapart.reified import ReifiedMapArt


@dataclass
class Block:
    block: str
    y: Literal[0, 1]

    @property
    def height(self) -> int:
        return self.y


@dataclass
class FillerBlock:
    y: Literal[0, 1]

    @property
    def height(self) -> int:
        return self.y


@dataclass
class CoveredBlock:
    """
    Represents a block at y=0 with a filler block at y=1.
    Used only in the case where there is DARK then FLAT then NONE shading.
    """

    block: str

    @property
    def height(self) -> int:
        return 1


type LayerPixel = Block | FillerBlock | CoveredBlock | None


@dataclass
class DualLayerMapArt(ReifiedMapArt):
    """
    Dual-layer map art using to separate layers to take advantage
    of Minecraft's selective rendering based on (x+z) parity.

    There are three 128×2×128 regions bottom, top_before, and top_after.
    During the rendering process of the map art, top_before is removed and
    replaced with top_after. There is a gap of `gap_size` blocks between
    bottom and the top regions.

    Intuitively, the regions contain the following (ignoring optimizations)
    - bottom: odd pixels (x+z) % 2 == 1
    - top_before: even pixels (x+z) % 2 == 0 (actual pixel data)
    - top_after: filler/transparency handling after top_before is removed

    When bottom and top_before are rendered, all even pixels will appear correctly.
    When bottom and top_after are rendered, all odd pixels will appear correctly.
    """

    bottom: list[list[LayerPixel]]
    top_before: list[list[LayerPixel]]
    top_after: list[list[LayerPixel]]

    filler_block: BlockState
    gap_size: int

    def __post_init__(self) -> None:
        for name, columns in [
            ("bottom", self.bottom),
            ("top_before", self.top_before),
            ("top_after", self.top_after),
        ]:
            for x, column in enumerate(columns):
                if len(column) != 129:
                    raise ValueError(f"{name} column {x=} does not have enough entries")
                z0_pixel = column[0]
                if isinstance(z0_pixel, Block):
                    raise ValueError(
                        f"{name} z=0 pixel at {x=} cannot be Block, got block='{z0_pixel.block}'"
                    )

    @staticmethod
    def pixel_column_to_layerpixels(
        column_index: int,
        column: Sequence[Pixel | None],
        *,
        optimize: bool = True,
    ) -> tuple[list[LayerPixel], list[LayerPixel], list[LayerPixel]]:
        """
        Convert a single pixel column into three layer columns.

        Returns (bottom, top_before, top_after) columns.
        """
        n = len(column)

        bottom: list[LayerPixel] = [None] * (n + 1)
        top_before: list[LayerPixel] = [None] * (n + 1)
        top_after: list[LayerPixel] = [None] * (n + 1)

        # place the special cases first
        # these are the ones whose transparency affect the layer the blocks appear on
        done_indices: set[int] = set()
        for z, (north, pixel) in enumerate(pairwise(column)):
            # for layer indexing, we have to account for the padding
            north_layer_z = z + 1
            pixel_layer_z = z + 2
            north_is_even = (column_index + z) % 2 == 0

            if not north_is_even:
                continue
            if pixel is None:
                continue
            if north is not None:
                continue

            if pixel.shading == Shading.DARK:
                top_after[north_layer_z] = FillerBlock(0)
                bottom[pixel_layer_z] = Block(pixel.block_name, 0)
                done_indices.add(north_layer_z)
                done_indices.add(pixel_layer_z)

            if pixel.shading == Shading.FLAT:
                top_after[north_layer_z] = FillerBlock(0)
                top_before[pixel_layer_z] = Block(pixel.block_name, 0)
                top_after[pixel_layer_z] = Block(pixel.block_name, 0)
                done_indices.add(north_layer_z)
                done_indices.add(pixel_layer_z)
                if z + 2 >= len(column):
                    continue
                south = column[z + 2]
                south_layer_z = z + 3
                if south is not None:
                    match south.shading:
                        case Shading.LITE:
                            top_before[south_layer_z] = Block(south.block_name, 1)
                            top_after[south_layer_z] = None
                        case Shading.FLAT:
                            top_before[south_layer_z] = Block(south.block_name, 0)
                            top_after[south_layer_z] = None
                        case Shading.DARK:
                            top_before[pixel_layer_z] = CoveredBlock(pixel.block_name)
                            top_before[south_layer_z] = Block(south.block_name, 0)
                            top_after[south_layer_z] = None
                done_indices.add(south_layer_z)

        # place the rest of the pixels naively
        for z, pixel in enumerate(column):
            if pixel is None:
                continue

            is_odd = (column_index + z) % 2 == 1
            layer_index = z + 1  # +1 because index 0 in return lists are padding
            if layer_index in done_indices:
                continue

            # pick the layer to add blocks to depending on parity
            layer = bottom if is_odd else top_before

            match pixel.shading:
                case Shading.LITE:
                    # we can save a filler block by using the lower layer or "void"
                    layer[layer_index] = Block(pixel.block_name, 0)
                case Shading.FLAT:
                    layer[layer_index] = Block(pixel.block_name, 0)
                    layer[layer_index - 1] = FillerBlock(0)
                case Shading.DARK:
                    layer[layer_index] = Block(pixel.block_name, 0)
                    layer[layer_index - 1] = FillerBlock(1)

        if not optimize:
            return bottom, top_before, top_after

        # optimization steps
        for z, (north, pixel) in enumerate(pairwise(column)):
            # for layer indexing, we have to account for the padding
            north_layer_z = z + 1
            pixel_layer_z = z + 2
            north_is_even = (column_index + z) % 2 == 0

            if not north_is_even:
                continue
            if north is None:
                continue

            # don't optimize the special cases
            if north_layer_z in done_indices or north_layer_z + 1 in done_indices:
                continue

            # handle northernmost row first
            if z == 0:
                if north.shading == Shading.FLAT:
                    continue
                if pixel is None or pixel.shading != Shading.LITE:
                    top_before[north_layer_z] = None
                    bottom[north_layer_z] = Block(
                        north.block_name,
                        0 if pixel is None or pixel.shading == Shading.FLAT else 1,
                    )
                    if north.shading == Shading.DARK:
                        top_before[north_layer_z - 1] = FillerBlock(0)

            norther: Pixel | None = column[z - 1]
            pixel_shading: Shading | None = None if pixel is None else pixel.shading
            norther_shading: Shading | None = (
                None if norther is None else norther.shading
            )
            match north.shading:
                case Shading.LITE:
                    if pixel_shading not in (None, Shading.DARK):
                        continue
                    top_before[north_layer_z] = None
                    bottom[north_layer_z] = Block(north.block_name, 1)
                case Shading.FLAT:
                    if pixel_shading == Shading.LITE:
                        continue
                    if norther_shading is None:
                        continue
                    top_before[north_layer_z] = None
                    top_before[north_layer_z - 1] = None
                    bottom[north_layer_z] = Block(north.block_name, 0)
                    if pixel_shading == Shading.DARK:
                        top_after[north_layer_z] = FillerBlock(0)
                case Shading.DARK:
                    if pixel_shading == Shading.LITE:
                        continue
                    top_before[north_layer_z] = None
                    top_before[north_layer_z - 1] = FillerBlock(0)
                    bottom[north_layer_z] = Block(
                        north.block_name, 1 if pixel_shading == Shading.DARK else 0
                    )

        return bottom, top_before, top_after

    @staticmethod
    def from_mapart(
        _mapart: MapArt,
        _gap_size: int,
        _filler_block: str = "resin_block",
    ) -> "DualLayerMapArt":
        """
        Create a DualLayerMapArt from a MapArt.
        """
        raise NotImplementedError()

    @override
    def to_schematic(self, name: str) -> Schematic:
        raise NotImplementedError()
