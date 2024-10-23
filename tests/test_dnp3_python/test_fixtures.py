from time import sleep
from typing import Generator

import pytest
from utils import get_free_port

from dnp3_python.dnp3station.master_new import MyMasterNew
from dnp3_python.dnp3station.outstation_new import MyOutStationNew

PORT = get_free_port()


# Create a pytest fixture for MyMasterNew
@pytest.fixture(scope="module")
def master_new() -> Generator[MyMasterNew, None, None]:
    # master = MyMasterNew()
    master = MyMasterNew(
        master_ip="0.0.0.0",
        outstation_ip="127.0.0.1",
        port=PORT,
        master_id=2,
        outstation_id=1,
    )
    master.start()
    yield master
    master.shutdown()


@pytest.fixture(scope="module")
def outstation_new() -> Generator[MyOutStationNew, None, None]:
    # outstation = MyOutStationNew()
    outstation = MyOutStationNew(
        outstation_ip="0.0.0.0",
        port=PORT,
        master_id=2,
        outstation_id=1,
        concurrency_hint=1,
    )
    outstation.start()
    yield outstation
    outstation.shutdown()


# Test to ensure the fixture initializes correctly
def test_master_new_initialization(master_new, outstation_new):
    assert master_new is not None
    assert outstation_new is not None

    for i in range(10):
        print(f"{i=}, {outstation_new.is_connected=}, {master_new.is_connected=}")
        if outstation_new.is_connected and master_new.is_connected:
            break
        sleep(1)
