from itertools import pairwise

from hypothesis import given, strategies as st

from mapart.mapart import Shading
from mapart.mapart import Pixel
from mapart.simple import Block, FillerBlock, SimpleMapArt


def pixel() -> st.SearchStrategy[Pixel | None]:
    """Strategy for generating a Pixel or None."""
    return st.one_of(
        # st.none(),
        st.builds(
            Pixel,
            block_name=st.text(
                alphabet=st.sampled_from(["A", "B"]),
                min_size=1,
                max_size=5,
            ),
            shading=st.sampled_from([Shading.DARK, Shading.FLAT, Shading.LITE]),
        ),
    )


@given(st.lists(pixel(), min_size=1, max_size=128))
def test_pixel_column_to_simplepixels(column: list[Pixel | None]) -> None:
    """Test conversion of a column of Pixels to SimplePixels."""
    result = SimpleMapArt.pixel_column_to_simplepixels(column)
    assert len(result) == len(column) + 1
    for pixel, (top, bot) in zip(column, pairwise(result)):
        if pixel is None:
            assert (bot is None) or isinstance(bot, FillerBlock)
            continue
        assert isinstance(bot, Block)
        assert bot.block == pixel.block_name

        match pixel.shading:
            case Shading.LITE:
                assert top is None or bot.height > top.height
            case Shading.FLAT:
                assert top is not None and bot.height == top.height
            case Shading.DARK:
                assert top is not None and bot.height < top.height
            case Shading.DARKER:
                raise ValueError("should never happen")
