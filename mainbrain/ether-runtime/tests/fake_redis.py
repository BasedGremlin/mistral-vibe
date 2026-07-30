"""Minimal in-memory Redis double.

Implements only the commands RedisStoreAdapter uses, with the same semantics
and return types as redis-py under ``decode_responses=True`` (str in, str out).

This exists so the adapter's LOGIC is provable offline. It is a test double,
not a Redis emulator: it does not model networking, persistence, eviction, or
concurrency. Passing against it means the adapter's state machine is correct;
it does NOT prove the adapter works against a real server.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class FakeRedis:
    def __init__(self) -> None:
        self._str: Dict[str, str] = {}
        self._hash: Dict[str, Dict[str, str]] = {}
        self._set: Dict[str, set] = {}
        self.closed = False

    # -- strings / counters -------------------------------------------------

    def get(self, key: str) -> Optional[str]:
        return self._str.get(key)

    def set(self, key: str, value: Any) -> bool:
        self._str[key] = str(value)
        return True

    def incr(self, key: str) -> int:
        value = int(self._str.get(key, "0")) + 1
        self._str[key] = str(value)
        return value

    def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            for store in (self._str, self._hash, self._set):
                if key in store:
                    del store[key]
                    removed += 1
        return removed

    # -- hashes -------------------------------------------------------------

    def hset(
        self,
        key: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        mapping: Optional[Dict[str, Any]] = None,
    ) -> int:
        bucket = self._hash.setdefault(key, {})
        written = 0
        if mapping:
            for k, v in mapping.items():
                bucket[str(k)] = str(v)
                written += 1
        if field is not None:
            bucket[str(field)] = str(value)
            written += 1
        return written

    def hget(self, key: str, field: str) -> Optional[str]:
        return self._hash.get(key, {}).get(str(field))

    def hgetall(self, key: str) -> Dict[str, str]:
        # Copy: callers mutate the store while iterating the result.
        return dict(self._hash.get(key, {}))

    def hdel(self, key: str, *fields: str) -> int:
        bucket = self._hash.get(key, {})
        removed = 0
        for field in fields:
            if str(field) in bucket:
                del bucket[str(field)]
                removed += 1
        return removed

    def hexists(self, key: str, field: str) -> bool:
        return str(field) in self._hash.get(key, {})

    def hincrby(self, key: str, field: str, amount: int = 1) -> int:
        bucket = self._hash.setdefault(key, {})
        value = int(bucket.get(str(field), "0")) + amount
        bucket[str(field)] = str(value)
        return value

    # -- sets ---------------------------------------------------------------

    def sadd(self, key: str, *members: str) -> int:
        bucket = self._set.setdefault(key, set())
        before = len(bucket)
        bucket.update(str(m) for m in members)
        return len(bucket) - before

    def smembers(self, key: str) -> set:
        return set(self._set.get(key, set()))

    # -- keyspace -----------------------------------------------------------

    def keys(self, pattern: str) -> List[str]:
        import fnmatch

        everything = set(self._str) | set(self._hash) | set(self._set)
        return sorted(k for k in everything if fnmatch.fnmatch(k, pattern))

    def ping(self) -> bool:
        return True

    def close(self) -> None:
        self.closed = True
