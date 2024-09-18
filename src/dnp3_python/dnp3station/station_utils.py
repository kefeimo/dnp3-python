import csv
import datetime
import io
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Callable, Dict, List, Optional, Tuple, Type, TypeVar, Union

import pandas as pd
from pydnp3 import asiodnp3, asiopal, opendnp3, openpal
from pydnp3.opendnp3 import GroupVariation, GroupVariationID

from .visitors import *

stdout_stream = logging.StreamHandler(sys.stdout)
stdout_stream.setFormatter(
    logging.Formatter("%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s")
)

_log = logging.getLogger(__name__)
_log.addHandler(stdout_stream)
_log.setLevel(logging.DEBUG)
# _log.setLevel(logging.INFO)

# alias
ICollectionIndexedVal = Union[
    opendnp3.ICollectionIndexedAnalog,
    opendnp3.ICollectionIndexedBinary,
    opendnp3.ICollectionIndexedAnalogOutputStatus,
    opendnp3.ICollectionIndexedBinaryOutputStatus,
]
DbPointVal = Union[float, int, bool]
VisitorClass = Union[
    VisitorIndexedTimeAndInterval,
    VisitorIndexedAnalog,
    VisitorIndexedBinary,
    VisitorIndexedCounter,
    VisitorIndexedFrozenCounter,
    VisitorIndexedAnalogOutputStatus,
    VisitorIndexedBinaryOutputStatus,
    VisitorIndexedDoubleBitBinary,
]

MasterCmdType = Union[
    opendnp3.AnalogOutputDouble64,
    opendnp3.AnalogOutputFloat32,
    opendnp3.AnalogOutputInt32,
    opendnp3.AnalogOutputInt16,
    opendnp3.ControlRelayOutputBlock,
]

OutstationCmdType = Union[
    opendnp3.Analog,
    opendnp3.AnalogOutputStatus,
    opendnp3.Binary,
    opendnp3.BinaryOutputStatus,
]

MeasurementType = TypeVar(
    "MeasurementType", bound=opendnp3.Measurement
)  # inheritance, e.g., opendnp3.Analog,

# TODO: add validating connection logic
# TODO: add validating configuration logic
#  (e.g., check if db at outstation side is configured correctly, i.e., OutstationStackConfig)


class HandlerLogger:
    def __int__(self, logger_name="HandlerLogger"):
        self._log = logging.getLogger(logger_name)
        self.config_logger()

    def get_logger(self):
        return self._log

    def config_logger(self, log_level=logging.INFO):
        self._log.addHandler(stdout_stream)
        self._log.setLevel(log_level)


class AppChannelListener(asiodnp3.IChannelListener):
    """
    Override IChannelListener in this manner to implement application-specific channel behavior.
    """

    def __init__(self):
        super(AppChannelListener, self).__init__()

    def OnStateChange(self, state):
        _log.debug(
            "In AppChannelListener.OnStateChange: state={}".format(
                opendnp3.ChannelStateToString(state)
            )
        )


