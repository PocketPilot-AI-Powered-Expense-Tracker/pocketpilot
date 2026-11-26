import datetime as dt

from bson import ObjectId


def to_out(doc: dict) -> dict:
    """Mongo document -> plain dict for a Pydantic *Out model.
    `_id` becomes `id`, ObjectIds become strings, user_id is dropped."""
    out = {}
    for k, v in doc.items():
        if k == "user_id":
            continue
        if k == "_id":
            out["id"] = str(v)
        elif isinstance(v, ObjectId):
            out[k] = str(v)
        else:
            out[k] = v
    return out


def date_str(d: dt.date) -> str:
    """Dates are stored as ISO strings (YYYY-MM-DD): timezone-free and they sort correctly."""
    return d.isoformat()
