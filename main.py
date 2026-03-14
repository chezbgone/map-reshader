from typing import Literal
from pathlib import Path

from litemapy import Schematic
import nbtlib

from NBT import remove_air
import optimizer.universal as universal
import optimizer.pairwise_z3 as pairwise_z3
from mapart import MapArt, StaircasedMapArt


def test():
    with nbtlib.load("bedrock.nbt") as schem:
        mapart = MapArt.from_nbt_file(schem)
        print(*enumerate(map(str, mapart.pixels[0][:32]), start=0), sep="\n")


def load_and_optimize_mapart(
    nbt_path: str,
    scaffolding_kind: str = "minimal",
    strategy: Literal["pairwise_z3", "universal"] = "pairwise_z3",
) -> tuple[StaircasedMapArt, float, float, float]:
    """Load NBT file, optimize mapart, return mapart and timing info."""
    with nbtlib.load(nbt_path) as schem:
        remove_air(schem)
        mapart = StaircasedMapArt.from_nbt_file(schem)

    if strategy == "pairwise_z3":
        opt_info = pairwise_z3.optimize_monotonically_bright(
            mapart, scaffolding_kind=scaffolding_kind
        )
    else:
        opt_info = universal.optimize(mapart)

    before_proportion = opt_info.original_eq_hpairs / opt_info.total_hpairs
    after_proportion = opt_info.final_eq_hpairs / opt_info.total_hpairs
    time_s = opt_info.time_taken.total_seconds()

    print(f"  {before_proportion:.4f} -> {after_proportion:.4f} in {time_s:.2f}s")
    return mapart, before_proportion, after_proportion, time_s


def save_mapart(
    mapart: StaircasedMapArt, name: str, region_name: str | None = None
) -> None:
    """Save mapart to a litematic file."""
    regions = {region_name or name: mapart.to_region()}
    Schematic(name, "chezbgone", regions=regions).save(f"{name}.litematic")


def optimize_pokemon(
    pokemon: str = "abra",
    strategy: Literal["pairwise_z3", "universal"] = "pairwise_z3",
):
    mapart, _, _, _ = load_and_optimize_mapart(
        f"base_schematics/{pokemon}.nbt",
        scaffolding_kind="minimal",
        strategy=strategy,
    )
    save_mapart(mapart, pokemon)


def optimize_all_and_collate():
    directory = Path("base_schematics")
    regions = {}
    total_time_s = 0
    for nbt in sorted(directory.iterdir()):
        if not nbt.is_file():
            continue
        print(f"processing {nbt}")
        mapart, _, _, time_s = load_and_optimize_mapart(str(nbt))
        total_time_s += time_s
        regions[nbt.stem] = mapart.to_region()

    Schematic("pokemon", "chezbgone", regions=regions).save("pokemon.litematic")
    print(f"done in {total_time_s:.2f} seconds!")


def optimize_one(nbt_file, out):
    mapart, _, _, _ = load_and_optimize_mapart(nbt_file)
    save_mapart(mapart, out, region_name="region")


def main():
    test()
    return
    optimize_all_and_collate()


if __name__ == "__main__":
    main()
