from typing import Never, TypedDict, cast

from collections.abc import Generator
from contextlib import contextmanager

import nbtlib
from nbtlib import Compound, List, String, Int


class BlockEntry(TypedDict):
    pos: tuple[Int, Int, Int]
    state: Int


class PaletteEntry(TypedDict):
    Name: String


class MapArtNBT(TypedDict):
    blocks: list[BlockEntry]
    entities: list[Never]
    palette: list[PaletteEntry]
    size: tuple[Int, Int, Int]
    DataVersion: Int


@contextmanager
def load_mapart_NBT(filename: str) -> Generator[MapArtNBT]:
    schem = nbtlib.load(filename)
    yield cast(MapArtNBT, cast(object, schem))


def get_palette(schem: MapArtNBT) -> dict[int, str]:
    palette = schem["palette"]
    return {index: str(entry["Name"]) for index, entry in enumerate(palette)}


def get_inverse_palette(schem: MapArtNBT) -> dict[str, int]:
    return {entry: index for index, entry in get_palette(schem).items()}


def get_blocks(schem: MapArtNBT) -> list[tuple[tuple[int, int, int], str]]:
    palette = get_palette(schem)
    return [
        ((block["pos"][0], block["pos"][1], block["pos"][2]), palette[block["state"]])
        for block in schem["blocks"]
    ]


def remove_air(schem: MapArtNBT) -> None:
    air_id = schem["palette"].index(Compound({"Name": "minecraft:air"}))  # pyright: ignore[reportArgumentType]
    blocks_with_no_air = [
        block for block in schem["blocks"] if block["state"] != air_id
    ]
    schem["blocks"] = List[Compound](blocks_with_no_air)
