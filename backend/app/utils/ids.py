from bson import ObjectId
from fastapi import HTTPException, status


def parse_object_id(value: str, what: str = "Record") -> ObjectId:
    """Parse an id from a URL. Invalid ids get the same 404 as missing ones."""
    if not ObjectId.is_valid(value):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{what} not found")
    return ObjectId(value)