class SOEHandler(opendnp3.ISOEHandler):
    """
    Override ISOEHandler in this manner to implement application-specific sequence-of-events behavior.

    This is an interface for SequenceOfEvents (SOE) callbacks from the Master stack to the application layer.
    """

    def __init__(self, soehandler_log_level=logging.INFO, *args, **kwargs):
        super(SOEHandler, self).__init__()

        # auxiliary database
        self._gv_index_value_nested_dict: Dict[
            GroupVariation, Optional[Dict[int, DbPointVal]]
        ] = {}
        self._gv_ts_ind_val_dict: Dict[
            GroupVariation, Tuple[datetime.datetime, Optional[Dict[int, DbPointVal]]]
        ] = {}
        self._gv_last_poll_dict: Dict[GroupVariation, Optional[datetime.datetime]] = {}

        # logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config_logger(log_level=soehandler_log_level)

        # db
        self._db = self.init_db()

        # temp: TODO get rid of them
        self.visitor_dict: Dict[str, "VisitorClass"] = {}
        self.value_visitor_dict: Dict[str, ICollectionIndexedVal] = {}
        self.info_visitor_dict: Dict[str, ICollectionIndexedVal] = {"ds": "dfs"}
        self.temp_values = None

    def config_logger(self, log_level=logging.INFO):
        self.logger.addHandler(stdout_stream)
        self.logger.setLevel(log_level)

    def Process(self, info, values: ICollectionIndexedVal, *args, **kwargs):
        """
            Process measurement data.
            Note: will only evoke when there is response from outstation

        :param info: HeaderInfo
        :param values: A collection of values received from the Outstation (various data types are possible).
        """
        # print("=========Process, info.gv, values", info.gv, values)
        visitor_class_types: dict = {
            opendnp3.ICollectionIndexedBinary: VisitorIndexedBinary,
            opendnp3.ICollectionIndexedDoubleBitBinary: VisitorIndexedDoubleBitBinary,
            opendnp3.ICollectionIndexedCounter: VisitorIndexedCounter,
            opendnp3.ICollectionIndexedFrozenCounter: VisitorIndexedFrozenCounter,
            opendnp3.ICollectionIndexedAnalog: VisitorIndexedAnalog,
            opendnp3.ICollectionIndexedBinaryOutputStatus: VisitorIndexedBinaryOutputStatus,
            opendnp3.ICollectionIndexedAnalogOutputStatus: VisitorIndexedAnalogOutputStatus,
            opendnp3.ICollectionIndexedTimeAndInterval: VisitorIndexedTimeAndInterval,
        }
        visitor_class: Union[Callable, VisitorClass] = visitor_class_types[type(values)]
        visitor = visitor_class()  # init
        # hot-fix VisitorXXAnalog do not distinguish float and integer.
        if visitor_class == VisitorIndexedAnalog:
            # Parsing to Int
            if info.gv in [
                # GroupVariation.Group30Var0,
                GroupVariation.Group30Var1,
                GroupVariation.Group30Var2,
                GroupVariation.Group30Var3,
                GroupVariation.Group30Var4,
                # GroupVariation.Group32Var0,
                # GroupVariation.Group32Var1,
                GroupVariation.Group32Var2,
                GroupVariation.Group32Var3,
                GroupVariation.Group32Var4,
                GroupVariation.Group32Var5,
            ]:
                visitor = VisitorIndexedAnalogInt()
        elif visitor_class == VisitorIndexedAnalogOutputStatus:
            if info.gv in [
                # GroupVariation.Group40Var0,
                GroupVariation.Group40Var1,
                GroupVariation.Group40Var2,
                # GroupVariation.Group42Var0,
                GroupVariation.Group42Var1,
                GroupVariation.Group42Var2,
                GroupVariation.Group42Var3,
                GroupVariation.Group42Var4,
            ]:
                visitor = VisitorIndexedAnalogOutputStatusInt()
        # Note: mystery method, magic side effect to update visitor.index_and_value
        values.Foreach(visitor)

        self.visitor_dict[str(visitor_class)] = visitor
        self.value_visitor_dict[str(visitor_class)] = visitor
        # info.Foreach(visitor)
        self.info_visitor_dict[str(visitor_class)] = info
        # self.info_ = info

        # values.Foreach(visitor)

        # visitor.index_and_value: List[Tuple[int, DbPointVal]]
        for index, value in visitor.index_and_value:
            log_string = "SOEHandler.Process {0}\theaderIndex={1}\tdata_type={2}\tindex={3}\tvalue={4}"
            self.logger.debug(
                log_string.format(
                    info.gv, info.headerIndex, type(values).__name__, index, value
                )
            )
            # print(log_string.format(info.gv, info.headerIndex, type(values).__name__, index, value))

        info_gv: GroupVariation = info.gv
        visitor_ind_val: List[Tuple[int, DbPointVal]] = visitor.index_and_value

        _log.info("======== SOEHandler.Process")
        _log.info(f"{info_gv=}")
        # _log.info(f"visitor_ind_val {visitor_ind_val}")
        _log.info(f"{values=}")
        self.temp_values = values
        self._post_process(info_gv=info_gv, visitor_ind_val=visitor_ind_val)

    def _post_process(
        self, info_gv: GroupVariation, visitor_ind_val: List[Tuple[int, DbPointVal]]
    ):
        """
        SOEHandler post process logic to stage data at MasterStation side
        to improve performance: e.g., consistent output

        info_gv: GroupVariation,
        visitor_ind_val: List[Tuple[int, DbPointVal]]
        """
        # Use dict update method to mitigate delay due to asynchronous communication. (i.e., return None)
        # Also, capture unsolicited updated values.
        if not self._gv_index_value_nested_dict.get(info_gv):
            self._gv_index_value_nested_dict[info_gv] = dict(visitor_ind_val)
        else:
            self._gv_index_value_nested_dict[info_gv].update(dict(visitor_ind_val))

        # Use another layer of storage to handle timestamp related logic
        self._gv_ts_ind_val_dict[info_gv] = (
            datetime.datetime.now(),
            self._gv_index_value_nested_dict.get(info_gv),
        )
        # Use another layer of storage to handle timestamp related logic
        self._gv_last_poll_dict[info_gv] = datetime.datetime.now()

    def Start(self):
        self.logger.debug("In SOEHandler.Start====")

    def End(self):
        self.logger.debug("In SOEHandler.End")

    @property
    def gv_index_value_nested_dict(
        self,
    ) -> Dict[GroupVariation, Optional[Dict[int, DbPointVal]]]:
        return self._gv_index_value_nested_dict

    @property
    def gv_ts_ind_val_dict(self):
        return self._gv_ts_ind_val_dict

    @property
    def gv_last_poll_dict(self) -> Dict[GroupVariation, Optional[datetime.datetime]]:
        return self._gv_last_poll_dict

    @property
    def db(self) -> dict:
        """micmic DbHandler.db"""
        self._consolidate_db()
        return self._db

    @staticmethod
    def init_db(size=10):
        db = {}
        for number, gv_name in zip(
            [size, size, size, size],
            ["Analog", "AnalogOutputStatus", "Binary", "BinaryOutputStatus"],
        ):
            val_body = dict((n, None) for n in range(number))
            db[gv_name] = val_body

        return db

    def _consolidate_db(self):
        """map group variance to db with 4 keys:
        "Binary", "BinaryOutputStatus", "Analog", "AnalogOutputStatus"
        """
        pass
        # for Analog (TODO: why get GroupVariation.Group30Var6)
        _db = {
            "Analog": self._gv_index_value_nested_dict.get(GroupVariation.Group30Var6)
        }
        if _db.get("Analog"):
            self._db.update(_db)
        # for AnalogOutputStatus
        _db = {
            "AnalogOutputStatus": self._gv_index_value_nested_dict.get(
                GroupVariation.Group40Var4
            )
        }
        if _db.get("AnalogOutputStatus"):
            self._db.update(_db)
        # for Binary
        _db = {
            "Binary": self._gv_index_value_nested_dict.get(GroupVariation.Group1Var2)
        }
        if _db.get("Binary"):
            self._db.update(_db)
        # for Binary
        _db = {
            "BinaryOutputStatus": self._gv_index_value_nested_dict.get(
                GroupVariation.Group10Var2
            )
        }
        if _db.get("BinaryOutputStatus"):
            self._db.update(_db)


