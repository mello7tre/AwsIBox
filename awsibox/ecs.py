import troposphere.ecs as ecs

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


def ECS_TaskDefinition(key):
    for n, v in getattr(cfg, key).items():
        if not v.get("IBOX_ENABLED", True):
            continue
        mapname = f"{key}{n}"

        # Resources
        R_TaskDefinition = ecs.TaskDefinition(mapname)
        auto_get_props(R_TaskDefinition)

        R_TaskDefinition.ContainerDefinitions = []
        for n, v in cfg.ContainerDefinitions.items():
            name = f"ContainerDefinitions{n}"  # Ex. ContainerDefinitions1
            r_Container = ecs.ContainerDefinition(name)
            auto_get_props(r_Container, indexname=n, res_obj_type="AWS::ECS::TaskDefinition")
            R_TaskDefinition.ContainerDefinitions.append(r_Container)

        add_obj([R_TaskDefinition])
