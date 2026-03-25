from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ListFoodRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Food name")
    quantity: int = Field(..., ge=0, description="Quantity available")
    price: float = Field(..., ge=0, description="Price (in your chosen currency)")


class ClaimRequest(BaseModel):
    listing_id: int = Field(..., ge=1)


class FoodListingResponse(BaseModel):
    id: int
    name: str
    quantity: int
    price: float
    hash: str
    tx_hash: str
    created_at: datetime
    claimed: bool = False

    @staticmethod
    def from_row(row: Any) -> "FoodListingResponse":
        """
        Normalize Supabase row shapes into our response model.
        Supabase might return `numeric`/`timestamptz` fields in different python types.
        """
        return FoodListingResponse(
            id=int(row.get("id")),
            name=str(row.get("name")),
            quantity=int(row.get("quantity")),
            price=float(row.get("price")),
            hash=str(row.get("hash")),
            tx_hash=str(row.get("tx_hash")),
            created_at=_parse_datetime(row.get("created_at")),
            claimed=bool(row.get("claimed", False)),
        )


class VerifyResponse(BaseModel):
    exists: bool
    tx_hash: Optional[str] = None


def _parse_datetime(value: Optional[Any]) -> datetime:
    if isinstance(value, datetime):
        return value
    if value is None:
        # Shouldn't happen if table schema uses `default now()`.
        raise ValueError("created_at is required")
    # Supabase typically returns ISO8601 strings for timestamptz.
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))

