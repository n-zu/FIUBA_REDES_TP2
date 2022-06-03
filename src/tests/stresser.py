from start_server import start_server, stop_event
from download import download
import random
from upload import upload
import threading
from loguru import logger

ADDR = ("127.0.0.1", 1234)

server_files = [
    "bee_script.txt",
    "doc.doc",
    "lorem_ipsum.txt",
]
client_files = [
    "tc.html",
    "traceroute.txt",
    # "yee.mp4"
]


def uploader():

    filename = client_files.pop(random.randint(0, len(client_files) - 1))
    logger.info(f"Uploading {filename}")
    filepath = "tests/utils/user_files/"

    upload(
        ADDR[0],
        ADDR[1],
        filepath,
        filename,
        "little",
        1024,
        "selective_repeat",
    )


def downloader():
    filename = server_files.pop(random.randint(0, len(server_files) - 1))
    logger.info(f"Downloading {filename}")
    download_folder = "tests/utils/user_files/"

    download(
        ADDR[0],
        ADDR[1],
        download_folder,
        filename,
        "little",
        1024,
        "selective_repeat",
    )


if __name__ == "__main__":

    server_thread = threading.Thread(
        target=start_server,
        args=(
            ADDR[0],
            ADDR[1],
            "tests/utils/server_files/",
            "selective_repeat",
        ),
    )
    server_thread.start()

    threads = []
    for i in range(3):
        if random.randint(0, 1) == 0:
            thread = threading.Thread(target=uploader)
        else:
            thread = threading.Thread(target=downloader)
        threads.append(thread)
        thread.start()

    for t in threads:
        t.join()

    stop_event.set()
    server_thread.join()
