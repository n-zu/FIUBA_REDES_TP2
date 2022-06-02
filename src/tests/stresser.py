from ftp.start_server import start_server
from ftp.download import download
import random
from ftp.upload import upload
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
    #"yee.mp4"
]


def uploader():

    filename = client_files.pop(random.randint(0, len(client_files) - 1))
    logger.info(f"Uploading {filename}")
    filepath = f"tests/utils/user_files/"

    upload(ADDR[0], ADDR[1], filepath, filename, "little", 1024)


def downloader():
    filename = server_files.pop(random.randint(0, len(server_files) - 1))
    logger.info(f"Downloading {filename}")
    download_folder = "tests/utils/user_files/"

    download(ADDR[0], ADDR[1], download_folder, filename, "little", 1024)


if __name__ == "__main__":

    server_thread = threading.Thread(target=start_server, args=(ADDR[0], ADDR[1], "tests/utils/server_files/", "stop_and_wait"))
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

    server_thread.join()