def collection_callback(result=None):
    """
    :type result: opendnp3.CommandPointResult
    """
    print(
        "Header: {0} | Index:  {1} | State:  {2} | Status: {3}".format(
            result.headerIndex,
            result.index,
            opendnp3.CommandPointStateToString(result.state),
            opendnp3.CommandStatusToString(result.status),
        )
    )


def command_callback(result: opendnp3.ICommandTaskResult = None):
    """
    :type result: opendnp3.ICommandTaskResult
    """
    # print("Received command result with summary: {}".format(opendnp3.TaskCompletionToString(result.summary)))
    # result.ForeachItem(collection_callback)
    pass


def restart_callback(result=opendnp3.RestartOperationResult()):
    if result.summary == opendnp3.TaskCompletion.SUCCESS:
        print(
            "Restart success | Restart Time: {}".format(
                result.restartTime.GetMilliseconds()
            )
        )
    else:
        print(
            "Restart fail | Failure: {}".format(
                opendnp3.TaskCompletionToString(result.summary)
            )
        )


def parsing_gvid_to_gvcls(gvid: GroupVariationID) -> GroupVariation:
    """Mapping gvId to GroupVariation member class

    :param opendnp3.GroupVariationID gvid: group-variance Id

    :return: GroupVariation member class.
    :rtype: opendnp3.GroupVariation

    :example:
    >>> parsing_gvid_to_gvcls(gvid=GroupVariationID(30, 6))
    GroupVariation.Group30Var6
    """
    # print("====gvId GroupVariationID", gvid)
    group: int = gvid.group
    variation: int = gvid.variation
    gv_cls: GroupVariation

    gv_cls = GroupVariationID(30, 6)  # default
    # auto parsing
    try:
        gv_cls = getattr(opendnp3.GroupVariation, f"Group{group}Var{variation}")
        assert gv_cls is not None
    except ValueError as e:
        _log.warning(f"Group{group}Var{variation} is not valid opendnp3.GroupVariation")

    return gv_cls


