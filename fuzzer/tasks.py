import redis
from celery import Celery

from .fuzzer import Fuzzer, EarlyCrash

import os
import time
import redis
import logging
import cPickle as pickle
import driller.config as config

l = logging.getLogger("fuzzer.tasks")

backend_url = "redis://%s:%d" % (config.REDIS_HOST, config.REDIS_PORT)
app = Celery('tasks', broker=config.BROKER_URL, backend=backend_url)
app.conf.CELERY_ROUTES = config.CELERY_ROUTES

@app.task
def fuzz(binary):

    l.info("beginning to fuzz \"%s\"", binary)

    binary_path = os.path.join(config.BINARY_DIR, binary)
    fuzzer = Fuzzer(binary_path, config.FUZZER_WORK_DIR, config.FUZZER_INSTANCES)

    early_crash = False
    try:
        fuzzer.start()

        # start the fuzzer and poll for a crash or timeout
        while not fuzzer.found_crash() and not fuzzer.timed_out():
            time.sleep(config.CRASH_CHECK_INTERVAL)

        # make sure to kill the fuzzers when we're done
        fuzzer.kill()

    except EarlyCrash:
        l.info("binary crashed on dummy testcase, moving on...")
        early_crash = True

    if fuzzer.found_crash() or early_crash:
        redis_inst = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, db=config.REDIS_DB)
        redis_inst.publish("crashes", binary)


    return fuzzer.found_crash() or early_crash