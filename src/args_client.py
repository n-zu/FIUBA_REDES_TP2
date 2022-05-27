import argparse


def args_client():
    first = '%(prog)s  [ - h ] [ - v | -q ] [ - H ADDR ] '
    second = '[ - p PORT ] [ - d FILEPATH ] [ - n FILENAME ]'
    parser = argparse.ArgumentParser(
        description='< command description >',
        usage=first + second)

    group = parser.add_mutually_exclusive_group()

    group.add_argument(
        "-v", "--verbose", help="increase output verbosity",
        action="store_true")
    group.add_argument(
        "-q", "--quiet", help="decrease output verbosity",
        action="store_true")
    parser.add_argument(
        "-H", "--host", help="server IP address", type=str, metavar="")
    parser.add_argument(
        "-p", "--port", help="server port", type=str, metavar="")
    parser.add_argument(
        "-d", "--dst", help="destination file path", type=str, metavar="")
    parser.add_argument(
        "-n", "--name", help="file name", type=str, metavar="")
    return parser.parse_args()
