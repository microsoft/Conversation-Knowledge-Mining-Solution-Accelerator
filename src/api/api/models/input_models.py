from pydantic import BaseModel
from typing import List


class SelectedFilters(BaseModel):
    Topic: List[str]
    Sentiment: List[str]
    DateRange: List[str]


class ChartFilters(BaseModel):
    selected_filters: SelectedFilters
