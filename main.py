import nbtlib

from mapart import MapArt


def test():
    with nbtlib.load("spheal4.nbt") as schem:
        mapart = MapArt.from_nbt_file(schem)
        for i in range(32):
            print(f"{i:>3} {mapart.pixels[0][i]}")


def main():
    test()


if __name__ == "__main__":
    main()
