from typing import Protocol, runtime_checkable

from litemapy import Schematic


@runtime_checkable
class ReifiedMapArt(Protocol):
    """Protocol for extracting with determined block placements from a map art"""

    def to_schematic(self, name: str) -> Schematic:
        """
        Convert the map art into a .litematic file
        """
        ...
