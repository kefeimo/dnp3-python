import random
from time import sleep
from typing import Generator

import pytest
from pydnp3 import opendnp3
from utils import get_free_port

from dnp3_python.dnp3station.master import MasterApplication
from dnp3_python.dnp3station.outstation import OutStationApplication

PORT = get_free_port()
NUMBER_OF_DB_POINTS = 10


@pytest.fixture(scope="function")
def master_new() -> Generator[MasterApplication, None, None]:
    master = MasterApplication(
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
def outstation_new() -> Generator[OutStationApplication, None, None]:
    outstation = OutStationApplication(
        outstation_ip="0.0.0.0",
        port=PORT,
        master_id=2,
        outstation_id=1,
        concurrency_hint=1,
        numAnalog=NUMBER_OF_DB_POINTS,
        numAnalogOutputStatus=NUMBER_OF_DB_POINTS,
        numBinary=NUMBER_OF_DB_POINTS,
        numBinaryOutputStatus=NUMBER_OF_DB_POINTS,
    )
    outstation.start()
    # outstation.update_db_with_random()

    yield outstation
    outstation.shutdown()


def test_send_scan_all_request(master_new, outstation_new):
    value = random.random()
    index = random.randint(0, NUMBER_OF_DB_POINTS - 1)
    outstation_new.apply_update(opendnp3.Analog(value=value), index)
    print(f"=== {index=}, {value=}")

    for i in range(10):
        master_new.send_scan_all_request()
        sleep(1)
        result = master_new.my_master.soe_handler.db
        print(f"{i=}, {result=}")
        if result["Analog"][index] is not None:
            break
        sleep(1)


def test_send_direct_point_command(master_new, outstation_new):
    group = 40
    variation = 4
    value = random.random()
    index = random.randint(0, NUMBER_OF_DB_POINTS - 1)
    print(f"=== {index=}, {value=}")

    for i in range(10):
        master_new.send_direct_point_command(
            group=group, variation=variation, index=index, val_to_set=value
        )
        sleep(1)
        master_new.get_db_by_group_variation(group=group, variation=variation)
        sleep(1)
        result = master_new.my_master.soe_handler.db["AnalogOutputStatus"]
        print(f"{i=}, {result=}")
        if result[index] == value:
            break
        sleep(1)
    assert result[index] == value


def test_send_direct_analog_output_point_command(master_new, outstation_new):
    value = random.random()
    index = random.randint(0, NUMBER_OF_DB_POINTS - 1)
    print(f"=== {index=}, {value=}")

    for i in range(10):
        master_new.send_direct_analog_output_point_command(index, value)
        sleep(1)
        master_new.send_scan_all_request()
        sleep(1)
        result = master_new.db.AnalogOutputStatus
        print(f"{i=}, {result=}")
        if result[index] == value:
            break
        sleep(1)
    assert result[index] == value


def test_send_direct_binary_output_point_command(master_new, outstation_new):
    value = random.choice([True, False])
    index = random.randint(0, NUMBER_OF_DB_POINTS - 1)
    print(f"=== {index=}, {value=}")

    for i in range(10):
        master_new.send_direct_binary_output_point_command(index, value)
        sleep(1)
        master_new.send_scan_all_request()
        sleep(1)
        result = master_new.db.BinaryOutputStatus
        print(f"{i=}, {result=}")
        if result[index] == value:
            break
        sleep(1)
    assert result[index] == value
