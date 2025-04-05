import os
import socket
import secrets
from typing import Union, Optional

import redis
from sources import logger

class Queue:

    LISTING_TEMPLATE = "{topic}:listing:{tid}"
    METRICS_TEMPLATE = "{topic}:metrics:{tid}"
    PENDING_TASKS_TEMPLATE = "{topic}:pending"
    WORKING_TASKS_TEMPLATE = "{topic}:working"

    def __init__(self, topic: str):
        self.topic = topic
        self.pending_tasks = Queue.PENDING_TASKS_TEMPLATE.format(topic=topic)
        self.working_tasks = Queue.WORKING_TASKS_TEMPLATE.format(topic=topic)

        kwargs = dict()
        kwargs["host"] = os.getenv("REDIS_HOST", "localhost")
        kwargs["port"] = int(os.getenv("REDIS_PORT", "6379"))
        kwargs["username"] = os.getenv("REDIS_USERNAME", None)
        kwargs["password"] = os.getenv("REDIS_PASSWORD", None)
        kwargs["decode_responses"] = True
        kwargs["retry_on_timeout"] = True
        kwargs["socket_connect_timeout"] = 5

        self.redis = redis.Redis(**kwargs)
        try:
            self.redis.ping()
            logger.info(f"Connected to Redis server at {kwargs['host']}:{kwargs['port']}.")
        except redis.ConnectionError:
            raise Exception("Could not connect to Redis server. Please check your connection settings.")

    def create(self, params: dict) -> str:
        tid = secrets.token_hex(8)
        listing = Queue.LISTING_TEMPLATE.format(topic=self.topic, tid=tid)
        with self.redis.pipeline() as pipe:
            pipe.hset(listing, mapping=params)
            pipe.rpush(self.pending_tasks, tid)
            pipe.execute()
        logger.info(f"Created task {tid} in topic '{self.topic}'.")
        return tid

    def acquire(self) -> Optional[Union[str, dict]]:
        with self.redis.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(self.pending_tasks)
                    tid = self.redis.lindex(self.pending_tasks, 0)
                    if tid is None:
                        logger.info(f"No pending tasks in topic '{self.topic}'.")
                        pipe.unwatch()
                        return None
                    listing = Queue.LISTING_TEMPLATE.format(topic=self.topic, tid=tid)
                    params = self.redis.hgetall(listing)
                    if not params:
                        logger.error(f"Task {tid} in topic '{self.topic}' has no parameters.")
                        pipe.unwatch()
                        continue
                    pipe.multi()
                    pipe.lpop(self.pending_tasks)
                    pipe.sadd(self.working_tasks, tid)
                    metrics = Queue.METRICS_TEMPLATE.format(topic=self.topic, tid=tid)
                    timestamp = self.redis.time()[0]
                    pipe.hset(metrics, "heartbeat", timestamp)
                    pipe.hset(metrics, "last-acquired", timestamp)
                    pipe.hset(metrics, "hostname", socket.gethostname())
                    pipe.hset(metrics, "pid", os.getpid())
                    pipe.execute()
                    logger.info(f"Acquired task {tid} from topic '{self.topic}'.")
                    return tid, params
                except redis.WatchError:
                    continue

    def update(self, tid: str, records: dict) -> None:
        with self.redis.pipeline() as pipe:
            metrics = Queue.METRICS_TEMPLATE.format(topic=self.topic, tid=tid)
            timestamp = self.redis.time()[0]
            pipe.hset(metrics, "heartbeat", timestamp)
            for key, val in records.items():
                pipe.hset(metrics, key, val)
            pipe.execute()
            logger.info(f"Updated task {tid} in topic '{self.topic}' with records.")

    def release(self, tid: str) -> None:
        with self.redis.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(self.working_tasks)
                    if not self.redis.sismember(self.working_tasks, tid):
                        logger.error(f"Task {tid} is not in working tasks for topic '{self.topic}'.")
                        return
                    pipe.multi()
                    pipe.srem(self.working_tasks, tid)
                    metrics = Queue.METRICS_TEMPLATE.format(topic=self.topic, tid=tid)
                    timestamp = self.redis.time()[0]
                    pipe.hset(metrics, "last-released", timestamp)
                    pipe.execute()
                    logger.info(f"Released task {tid} from topic '{self.topic}'.")
                    return
                except redis.WatchError:
                    continue
