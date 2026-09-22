from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CategoryContract(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str = Field(min_length=2, max_length=100)
    slug: str = Field(min_length=1, max_length=50)


class ProductContract(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str = Field(min_length=2, max_length=200)
    price: Decimal = Field(gt=0, le=1_000_000, max_digits=10, decimal_places=2)
    category: int = Field(gt=0)
    is_active: bool = True
    preview: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CategoryRead(BaseModel):
    name: str


class TagRead(BaseModel):
    name: str


class ProductReadContract(BaseModel):
    name: str
    price: Decimal
    category: CategoryRead
    tags: list[TagRead]
