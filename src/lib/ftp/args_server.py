import argparse


def args_server():
    first = "%(prog)s  [ - h ] [ - v | -q ] [ - H ADDR ] "
    second = "[ - p PORT ] [ - s DIRPATH ]"

    parser = argparse.ArgumentParser(
        description="< command description >", usage=first + second
    )

    group = parser.add_mutually_exclusive_group()

    group.add_argument(
        "-v",
        "--verbose",
        help="increase output verbosity",
        action="store_true",
    )
    group.add_argument(
        "-q", "--quiet", help="decrease output verbosity", action="store_true"
    )

    parser.add_argument(
        "-H",
        "--host",
        help="service IP address",
        type=str,
        metavar="",
        required=True,
    )
    parser.add_argument(
        "-p",
        "--port",
        help="service port",
        type=str,
        metavar="",
        required=True,
    )
    parser.add_argument(
        "-s",
        "--storage",
        help="storage dir path",
        type=str,
        metavar="",
        required=True,
    )

    return parser.parse_args()
