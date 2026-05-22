"""Map context client interface.

Detailed location and map facts belong to map-service / map read model.
"""
from typing import Protocol, Any


class MapContextClient(Protocol):
    async def get_location_context(self, lat: float, lng: float) -> Any: ...
