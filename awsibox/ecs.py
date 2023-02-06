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
from .ec2 import SecurityGroupEcsService, SecurityGroupRuleEcsService


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


def ECS_Service(key):
    # Resources
    R_SG = SecurityGroupEcsService("SecurityGroupEcsService")
    if "External" in cfg.LoadBalancer:
        SGRule = SecurityGroupRuleEcsService(scheme="External")
        R_SG.SecurityGroupIngress.append(SGRule)

    if "Internal" in cfg.LoadBalancer:
        SGRule = SecurityGroupRuleEcsService(scheme="Internal")
        R_SG.SecurityGroupIngress.append(SGRule)

    add_obj(R_SG)

    for n, v in getattr(cfg, key).items():
        if not v["IBOX_ENABLED"]:
            continue
        mapname = f"{key}{n}"

        # delete not used LoadBalancers configuration, so that auto_get_props
        # do not find it
        for m in ["External", "Internal"]:
            if m not in cfg.LoadBalancer:
                del v["LoadBalancers"][m]
        if not v["LoadBalancers"]:
            # delete if empty to maintain compatibility with previous conf
            del v["LoadBalancers"]

        r_Service = ecs.Service(mapname)
        auto_get_props(r_Service)

        if cfg.LoadBalancer:
            r_Service.Role = If(
                "NetworkModeAwsVpc", Ref("AWS::NoValue"), get_expvalue("RoleECSService")
            )

        # When creating a service that specifies multiple target groups,
        # the Amazon ECS service-linked role must be created.
        # The role is created by omitting the Role property
        # in AWS CloudFormation
        if all(k in cfg.LoadBalancer for k in ["External", "Internal"]):
            r_Service.Role = Ref("AWS::NoValue")

        add_obj(r_Service)
