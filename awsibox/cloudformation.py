import troposphere.cloudformation as cfm

from .common import *
from .shared import (
    Parameter,
    do_no_override,
    get_endvalue,
    get_expvalue,
    get_subvalue,
    auto_get_props,
    get_condition,
    add_obj,
    auto_build_obj,
)


def CFM_Parameters(key):
    auto_build_obj(Parameter(""), getattr(cfg, key))


def CFM_Conditions(key):
    do_no_override(True)
    for n, v in getattr(cfg, key).items():
        c_Condition = {n: eval(v)}

        add_obj(c_Condition)
    do_no_override(False)


def CFM_Mappings(key):
    for n, v in getattr(cfg, key).items():
        c_Mapping = {n: v}

        cfg.Mappings.update(c_Mapping)


def CFM_Outputs(key):
    auto_build_obj(Output(""), getattr(cfg, key))


def CFM_CustomResourceReplicator(key):
    resname = "CloudFormationCustomResourceStackReplicator"
    # Parameters
    P_ReplicateRegions = Parameter(
        "CCRReplicateRegions",
        Description="Regions where to replicate - none to disable - empty for default based on env/role",
        Type="CommaDelimitedList",
    )

    add_obj(P_ReplicateRegions)

    # Resources
    R_Replicator = cfm.CustomResource(resname)

    if "LambdaCCRStackReplicator" in cfg.Resources:
        R_Replicator.DependsOn = "IAMPolicyLambdaCCRStackReplicator"
        R_Replicator.ServiceToken = GetAtt("LambdaCCRStackReplicator", "Arn")
    else:
        R_Replicator.ServiceToken = get_expvalue("LambdaCCRStackReplicator")

    for p, v in cfg.Parameters.items():
        if not p.startswith("Env"):
            value = get_endvalue(p)
        else:
            value = Ref(p)
        setattr(R_Replicator, p, value)

    add_obj(R_Replicator)


def CFM_CustomResourceLightHouse(key):
    resname = "CloudFormationCustomResourceLightHouse"
    # Parameters
    P_LightHouse = Parameter(
        "CCRLightHouse",
        Description="Enable CustomResource for LightHouse - " "empty for mapped value",
        AllowedValues=["", "yes", "no"],
    )

    add_obj(P_LightHouse)

    # Conditions
    C_LightHouse = get_condition(resname, "equals", "yes", "CCRLightHouse")

    add_obj(C_LightHouse)

    # Resources
    R_LightHouse = cfm.CustomResource(
        resname,
        Condition=resname,
        DependsOn="Service",
        ServiceToken=get_expvalue("LambdaCCRLightHouse"),
        EnvRole=Ref("EnvRole"),
        EnvApp1Version=Ref("EnvApp1Version"),
        RepoName=get_endvalue("RepoName"),
    )

    add_obj(R_LightHouse)


def CFM_CustomResourceFargateSpot(key):
    resname = "CloudFormationCustomResourceFargateSpot"
    R_FargateSpot = cfm.CustomResource(
        resname,
        Condition="FargateSpot",
        DependsOn="ServiceSpot",
        ServiceToken=get_expvalue("LambdaCCRFargateSpot"),
        ServiceArn=Ref("ServiceSpot"),
        ServiceBase=GetAtt("Service", "Name"),
        ServiceSpot=GetAtt("ServiceSpot", "Name"),
        Cluster=get_expvalue("Cluster", "ClusterStack"),
        ScalingPolicy=Ref("ApplicationAutoScalingScalingPolicyCpu"),
    )

    add_obj(R_FargateSpot)