def parsing_gv_to_mastercmdtype(
    group: int, variation: int, val_to_set: DbPointVal
) -> MasterCmdType:
    pass
    """
    hard-coded parsing, e.g., group40, variation:4 -> opendnp3.AnalogOutputDouble64
    """
    master_cmd: MasterCmdType
    # AnalogOutput
    if group == 40:
        if not type(val_to_set) in [float, int]:
            raise ValueError(
                f"val_to_set {val_to_set} of MasterCmdType group {group}, variation {variation} invalid."
            )
        if variation == 1:
            master_cmd = opendnp3.AnalogOutputInt32()
        elif variation == 2:
            master_cmd = opendnp3.AnalogOutputInt16()
        elif variation == 3:
            master_cmd = opendnp3.AnalogOutputFloat32()
        elif variation == 4:
            master_cmd = opendnp3.AnalogOutputDouble64()
        else:
            raise ValueError(
                f"val_to_set {val_to_set} of MasterCmdType group {group} invalid."
            )

        master_cmd.value = val_to_set
    # BinaryOutput
    elif group == 10 and variation in [1, 2]:
        master_cmd = opendnp3.ControlRelayOutputBlock()
        if not type(val_to_set) is bool:
            raise ValueError(
                f"val_to_set {val_to_set} of MasterCmdType group {group}, variation {variation} invalid."
            )
        if val_to_set is True:
            master_cmd.rawCode = 3
        else:
            master_cmd.rawCode = 4
    else:
        raise ValueError(
            f"val_to_set {val_to_set} of MasterCmdType group {group} invalid."
        )

    return master_cmd


# alias
# OutstationCmdType = Union[opendnp3.Analog, opendnp3.Binary, opendnp3.AnalogOutputStatus,
#                           opendnp3.BinaryOutputStatus]  # based on asiodnp3.UpdateBuilder.Update(**args)
# MasterCmdType = Union[opendnp3.AnalogOutputDouble64,
#                       opendnp3.AnalogOutputFloat32,
#                       opendnp3.AnalogOutputInt32,
#                       opendnp3.AnalogOutputInt16,
#                       opendnp3.ControlRelayOutputBlock]


def master_to_outstation_command_parser(master_cmd: MasterCmdType) -> OutstationCmdType:
    """
    Used to parse send command to update command, e.g., opendnp3.AnalogOutputDouble64 -> AnalogOutputStatus
    """
    # return None
    if type(master_cmd) in [
        opendnp3.AnalogOutputDouble64,
        opendnp3.AnalogOutputFloat32,
        opendnp3.AnalogOutputInt32,
        opendnp3.AnalogOutputInt16,
    ]:
        return opendnp3.AnalogOutputStatus(value=master_cmd.value)
    elif type(master_cmd) is opendnp3.ControlRelayOutputBlock:
        # Note: ControlRelayOutputBlock requires to use hard-coded rawCode to retrieve value at this version.
        bi_value: bool
        if master_cmd.rawCode == 3:
            bi_value = True
        elif master_cmd.rawCode == 4:
            bi_value = False
        else:
            raise ValueError(
                f"master_cmd.rawCode {master_cmd.rawCode} is not a valid rawCode. (3: On/True, 4:Off/False."
            )
        return opendnp3.BinaryOutputStatus(value=bi_value)
    else:
        raise ValueError(
            f"master_cmd {master_cmd} with type {type(master_cmd)} is not a valid command."
        )


