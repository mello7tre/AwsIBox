import troposphere.scheduler as scheduler

from .common import *
from .shared import (
    Parameter,
    get_endvalue,
    get_expvalue,
    get_subvalue,
    auto_get_props,
    get_condition,
    add_obj,
)


def SCHEDULER_Schedule(key):
    for n, v in getattr(cfg, key).items():
        if not v.get("IBOX_ENABLED", True):
            continue

        resname = f"{key}{n}"
        ibox_lo_cfg = v.get("IBOX_LINKED_OBJ", {})
        if isinstance(ibox_lo_cfg, str):
            ibox_lo_cfg = {"Base": ibox_lo_cfg}

        # resources
        target = v["Target"]
        R_Target = scheduler.Target(f"{resname}Target")

        if target["Type"] == "Lambda":
            # create ad hoc IBOX_LINKED_OBJ
            lo_cfg = {
                "Key": "LambdaPermission",
                "Type": "SchedulerSchedule",
                "Name": f"LambdaPermission{resname}",
                "Conf": {
                    "IBOX_RESNAME": f"LambdaPermission{resname}",
                    "IBOX_LINKED_OBJ_NAME": target["Arn"],
                    "IBOX_LINKED_OBJ_INDEX": f"GetAtt('{resname}', 'Arn')",
                },
            }
            ibox_lo_cfg[n] = lo_cfg
        if target["Type"] == "ECSCluster":
            # add common "fixed" props
            auto_get_props(
                R_Target, mapname="SchedulerScheduleTargetECSCluster", indexname=m, res_obj_type="AWS::Scheduler::Schedule")

        getattr(cfg, resname).update({"IBOX_LINKED_OBJ": ibox_lo_cfg})
        R_Schedule = scheduler.Schedule(resname)
        auto_get_props(R_Schedule, indexname=n)

        add_obj(R_Schedule)
