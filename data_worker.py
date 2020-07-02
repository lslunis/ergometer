import asyncio
import sys

from .database import database_updater
from .data_processor import (
    BrokerClient,
    FileManager,
    change_subscriber,
    exit_watcher,
    get_current_host,
    local_event_handler,
    publish_local_events,
    run_subprocess,
)
from .util import die_unless


async def data_worker(model):
    storage_root = sys.argv[1]
    cloud_broker_address = sys.argv[2]

    error_event = asyncio.Event()
    host = get_current_host(storage_root)
    die_unless(len(host) > 0, "host is empty")
    file_manager = FileManager(host, storage_root, error_event)
    broker = BrokerClient(cloud_broker_address)

    try:
        await asyncio.gather(
            change_subscriber(host, broker, file_manager),
            publish_local_events(host, broker, file_manager),
            run_subprocess(model.push_local_event, "yes", ["0123456789ABCDEF"]),
            local_event_handler(host, model.pop_local_event, file_manager, 100),
            database_updater(model.Session, model.update_cache, file_manager.subscribe),
            exit_watcher(model.is_exiting),
        )
    except SystemExit:
        return


def run_loop(model):
    asyncio.run(data_worker(model))