class DBHandler:
    """
    Work as an auxiliary database for outstation (Mimic SOEHAndler for master-station)
    """

    def __init__(
        self,
        stack_config=asiodnp3.OutstationStackConfig(
            opendnp3.DatabaseSizes.AllTypes(10)
        ),
        dbhandler_log_level=logging.INFO,
        *args,
        **kwargs,
    ):
        self.stack_config = stack_config
        self._db: dict = self.config_db(
            stack_config
        )  # TODO: ideally, this should be a dataclass

        self.logger = logging.getLogger(self.__class__.__name__)
        self.config_logger(log_level=dbhandler_log_level)
        self.dnp3_database: Dnp3Database = Dnp3Database()

    def config_logger(self, log_level=logging.INFO):
        self.logger.addHandler(stdout_stream)
        self.logger.setLevel(log_level)

    @staticmethod
    def config_db(stack_config):
        db = {}
        for number, gv_name in zip(
            [
                stack_config.dbConfig.sizes.numAnalog,
                stack_config.dbConfig.sizes.numAnalogOutputStatus,
                stack_config.dbConfig.sizes.numBinary,
                stack_config.dbConfig.sizes.numBinaryOutputStatus,
            ],
            ["Analog", "AnalogOutputStatus", "Binary", "BinaryOutputStatus"],
        ):
            val_body = dict((n, None) for n in range(number))
            db[gv_name] = val_body

        return db

    @property
    def db(self) -> dict:
        return self._db

    def process(self, command: OutstationCmdType, index: int):
        """
        Note: this method would be magically evoked when outstation apply_update,
        or receive command from master.
        command.__class__.__name__ is in ["Analog", "AnalogOutputStatus", "Binary", "BinaryOutputStatus"]
        """
        # _log.info(f"{command=}, {type(command)=}")
        # _log.info(f"index {index}")
        update_body: dict = {index: command.value}
        if self.db.get(command.__class__.__name__):
            self.db[command.__class__.__name__].update(update_body)
        else:
            self.db[command.__class__.__name__] = update_body
        # _log.info(f"========= self.db {self.db}")
        command_to_dataclass_type = {
            "Analog": "AnalogInput",
            "AnalogOutputStatus": "AnalogOutput",
            "Binary": "BinaryInput",
            "BinaryOutputStatus": "BinaryOutput",
        }
        self.dnp3_database.add_point(
            command_to_dataclass_type[command.__class__.__name__],
            index,
            command.value,
            str(datetime.datetime.now()),
            # datetime.datetime.now(),
        )


class MyLogger(openpal.ILogHandler):
    """
    Override ILogHandler in this manner to implement application-specific logging behavior.
    """

    def __init__(self):
        super(MyLogger, self).__init__()

    def Log(self, entry):
        filters = entry.filters.GetBitfield()
        location = entry.location.rsplit("/")[-1] if entry.location else ""
        message = entry.message
        _log.debug(
            "Log\tfilters={}\tlocation={}\tentry={}".format(filters, location, message)
        )


def to_flat_db(db: dict) -> dict:
    db_flat: dict = {}
    # {"Name": ["Analog_0", "Analog_1"],
    # "Value": [0.0, 0.1],
    # "Type": ["AnalogInput", "AnalogInput"],
    # "Update_at": [2024-08-05 15:39:02.275748, 2024-08-05 15:39:02.275748]}
    for k, v in db.items():
        # 'Analog': {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0}
        names = [k + "_" + str(index) for index in v.keys()]
        values = [value for value in v.values()]
        types = [k for _ in v.keys()]
        # Update_at =
        if db_flat == {}:
            db_flat = {"Name": names, "Value": values, "Type": types}
        else:
            db_flat["Name"] += names
            db_flat["Value"] += values
            db_flat["Type"] += types
    return db_flat


def to_pnnl_schema(db: dict, is_wrapped_text=True) -> pd.DataFrame:
    db_flat = to_flat_db(db)
    df_flat = pd.DataFrame(db_flat)

    def dnp3_name_mapping(default_name: str) -> str:
        point_type, point_index = default_name.split("_")[0], default_name.split("_")[1]
        if point_type == "Analog":
            schema_type = "AI"
        elif point_type == "AnalogOutputStatus":
            schema_type = "AO"
        elif point_type == "Binary":
            schema_type = "BI"
        else:  # point_type == "BinaryOutputStatus":
            schema_type = "BO"

        return f"{schema_type}-{(point_index).zfill(3)}"  # 'padding in-front with zeros up to 3 digits

    df_flat["point_name"] = df_flat["Name"].apply(lambda x: dnp3_name_mapping(x))
    df_points = pd.read_csv("/home/kefei/project/dnp3-python/dnp3-example-schema.csv")

    import textwrap

    def wrap_text(text, width):
        return "\n".join(textwrap.wrap(text, width=width))

    df_merged = pd.merge(
        df_flat[["Value", "point_name"]],
        df_points,
        left_on="point_name",
        right_on="Point",
    ).drop("point_name", axis=1)

    if is_wrapped_text:
        df_merged["Desc_Short"] = df_merged["Desc_Short"].apply(
            lambda x: wrap_text(x, width=30)
        )
    # df_merged["Value"] = df_merged["Value"].apply(lambda x: int(x))

    return df_merged


