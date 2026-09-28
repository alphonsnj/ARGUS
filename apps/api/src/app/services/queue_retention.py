from typing import cast

from redis import Redis

# Compute the low-water mark and trim in one Redis transaction. No XACK/XREADGROUP
# or group creation can interleave and invalidate the pending/delivered boundary.
_TRIM = """
if redis.call('EXISTS', KEYS[1]) == 0 then return 0 end
local groups = redis.call('XINFO', 'GROUPS', KEYS[1])
if #groups == 0 then return 0 end
local function number_less(a, b)
    if #a ~= #b then return #a < #b end
    return a < b
end
local function id_less(a, b)
    local am, as = string.match(a, '^(%d+)%-(%d+)$')
    local bm, bs = string.match(b, '^(%d+)%-(%d+)$')
    if am == bm then return number_less(as, bs) end
    return number_less(am, bm)
end
local now = redis.call('TIME')
local cutoff_ms = tonumber(now[1]) * 1000 - tonumber(ARGV[1]) * 1000
if cutoff_ms <= 0 then return 0 end
local boundary = string.format('%.0f', cutoff_ms) .. '-0'
for _, group in ipairs(groups) do
    local name, delivered
    for i = 1, #group, 2 do
        if group[i] == 'name' then name = group[i + 1] end
        if group[i] == 'last-delivered-id' then delivered = group[i + 1] end
    end
    if not name or not delivered then return 0 end
    if id_less(delivered, boundary) then boundary = delivered end
    local pending = redis.call('XPENDING', KEYS[1], name)
    if pending[1] > 0 and id_less(pending[2], boundary) then
        boundary = pending[2]
    end
end
-- Approximate trimming only removes complete nodes below the safe boundary.
-- Bound work per invocation instead of blocking Redis on an unbounded backlog.
return redis.call('XTRIM', KEYS[1], 'MINID', '~', boundary, 'LIMIT', 1000)
"""


def trim_completed(redis: Redis, stream: str, retention_seconds: int) -> int:
    """Retain pending/undelivered messages in every group and recent history."""
    if retention_seconds <= 0:
        return 0
    return int(cast(int, redis.eval(_TRIM, 1, stream, str(retention_seconds))))
