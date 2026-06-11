import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError

from assistant_shared.queue import ControlMessage, describe_redis_target, dequeue_run, wait_control


class TimeoutRedis:
    async def brpop(self, key: str, timeout: int):
        raise TimeoutError("Timeout reading from redis")


class TimeoutThenMessageRedis:
    def __init__(self):
        self.calls = 0

    async def brpop(self, key: str, timeout: int):
        self.calls += 1
        if self.calls == 1:
            raise TimeoutError("Timeout reading from redis")
        return key, ControlMessage(type="approval_resolved", status="approved").model_dump_json()


class ConnectionErrorRedis:
    async def brpop(self, key: str, timeout: int):
        raise RedisConnectionError("Error while reading from upstash : connection aborted")


class ConnectionErrorThenMessageRedis:
    def __init__(self):
        self.calls = 0

    async def brpop(self, key: str, timeout: int):
        self.calls += 1
        if self.calls == 1:
            raise RedisConnectionError("Error while reading from upstash : connection aborted")
        return key, ControlMessage(type="approval_resolved", status="approved").model_dump_json()


@pytest.mark.asyncio
async def test_dequeue_run_treats_redis_timeout_as_empty_poll():
    assert await dequeue_run(TimeoutRedis(), timeout=5) is None


@pytest.mark.asyncio
async def test_wait_control_retries_redis_timeout_until_deadline():
    redis = TimeoutThenMessageRedis()

    msg = await wait_control(redis, "run-1", timeout=5)

    assert msg == ControlMessage(type="approval_resolved", status="approved")
    assert redis.calls == 2


@pytest.mark.asyncio
async def test_dequeue_run_treats_connection_error_as_empty_poll():
    # Upstash drops idle TLS connections; a blip must not kill the worker loop.
    assert await dequeue_run(ConnectionErrorRedis(), timeout=5) is None


@pytest.mark.asyncio
async def test_wait_control_retries_connection_error_until_deadline():
    redis = ConnectionErrorThenMessageRedis()

    msg = await wait_control(redis, "run-1", timeout=5)

    assert msg == ControlMessage(type="approval_resolved", status="approved")
    assert redis.calls == 2


def test_describe_redis_target_redacts_credentials():
    description = describe_redis_target("rediss://default:secret@example.upstash.io:6379")

    assert description == "rediss://example.upstash.io:6379"
    assert "secret" not in description
    assert "default" not in description
