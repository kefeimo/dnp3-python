from time import sleep
from typing import Generator

import pytest
from pydnp3 import opendnp3
from utils import get_free_port

from dnp3_python.dnp3station.master import MyMaster
from dnp3_python.dnp3station.outstation import MyOutStation

PORT = get_free_port()


@pytest.fixture(scope="function")
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


def test_send_scan_all_request(master_new, outstation_new):
    value = 0.1234
    index = 0
    outstation_new.apply_update(opendnp3.Analog(value=value), index)

    for i in range(10):
        master_new.send_scan_all_request()
        sleep(1)
        result = master_new.soe_handler.db
        print(f"{i=}, {result=}")
        if result["Analog"][index] is not None:
            break
        sleep(1)


def test_send_direct_point_command(master_new, outstation_new):
    group = 40
    variation = 4
    index = 1
    value_to_set = 12.34

    for i in range(10):
        master_new.send_direct_point_command(
            group=group, variation=variation, index=index, val_to_set=value_to_set
        )
        sleep(1)
        master_new.get_db_by_group_variation(group=group, variation=variation)
        sleep(1)
        result = master_new.soe_handler.db["AnalogOutputStatus"]
        print(f"{i=}, {result=}")
        if result[index] is not None:
            break
        sleep(1)
