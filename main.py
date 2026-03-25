import hashlib
import json
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from models.schemas import ClaimRequest, FoodListingResponse, ListFoodRequest, VerifyResponse
from services.blockchain import send_to_blockchain
from services.supabase_client import get_supabase_client


app = FastAPI(title="Pocket Bite API", version="0.1.0")

# Hackathon-friendly: allow all origins. Tighten for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: str
    time_utc: str


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", time_utc=datetime.utcnow().isoformat() + "Z")


def compute_food_hash(name: str, quantity: int, price: float) -> str:
    """
    Produce a stable SHA256 over the listing fields.

    Note: Supabase `numeric` -> float conversion can vary; keep the input types stable
    by hashing the canonical request payload (not the stored DB value).
    """
    payload = {"name": name, "quantity": quantity, "price": price}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@app.post("/list-food", response_model=FoodListingResponse)
def list_food(req: ListFoodRequest) -> FoodListingResponse:
    supabase = get_supabase_client()

    if req.quantity < 0:
        raise HTTPException(status_code=400, detail="quantity must be >= 0")
    if req.price < 0:
        raise HTTPException(status_code=400, detail="price must be >= 0")

    food_hash = compute_food_hash(req.name, req.quantity, req.price)

    # Blockchain-backed verification
    tx_hash = send_to_blockchain(food_hash)

    listing_row = {
        "name": req.name,
        "quantity": req.quantity,
        "price": req.price,
        "hash": food_hash,
        "tx_hash": tx_hash,
        "claimed": False,
    }

    try:
        # Insert and request the inserted row back.
        res = supabase.table("food_listings").insert(listing_row).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store listing in Supabase: {e}")

    data = getattr(res, "data", None)
    if not data:
        # Some Supabase configurations return no row data on insert; fetch by hash.
        try:
            res2 = (
                supabase.table("food_listings")
                .select("*")
                .eq("hash", food_hash)
                .order("created_at", desc=True)
                .execute()
            )
            data = getattr(res2, "data", None)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Inserted, but failed to fetch row: {e}")

    if not data:
        raise HTTPException(status_code=500, detail="Supabase insert returned no data")

    row = data[0] if isinstance(data, list) else data
    return FoodListingResponse.from_row(row)


@app.get("/get-listings", response_model=list[FoodListingResponse])
def get_listings() -> list[FoodListingResponse]:
    supabase = get_supabase_client()

    try:
        res = (
            supabase.table("food_listings")
            .select("*")
            .order("created_at", desc=False)
            .execute()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load listings from Supabase: {e}")

    data = getattr(res, "data", [])
    return [FoodListingResponse.from_row(row) for row in (data or [])]


@app.post("/claim", response_model=FoodListingResponse)
def claim_food(req: ClaimRequest) -> FoodListingResponse:
    supabase = get_supabase_client()

    try:
        res = (
            supabase.table("food_listings")
            .update({"claimed": True})
            .eq("id", req.listing_id)
            .execute()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update claim in Supabase: {e}")

    data = getattr(res, "data", None)
    if not data:
        # Some configurations return no updated-row data; fetch it.
        try:
            res2 = supabase.table("food_listings").select("*").eq("id", req.listing_id).execute()
            data = getattr(res2, "data", None)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Claim updated, but failed to fetch row: {e}")

    if not data:
        raise HTTPException(status_code=404, detail="Listing not found")

    row = data[0] if isinstance(data, list) else data
    return FoodListingResponse.from_row(row)


@app.get("/verify/{hash}", response_model=VerifyResponse)
def verify_hash(hash: str) -> VerifyResponse:
    supabase = get_supabase_client()
    try:
        res = (
            supabase.table("food_listings")
            .select("tx_hash")
            .eq("hash", hash)
            .limit(1)
            .execute()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to verify hash in Supabase: {e}")

    data = getattr(res, "data", None) or []
    if not data:
        return VerifyResponse(exists=False, tx_hash=None)

    row = data[0] if isinstance(data, list) else data
    tx_hash = row.get("tx_hash")
    return VerifyResponse(exists=True, tx_hash=str(tx_hash) if tx_hash is not None else None)

