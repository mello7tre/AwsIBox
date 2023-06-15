import troposphere.cloudformation as cfm

from ..common import *
from ..shared import (
    Parameter,
    do_no_override,
    get_endvalue,
    get_expvalue,
    # need it even if not directly used cause eval in CFM_Conditions
    get_condition,
    add_obj,
    auto_build_obj,
)


def mapping_EnvRegion():
    RP = copy.deepcopy(cfg.RP_map)

    for env in list(RP):
        rvalue = RP[env]
        for region in list(rvalue.keys()):
            for key in cfg.mappedvalues:
                if key not in RP[env][region]:
                    # get base/global value
                    try:
                        RP[env][region][key] = getattr(cfg, key)
                    except Exception:
                        pass
            # delete empty mappings CF do not like them
            if not RP[env][region]:
                del RP[env][region]
        if not RP[env]:
            del RP[env]

    return RP


def mapping_EC2():
    mappings = {}
    mappings["InstanceTypes"] = {}

    for i in cfg.INSTANCE_LIST:
        mappings["InstanceTypes"].update(
            {
                i: {
                    "InstaceEphemeral0": "1"
                    if i in cfg.EPHEMERAL_MAP["InstaceEphemeral0"]
                    else "0",
                    "InstaceEphemeral1": "1"
                    if i in cfg.EPHEMERAL_MAP["InstaceEphemeral1"]
                    else "0",
                    "InstaceEphemeral2": "1"
                    if i in cfg.EPHEMERAL_MAP["InstaceEphemeral2"]
                    else "0",
                }
            }
        )

    return mappings


def mapping_AZ():
    mappings = {}
    mappings["AvabilityZones"] = {}
    AZ = cfg.AZones

    for r in cfg.regions:
        zones = {}
        try:
            nzones = AZ[r]
        except Exception:
            nzones = AZ["default"]

        try:
            nzones = cfg.RP["dev"][r]["AZones"]
        except Exception:
            pass

        for n in range(AZ["MAX"]):
            zones[f"Zone{n}"] = "True" if nzones > n else "False"

        mappings["AvabilityZones"][r] = zones

    return mappings


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
        if n == "IBoxEnvRegion":
            c_Mapping = mapping_EnvRegion()
        elif n == "IBoxEC2":
            c_Mapping = mapping_EC2()
        elif n == "IBoxAZ":
            c_Mapping = mapping_AZ()
        else:
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
