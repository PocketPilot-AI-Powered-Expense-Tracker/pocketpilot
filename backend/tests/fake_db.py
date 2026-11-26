"""Minimal async wrapper around mongomock so tests run without a MongoDB server.

Only the methods PocketPilot uses are wrapped. mongomock enforces unique
indexes and raises pymongo's DuplicateKeyError, like the real server.
"""
import mongomock


class FakeCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def sort(self, *args, **kwargs):
        self._cursor = self._cursor.sort(*args, **kwargs)
        return self

    def skip(self, n):
        self._cursor = self._cursor.skip(n)
        return self

    def limit(self, n):
        self._cursor = self._cursor.limit(n)
        return self

    async def to_list(self, length=None):
        items = list(self._cursor)
        return items if length is None else items[:length]

    def __aiter__(self):
        self._iter = iter(self._cursor)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class FakeCollection:
    def __init__(self, coll):
        self._c = coll

    def find(self, *args, **kwargs):
        return FakeCursor(self._c.find(*args, **kwargs))

    def aggregate(self, pipeline, **kwargs):
        return FakeCursor(self._c.aggregate(pipeline, **kwargs))

    async def create_index(self, keys, **kwargs):
        # mongomock expires TTL documents using the real clock, but tests pin "now" to a
        # fixed date, so TTL indexes would randomly delete fresh test data. Real MongoDB
        # TTL is a background cleanup job the app never relies on, so skip it here.
        kwargs.pop("expireAfterSeconds", None)
        return self._c.create_index(keys, **kwargs)

    def __getattr__(self, name):
        attr = getattr(self._c, name)
        if not callable(attr):
            return attr

        async def wrapper(*args, **kwargs):
            return attr(*args, **kwargs)

        return wrapper


class FakeDatabase:
    def __init__(self):
        self._db = mongomock.MongoClient(tz_aware=True)["pocketpilot_test"]

    async def command(self, name, *args, **kwargs):
        return {"ok": 1.0}

    def __getattr__(self, name):
        return FakeCollection(self._db[name])

    def __getitem__(self, name):
        return FakeCollection(self._db[name])
