from typing import Literal
from pathlib import Path

from litemapy import Schematic
import nbtlib

from NBT import remove_air
import optimizer.universal as universal
import optimizer.pairwise_z3 as pairwise_z3
from mapart import StaircasedMapArt


def optimize_pokemon(
    pokemon: str = "abra",
    strategy: Literal["pairwise_z3", "universal"] = "pairwise_z3",
):
    regions = {}
    with nbtlib.load(f"base_schematics/{pokemon}.nbt") as schem:
        remove_air(schem)
        mapart = StaircasedMapArt.from_nbt_file(schem)
    if strategy == "pairwise_z3":
        opt_info = pairwise_z3.optimize_monotonically_bright(
            mapart, scaffolding_kind="minimal"
        )
    else:
        opt_info = universal.optimize(mapart)
    before_proportion = opt_info.original_eq_hpairs / opt_info.total_hpairs
    after_proportion = opt_info.final_eq_hpairs / opt_info.total_hpairs
    print(
        f"  {before_proportion:.4f} -> {after_proportion:.4f} in {opt_info.time_taken.total_seconds():.2f}s"
    )
    regions[pokemon] = mapart.to_region()
    schem = Schematic(pokemon, "chezbgone", regions=regions).save(
        f"{pokemon}.litematic"
    )


def optimize_all_and_collate():
    directory = Path("base_schematics")
    regions = {}
    total_time_s = 0
    for nbt in sorted(directory.iterdir()):
        if not nbt.is_file():
            continue
        print(f"processing {nbt}")
        with nbtlib.load(nbt) as schem:
            remove_air(schem)
            mapart = StaircasedMapArt.from_nbt_file(schem)
        opt_info = pairwise_z3.optimize_monotonically_bright(
            mapart, scaffolding_kind="minimal"
        )
        before_proportion = opt_info.original_eq_hpairs / opt_info.total_hpairs
        after_proportion = opt_info.final_eq_hpairs / opt_info.total_hpairs
        total_time_s += opt_info.time_taken.total_seconds()
        print(
            f"  {before_proportion:.4f} -> {after_proportion:.4f} in {opt_info.time_taken.total_seconds():.2f}s"
        )
        regions[nbt.stem] = mapart.to_region()

    Schematic("pokemon", "chezbgone", regions=regions).save("pokemon.litematic")
    print(f"done in {total_time_s:.2f} seconds!")


def optimize_one(nbt_file, out):
    with nbtlib.load(nbt_file) as schem:
        remove_air(schem)
        mapart = StaircasedMapArt.from_nbt_file(schem)
    opt_info = pairwise_z3.optimize_monotonically_bright(
        mapart, scaffolding_kind="minimal"
    )
    before_proportion = opt_info.original_eq_hpairs / opt_info.total_hpairs
    after_proportion = opt_info.final_eq_hpairs / opt_info.total_hpairs
    print(
        f"  {before_proportion:.4f} -> {after_proportion:.4f} in {opt_info.time_taken.total_seconds():.2f}s"
    )
    regions = {"region": mapart.to_region()}
    Schematic(out, "chezbgone", regions=regions).save(f"{out}.litematic")


def main():
    optimize_all_and_collate()


if __name__ == "__main__":
    main()
