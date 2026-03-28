# pyright: reportMissingTypeStubs=true


from nbtlib import Compound, List


def get_palette(schem: Compound) -> dict[int, str]:
    palette = schem["palette"]
    return {index: str(entry["Name"]) for index, entry in enumerate(palette)}


def get_inverse_palette(schem: Compound) -> dict[str, int]:
    return {entry: index for index, entry in get_palette(schem).items()}


def get_blocks(schem: Compound) -> list[tuple[tuple[int, int, int], str]]:
    palette = get_palette(schem)
    return [
        ((block["pos"][0], block["pos"][1], block["pos"][2]), palette[block["state"]])
        for block in schem["blocks"]
    ]


def remove_air(schem: Compound) -> None:
    air_id = schem["palette"].index(Compound({"Name": "minecraft:air"}))
    blocks_with_no_air = [
        block for block in schem["blocks"] if block["state"] != air_id
    ]
    schem["blocks"] = List[Compound](blocks_with_no_air)
