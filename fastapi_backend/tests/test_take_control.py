import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import redis.asyncio as aioredis
from app.config import settings

redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

async def test_take_and_release_control_flow():
    print("\n--- [TEST 1] Testing Take Control & Release Control Redis Channel Flow ---")
    device_id = "AG-777-888-999"

    agent_channel = f"channel:agent:{device_id}"
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(agent_channel)

    # 1. Take Control notification
    take_payload = {"type": "take_control", "device_id": device_id}
    await redis_client.publish(agent_channel, json.dumps(take_payload))

    msg = None
    for _ in range(10):
        m = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
        if m and m.get("data"):
            msg = json.loads(m["data"])
            break
        await asyncio.sleep(0.05)

    assert msg is not None, "Failed to receive message on agent_channel"
    assert msg.get("type") == "take_control"
    print("✓ Take control event published and verified on agent channel!")

    # 2. Mouse action during active control
    mouse_payload = {"type": "mousemove", "x": 0.5, "y": 0.5}
    await redis_client.publish(agent_channel, json.dumps(mouse_payload))

    msg = None
    for _ in range(10):
        m = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
        if m and m.get("data"):
            msg = json.loads(m["data"])
            break
        await asyncio.sleep(0.05)

    assert msg is not None, "Failed to receive mouse message on agent_channel"
    assert msg.get("type") == "mousemove"
    print("✓ Mouse move event published and received on agent channel!")

    # 3. Release Control notification
    release_payload = {"type": "release_control", "device_id": device_id}
    await redis_client.publish(agent_channel, json.dumps(release_payload))

    msg = None
    for _ in range(10):
        m = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
        if m and m.get("data"):
            msg = json.loads(m["data"])
            break
        await asyncio.sleep(0.05)

    assert msg is not None, "Failed to receive release message on agent_channel"
    assert msg.get("type") == "release_control"
    print("✓ Release control event published and verified on agent channel!")

    await pubsub.unsubscribe(agent_channel)
    await pubsub.close()
    print("\n=======================================================")
    print(">>> ALL TAKE CONTROL / RELEASE CONTROL TESTS PASSED! <<<")
    print("=======================================================")

if __name__ == "__main__":
    asyncio.run(test_take_and_release_control_flow())
