from dataclasses import dataclass, field
from typing import TypedDict

from litemapy import Schematic, Region


type Coords = tuple[int, int]


@dataclass
class Block:
    block_name: str
    height: int


class ReifiedMapArtMeta(TypedDict, total=False):
    pass


@dataclass
class ReifiedMapArt:
    """Base class for reified (3D) map art representations."""

    blocks: list[list[Block | None]]
    padding_heights: list[int | None]
    scaffolding: set[Coords] = field(default_factory=set)
    meta: ReifiedMapArtMeta = field(default_factory=dict)  # type: ignore[assignment]

    @property
    def size(self) -> int:
        return len(self.blocks[0])

    def to_region(self, support_block: str = "minecraft:resin_block") -> Region:
        """Convert to a litemapy Region."""
        raise NotImplementedError

    def to_schematic(
        self,
        name: str,
        region_name: str | None = None,
        support_block: str = "minecraft:netherrack",
    ) -> Schematic:
        """Convert to a litemapy Schematic."""
        region = self.to_region(support_block=support_block)
        if region_name is None:
            region_name = name
        return Schematic(name=name, regions={region_name: region})
