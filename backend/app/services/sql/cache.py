import difflib
import hashlib
import re
import time
from collections import OrderedDict
from typing import Optional

from app.config import (
    SQL_CACHE_ENABLED,
    SQL_CACHE_FUZZY_THRESHOLD,
    SQL_CACHE_MAX_ENTRIES,
    SQL_CACHE_TTL_SECONDS,
    SQL_INTENT_ENHANCE,
    SQL_INTENT_REFINE,
)


def normalize_query_for_cache(text: str) -> str:
    s = (text or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s.rstrip("?.!,")


def normalize_sql_for_cache(sql: str) -> str:
    return re.sub(r"\s+", " ", (sql or "").strip().lower())


def build_sql_cache_key(
    schema_id: str,
    schema_updated_at: int,
    sql_provider: str,
    model: str,
    intent: str,
    normalized_query: str,
    last_sql: Optional[str],
) -> str:
    parts = [
        schema_id,
        str(schema_updated_at),
        sql_provider,
        model,
        intent,
        normalized_query,
    ]
    if intent in (SQL_INTENT_REFINE, SQL_INTENT_ENHANCE) and last_sql:
        sql_hash = hashlib.sha256(normalize_sql_for_cache(last_sql).encode()).hexdigest()[:16]
        parts.append(sql_hash)
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def build_sql_cache_fuzzy_bucket(
    schema_id: str,
    schema_updated_at: int,
    sql_provider: str,
    model: str,
    intent: str,
    last_sql: Optional[str],
) -> str:
    base = f"{schema_id}|{schema_updated_at}|{sql_provider}|{model}|{intent}"
    if intent in (SQL_INTENT_REFINE, SQL_INTENT_ENHANCE) and last_sql:
        sql_hash = hashlib.sha256(normalize_sql_for_cache(last_sql).encode()).hexdigest()[:16]
        return f"{base}|{sql_hash}"
    return base


class _SqlCacheEntry:
    __slots__ = ("sql", "expires_at", "normalized_query", "fuzzy_bucket")

    def __init__(
        self,
        sql: str,
        expires_at: float,
        normalized_query: str,
        fuzzy_bucket: str,
    ):
        self.sql = sql
        self.expires_at = expires_at
        self.normalized_query = normalized_query
        self.fuzzy_bucket = fuzzy_bucket


class SqlResponseCache:
    """In-memory LRU cache for validated SQL responses."""

    def __init__(self, max_entries: int, ttl_seconds: int, fuzzy_threshold: float):
        self._max_entries = max(1, max_entries)
        self._ttl_seconds = max(0, ttl_seconds)
        self._fuzzy_threshold = fuzzy_threshold
        self._entries: OrderedDict[str, _SqlCacheEntry] = OrderedDict()

    def _evict_expired(self) -> None:
        if self._ttl_seconds <= 0:
            return
        now = time.time()
        expired = [k for k, e in self._entries.items() if e.expires_at <= now]
        for key in expired:
            self._entries.pop(key, None)

    def _touch(self, key: str) -> None:
        entry = self._entries.pop(key)
        self._entries[key] = entry

    def get(
        self,
        cache_key: str,
        normalized_query: str,
        fuzzy_bucket: str,
    ) -> Optional[str]:
        if not SQL_CACHE_ENABLED:
            return None
        self._evict_expired()
        entry = self._entries.get(cache_key)
        if entry is not None:
            if self._ttl_seconds > 0 and entry.expires_at <= time.time():
                self._entries.pop(cache_key, None)
            else:
                self._touch(cache_key)
                print(f"[sql-cache] exact hit key={cache_key[:12]}...")
                return entry.sql

        if self._fuzzy_threshold >= 1.0:
            return None

        best_ratio = 0.0
        best_key: Optional[str] = None
        for key, candidate in list(self._entries.items()):
            if candidate.fuzzy_bucket != fuzzy_bucket:
                continue
            if self._ttl_seconds > 0 and candidate.expires_at <= time.time():
                continue
            ratio = difflib.SequenceMatcher(
                None, normalized_query, candidate.normalized_query
            ).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_key = key

        if best_key and best_ratio >= self._fuzzy_threshold:
            self._touch(best_key)
            print(f"[sql-cache] fuzzy hit ratio={best_ratio:.3f} key={best_key[:12]}...")
            return self._entries[best_key].sql
        return None

    def put(
        self,
        cache_key: str,
        sql: str,
        normalized_query: str,
        fuzzy_bucket: str,
    ) -> None:
        if not SQL_CACHE_ENABLED:
            return
        self._evict_expired()
        expires_at = (
            time.time() + self._ttl_seconds if self._ttl_seconds > 0 else float("inf")
        )
        if cache_key in self._entries:
            self._entries.pop(cache_key)
        self._entries[cache_key] = _SqlCacheEntry(
            sql=sql,
            expires_at=expires_at,
            normalized_query=normalized_query,
            fuzzy_bucket=fuzzy_bucket,
        )
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)


sql_response_cache = SqlResponseCache(
    SQL_CACHE_MAX_ENTRIES,
    SQL_CACHE_TTL_SECONDS,
    SQL_CACHE_FUZZY_THRESHOLD,
)
