from time import sleep
from typing import Generator

import pytest
from utils import get_free_port

from dnp3_python.dnp3station.master import MasterApplication, MyMaster
from dnp3_python.dnp3station.outstation import MyOutStation, OutStationApplication

PORT = get_free_port()


@pytest.fixture(scope="module")
def master_new() -> Generator[MyMaster, None, None]:
    master = MyMaster(
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
def outstation_new() -> Generator[MyOutStation, None, None]:
    outstation = MyOutStation(
        outstation_ip="0.0.0.0",
        port=PORT,
        master_id=2,
        outstation_id=1,
        concurrency_hint=1,
    )
    outstation.start()
    yield outstation
    outstation.shutdown()


def test_station_new_initialization(master_new, outstation_new):
    assert master_new is not None
    assert outstation_new is not None

    for i in range(10):
        print(f"{i=}, {outstation_new.is_connected=}, {master_new.is_connected=}")
        if outstation_new.is_connected and master_new.is_connected:
            break
        sleep(1)


# @pytest.fixture(scope="function")
# def master_app() -> Generator[MasterApplication, None, None]:
#     master = MasterApplication(
#         master_ip="0.0.0.0",
#         outstation_ip="127.0.0.1",
#         port=PORT,
#         master_id=2,
#         outstation_id=1,
#     )
#     master.start()
#     yield master
#     master.shutdown()


# @pytest.fixture(scope="function")
# def outstation_app() -> Generator[OutStationApplication, None, None]:
#     outstation = OutStationApplication(
#         outstation_ip="0.0.0.0",
#         port=PORT,
#         master_id=2,
#         outstation_id=1,
#         concurrency_hint=1,
#     )
#     outstation.start()
#     yield outstation
#     outstation.shutdown()


# def test_station_application_new_initialization(master_app, outstation_app):
#     assert master_app is not None
#     assert outstation_app is not None

#     for i in range(10):
#         print(f"{i=}, {outstation_app.is_connected=}, {master_app.is_connected=}")
#         if outstation_app.is_connected and master_app.is_connected:
#             break
#         sleep(1)
