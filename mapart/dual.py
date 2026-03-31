from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, override

from litemapy import BlockState, Region, Schematic

from mapart.mapart import MAPART_SIZE, MapArt, Pixel
from mapart.reified import ReifiedMapArt


@dataclass
class Block:
    block: str
    position: Literal["up", "down"]

    @property
    def height(self) -> int:
        return 1 if self.position == "up" else 0


@dataclass
class FillerBlock:
    position: Literal["up", "down"]

    @property
    def height(self) -> int:
        return 1 if self.position == "up" else 0


type LayerPixel = Block | FillerBlock | None


@dataclass
class DualLayerMapArt(ReifiedMapArt):
    """
    Dual-layer map art using two separate layers to take advantage
    of Minecraft's selective rendering based on (x+z) parity.

    There are three 128×2×128 regions bottom, top_before, and top_after.
    During the rendering process of the map art, top_before is removed and
    replaced with top_after. There is a gap of `gap_size` blocks between
    bottom and the top regions.

    Intuitively, the regions contain the following (ignoring optimizations)
    - bottom: odd pixels (x+z) % 2 == 1
    - top_before: even pixels (x+z) % 2 == 0 (actual pixel data)
    - top_after: filler/transparency handling after top_before is removed

    When bottom and top_before is rendered, all even pixels will appear correctly.
    When bottom and top_after is rendered, all odd pixels will appear correctly.
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
    ) -> tuple[list[LayerPixel], list[LayerPixel], list[LayerPixel]]:
        """
        Convert a single pixel column into three layer columns.


        Returns (bottom, top_before, top_after) columns.
        """
        raise NotImplementedError()

    @staticmethod
    def from_mapart(
        mapart: MapArt,
        gap_size: int,
    ) -> "DualLayerMapArt":
        """
        Create a DualLayerMapArt from a MapArt.

        Distributes pixels based on (x+z) parity:
        - Odd (x+z): bottom layer
        - Even (x+z): top_before layer

        The top_after layer handles filler/transparency.
        """
        raise NotImplementedError()

    @override
    def to_schematic(self, name: str) -> Schematic:
        raise NotImplementedError()
