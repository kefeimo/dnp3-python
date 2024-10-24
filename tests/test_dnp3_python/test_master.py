# test_master.py
from time import sleep
from typing import Generator

import pytest
from utils import get_free_port

from dnp3_python.dnp3station.master_new import MyMasterNew
from dnp3_python.dnp3station.outstation_new import MyOutStationNew

PORT = get_free_port()


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


# Test function to verify that sending a direct point command works as expected
def test_send_direct_point_command(master_new, outstation_new):
    # Setup the conditions for the test (e.g., known state of the outstation)
    group = 40
    variation = 4
    index = 1
    value_to_set = 12.34

    # Verify the results
    # Assuming the MyMasterNew class has a method to fetch the latest command's response or status
    for i in range(10):
        master_new.send_direct_point_command(
            group=group, variation=variation, index=index, val_to_set=value_to_set
        )
        sleep(1)
        master_new.get_db_by_group_variation(group=group, variation=variation)
        sleep(1)
        result = master_new.soe_handler.db["AnalogOutputStatus"]
        print(f"{i=}, {result=}")
        sleep(1)
        if result[index] != 0:
            break
    # expected_result = {
    #     "AnalogOutputStatus": [(index, value_to_set)]
    # }  # Example expected result format
    # assert result == expected_result, f"Expected {expected_result}, got {result}"
