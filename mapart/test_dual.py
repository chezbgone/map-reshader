from itertools import pairwise
from hypothesis import given, settings, strategies as st

from mapart.mapart import Shading
from mapart.mapart import Pixel
from mapart.dual import Block, DualLayerMapArt, FillerBlock


def pixel() -> st.SearchStrategy[Pixel | None]:
    """Strategy for generating a Pixel or None."""
    return st.one_of(
        st.builds(
            Pixel,
            block_name=st.text(
                alphabet=st.sampled_from(["A", "B"]),
                min_size=1,
                max_size=3,
            ),
            shading=st.sampled_from([Shading.DARK, Shading.FLAT, Shading.LITE]),
        ),
    )


@given(
    st.integers(min_value=0, max_value=127), st.lists(pixel(), min_size=1, max_size=128)
)
@settings(max_examples=100)
def test_pixel_column_to_layerpixels(x: int, column: list[Pixel | None]) -> None:
    """Test conversion of a column of Pixels to three layer columns."""
    result_bottom, result_top_before, result_top_after = (
        DualLayerMapArt.pixel_column_to_layerpixels(x, column)
    )

    # Each layer column should have padding (z=0) + original column length
    assert len(result_bottom) == len(column) + 1
    assert len(result_top_before) == len(column) + 1
    assert len(result_top_after) == len(column) + 1

    results = zip(result_bottom, result_top_before, result_top_after)
    for z, (
        pixel,
        ((bot_, top_before_, top_after_), (bot, top_before, top_after)),
    ) in enumerate(zip(column, pairwise(results))):
        # whole column is transpraent if pixel is transparent
        if pixel is None:
            assert bot is None and top_before is None
            continue

        # select which top to use based on parity
        is_even = (x + z) % 2 == 0
        top = top_before if is_even else top_after
        top_ = top_before_ if is_even else top_after_

        # pixel is not transparent, so top should be a real block or None
        assert not isinstance(top, FillerBlock)

        # ensure block_name is correct, and compute heights
        if top is None:
            assert isinstance(bot, Block)
            assert bot.block == pixel.block_name
            this_height = bot.height
        else:
            assert top.block == pixel.block_name
            this_height = top.height

        if top_ is None:
            north_height = bot_.height if bot_ is not None else -float("inf")
        else:
            north_height = top_.height

        # check shading
        match pixel.shading:
            case Shading.LITE:
                assert this_height > north_height
            case Shading.FLAT:
                assert this_height == north_height
            case Shading.DARK:
                assert this_height < north_height
            case Shading.DARKER:
                raise ValueError("DARKER shading not supported")