import datetime
from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class Dnp3DatabaseRecord:
    """
    Represents a record in a DNP3 database.

    Attributes:
        point_type (str): The type of point, e.g., AnalogInput, AnalogOutput.
        index (int): The index of the point in the database.
        value (str | float | bool | None): The value of the point.
        updated_at (datetime.datetime): The timestamp when the point was last updated.
        received_at (datetime.datetime): The timestamp when the point was last received.

    Example:
        >>> record = Dnp3DatabaseRecord(
                point_type="AnalogInput",
                index=1,
                value=123.45,
                updated_at=datetime.datetime.now(),
                received_at=datetime.datetime.now()
            )
    """

    point_type: str
    index: int
    value: str | float | bool | None
    updated_at: str | datetime.datetime
    # received_at: datetime.datetime


@dataclass
class Dnp3Database:
    """
    Represents a database for storing DNP3 data points.

    Attributes:
        rows (List[Dnp3DatabaseRecord]): A list of Dnp3DatabaseRecord instances.

    Example:
        >>> db = Dnp3Database()
        >>> db.add_point("AnalogInput", 1, 123.45, datetime.datetime.now())
        >>> print(db.query_by_type("AnalogInput"))
        >>> sorted_db = db.sort_by_field("index")
        >>> print(sorted_db.rows)
    """

    rows: List[Dnp3DatabaseRecord] = field(default_factory=list)

    def add_point(
        self,
        point_type: str,
        index: int,
        value: str | float | bool | None,
        updated_at: str | datetime.datetime,
        # received_at: datetime.datetime,
    ):
        """
        Adds a new point to the database.

        Args:
            point_type (str): The type of point, must be one of ["AnalogInput", "AnalogOutput", "BinaryInput", "BinaryOutput"].
            index (int): The index of the point.
            value (str | float | bool | None): The value of the point.
            updated_at (datetime.datetime): The timestamp when the point is being updated.
            received_at (datetime.datetime): The timestamp when the point is being received.

        Raises:
            ValueError: If the point_type is not valid.

        Example:
            >>> db.add_point("BinaryInput", 2, True, datetime.datetime.now(), datetime.datetime.now())
        """
        if point_type in ["AnalogInput", "AnalogOutput", "BinaryInput", "BinaryOutput"]:
            new_record = Dnp3DatabaseRecord(point_type, index, value, updated_at)
            self.rows.append(new_record)
        else:
            raise ValueError("Invalid point type")

    def query_by_type(self, point_type: str) -> "Dnp3Database":
        """
        Queries the database for all records of a specified type.

        Args:
            point_type (str): The type of points to query for.

        Returns:
            Dnp3Database: A new Dnp3Database instance containing only the records of the specified type.

        Example:
            >>> db.query_by_type("AnalogInput")
        """
        filtered_rows = [point for point in self.rows if point.point_type == point_type]
        return Dnp3Database(filtered_rows)

    def sort_by_field(
        self, field_name: str, descending: bool = False
    ) -> "Dnp3Database":
        """
        Sorts the database by a specified field.

        Args:
            field_name (str): The name of the field to sort by.
            descending (bool): Whether to sort in descending order.

        Returns:
            Dnp3Database: A new Dnp3Database instance containing the sorted records.

        Raises:
            ValueError: If the field_name does not exist in the records.

        Example:
            >>> db.sort_by_field("updated_at", descending=True)
        """
        if not self.rows:
            return Dnp3Database()
        if hasattr(self.rows[0], field_name):
            sorted_rows = sorted(
                self.rows, key=lambda x: getattr(x, field_name), reverse=descending
            )
            return Dnp3Database(sorted_rows)
        else:
            raise ValueError(f"Field {field_name} does not exist in Point data class")

    def to_csv(self, file_path: str | None = None) -> str:
        """
        Converts the database records to a CSV formatted string.

        Returns:
            str: A string containing the CSV representation of the database records.

        Example:
            >>> db = Dnp3Database()
            >>> db.add_point("AnalogInput", 1, 123.45, datetime.datetime.now(), datetime.datetime.now())
            >>> print(db.to_csv())
        """
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=["point_type", "index", "value", "updated_at"],
        )
        writer.writeheader()
        for record in self.rows:
            writer.writerow(asdict(record))

        # Ensure the file exists, if not, create it
        output_stream = output.getvalue()
        if file_path:
            try:
                with open(file_path, "w") as f:
                    f.write(output_stream)
                _log.info(f"Wrote dnp3-database to {file_path=}")
            except FileNotFoundError:
                # If the directory doesn't exist, you may want to create it
                directory = os.path.dirname(file_path)
                os.makedirs(directory, exist_ok=True)
                # After ensuring the directory exists, try writing again
                with open(file_path, "w") as f:
                    f.write(output_stream)
        return output_stream
