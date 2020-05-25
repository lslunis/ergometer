import asyncio
from data_processor import *
from util import die_unless


async def main():
    storage_root = sys.argv[1]
    cloud_broker_address = sys.argv[2]

    error_event = asyncio.Event()
    host = get_current_host(storage_root)
    die_unless(len(host) > 0, "host is empty")
    file_manager = FileManager(host, storage_root, error_event)

    # Set up cloud change manager.
    broker = BrokerClient(cloud_broker_address)
    subscriber = asyncio.create_task(change_subscriber(host, broker, file_manager))

    # # Set up the local change publisher.
    publisher = asyncio.create_task(publish_local_events(host, broker, file_manager))

    # Set up a subprocess listener
    subprocess_queue = asyncio.Queue()
    subprocess = asyncio.create_task(
        run_subprocess(subprocess_queue, "yes", ["0123456789ABCDEF"])
    )
    local_events = asyncio.create_task(
        local_event_handler(host, subprocess_queue, file_manager, 100)
    )

    await asyncio.gather(
        subscriber, publisher, subprocess, local_events,
    )


if __name__ == "__main__":
    if platform.system() == "Windows":
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
    asyncio.get_event_loop().run_until_complete(main())
