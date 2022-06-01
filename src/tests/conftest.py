import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--runslow", action="store_true", default=False, help="run slow tests"
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: mark test as slow to run")
    config.addinivalue_line("markers", "ignore: dont run this test")


def pytest_collection_modifyitems(config, items):

    runslow = config.getoption("--runslow")

    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    skip_ignore = pytest.mark.skip(reason="this test is ignored")

    for item in items:

        if "ignore" in item.keywords:
            item.add_marker(skip_ignore)

        if "slow" in item.keywords and not runslow:
            item.add_marker(skip_slow)
