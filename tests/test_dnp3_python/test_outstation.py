# test_master.py
from time import sleep
from typing import Generator

import pytest
from pydnp3 import opendnp3
from utils import get_free_port

from dnp3_python.dnp3station.master import MyMaster
from dnp3_python.dnp3station.outstation import MyOutStation

PORT = get_free_port()


@pytest.fixture(scope="module")
def master_new() -> Generator[MyMaster, None, None]:
    # master = MyMasterNew()
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


@pytest.fixture(scope="function")
def outstation_new() -> Generator[MyOutStation, None, None]:
    # outstation = MyOutStationNew()
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


# Test function to verify that sending a direct point command works as expected
def test_apply_update(master_new, outstation_new):
    # Setup the conditions for the test (e.g., known state of the outstation)
    value = 0.1234
    index = 1
    outstation_new.apply_update(opendnp3.Analog(value=value), index)

    for i in range(10):
        result = outstation_new.db_handler.db
        print(f"{i=}, {result=}")
        if result["Analog"][index] != 0:
            break
        sleep(1)


# Test function to verify that sending a direct point command works as expected
def test_send_scan_all_request_passive(master_new, outstation_new):
    # Setup the conditions for the test (e.g., known state of the outstation)
    value = 0.1234
    index = 0
    outstation_new.apply_update(opendnp3.Analog(value=value), index)

    for i in range(10):
        master_new.send_scan_all_request()
        sleep(1)
        result_master = master_new.soe_handler.db
        print(f"{i=}, {result_master=}")
        if result_master["Analog"][index] is not None:
            break
        sleep(1)
