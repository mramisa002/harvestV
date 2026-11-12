from datetime import date
from typing import Protocol
from pydantic import BaseModel, Field
class ForecastDay(BaseModel):
    day: date
    rain_mm: float = Field(ge=0)
    tmin: float
    tmax: float
    issued_at: str
    provider: str
class ForecastProvider(Protocol):
    async def fetch(self, lat: float, lon: float, start: date, days: int) -> list[ForecastDay]: ...
# No provider is configured. No endpoint presents climatology as a forecast.
