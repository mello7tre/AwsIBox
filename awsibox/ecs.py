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


def ECS_ContainerDefinition():
    Containers = []
    for n, v in cfg.ContainerDefinitions.items():
        name = f"ContainerDefinitions{n}"  # Ex. ContainerDefinitions1

        EnvValue_Out_String = []
        EnvValue_Out_Map = {}
        for m, w in v["Environment"].items():
            if m.startswith("Env"):
                continue
            envname = f"{name}Environment{m}"
            envkeyname = w["Name"]
            # parameters
            p_EnvValue = Parameter(
                f"{envname}Value",
                Description=f"{envkeyname} - empty for default based on env/role",
            )

            # If key NoParam is present skip adding Parameters
            # (usefull as they have a limited max number)
            if "NoParam" not in w:
                add_obj(p_EnvValue)

            EnvValue_Out_String.append("%s=${%s}" % (envkeyname, envkeyname))
            EnvValue_Out_Map.update({envkeyname: get_endvalue(f"{envname}Value")})

        # resources
        Container = ecs.ContainerDefinition(name)
        auto_get_props(Container, indexname=n, res_obj_type="AWS::ECS::TaskDefinition")

        if len(cfg.ContainerDefinitions) == 1:
            # parameters
            p_UseTaskCpu = Parameter(
                f"{name}UseTaskCpu",
                Description="Empty for mapped value - Use Task Cpu Value, if present, for Container Cpu",
                AllowedValues=["", "true", "false"],
            )

            add_obj(p_UseTaskCpu)

            # conditions
            c_UseTaskCpu = {
                f"{name}UseTaskCpu": And(
                    Condition("CpuTask"),
                    get_condition("", "equals", "true", f"{name}UseTaskCpu"),
                )
            }

            add_obj(c_UseTaskCpu)

            Container.Cpu = If(
                f"{name}UseTaskCpu", get_endvalue("Cpu"), get_endvalue(f"{name}Cpu")
            )
            Container.Memory = If(
                "LaunchTypeFarGate",
                get_endvalue("Memory"),
                get_endvalue(f"{name}Memory"),
            )

        Containers.append(Container)

        # outputs
        o_EnvValueOut = Output(
            f"{name}Environment",
            Value=Sub(",".join(EnvValue_Out_String), **EnvValue_Out_Map),
        )

        add_obj(o_EnvValueOut)

    return Containers


def ECS_TaskDefinition(key):
    for n, v in getattr(cfg, key).items():
        if not v.get("IBOX_ENABLED", True):
            continue
        mapname = f"{key}{n}"

        # Resources
        R_TaskDefinition = ecs.TaskDefinition(mapname)
        auto_get_props(R_TaskDefinition)
        R_TaskDefinition.ContainerDefinitions = ECS_ContainerDefinition()

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
