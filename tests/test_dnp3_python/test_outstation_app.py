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


@pytest.fixture(scope="module")
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


@pytest.fixture(scope="function")
def outstation_app() -> Generator[OutStationApplication, None, None]:
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

    yield outstation
    outstation.shutdown()


def test_apply_update(master_new, outstation_app):
    value = random.random()
    index = random.randint(0, NUMBER_OF_DB_POINTS - 1)
    outstation_app.apply_update(opendnp3.Analog(value=value), index)
    print(f"=== {index=}, {value=}")

    for i in range(10):
        result = outstation_app.db
        print(f"{i=}, {result=}")
        if result.Analog[index] != 0:
            break
        sleep(1)


def test_update_db_with_random(master_new, outstation_app):
    outstation_app.update_db_with_random()

    for i in range(10):
        result = outstation_app.db
        print(f"{i=}, {result=}")
        if result.Analog[0] != 0:
            break
        sleep(1)


def test_send_scan_all_request_passive(master_new, outstation_app):
    value = random.random()
    index = random.randint(0, NUMBER_OF_DB_POINTS - 1)
    outstation_app.apply_update(opendnp3.Analog(value=value), index)
    print(f"=== {index=}, {value=}")

    for i in range(10):
        master_new.send_scan_all_request()
        sleep(1)
        result_master = master_new.db
        print(f"{i=}, {result_master=}")
        if result_master.Analog[index] is not None:
            break
        sleep(1)


def test_apply_update_analog_input(master_new, outstation_app):
    value = random.random()
    index = random.randint(0, NUMBER_OF_DB_POINTS - 1)
    outstation_app.apply_update_analog_input(value, index)
    print(f"=== {index=}, {value=}")

    for i in range(10):
        result = outstation_app.db
        print(f"{i=}, {result=}")
        if result.Analog[index] == value:
            break
        sleep(1)
    assert result.Analog[index] == value


def test_apply_update_analog_output(master_new, outstation_app):
    value = random.random()
    index = random.randint(0, NUMBER_OF_DB_POINTS - 1)
    outstation_app.apply_update_analog_output(value, index)
    print(f"=== {index=}, {value=}")

    for i in range(10):
        result = outstation_app.db
        print(f"{i=}, {result=}")
        if result.AnalogOutputStatus[index] == value:
            break
        sleep(1)
    assert result.AnalogOutputStatus[index] == value


def test_apply_update_binary_input(master_new, outstation_app):
    value = random.choice([True, False])
    index = random.randint(0, NUMBER_OF_DB_POINTS - 1)
    outstation_app.apply_update_binary_input(value, index)
    print(f"=== {index=}, {value=}")

    for i in range(10):
        result = outstation_app.db
        print(f"{i=}, {result=}")
        if result.Binary[index] == value:
            break
        sleep(1)
    assert result.Binary[index] == value


def test_apply_update_binary_output(master_new, outstation_app):
    value = random.choice([True, False])
    index = random.randint(0, NUMBER_OF_DB_POINTS - 1)
    outstation_app.apply_update_binary_output(value, index)
    print(f"=== {index=}, {value=}")

    for i in range(10):
        result = outstation_app.db
        print(f"{i=}, {result=}")
        if result.BinaryOutputStatus[index] == value:
            break
        sleep(1)
    assert result.BinaryOutputStatus[index] == value
