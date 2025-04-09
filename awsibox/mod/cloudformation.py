import copy
from troposphere import cloudformation, Ref
from awsibox import cfg
from ..shared import get_endvalue, add_obj, auto_get_props


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


def CFM_CustomResourceReplicator(key):
    R_Replicator = cloudformation.CustomResource(
        "CloudFormationCustomResourceStackReplicator"
    )
    auto_get_props(R_Replicator)

    for p, v in cfg.Parameters.items():
        if not p.startswith("Env"):
            value = get_endvalue(p)
        else:
            value = Ref(p)
        setattr(R_Replicator, p, value)

    add_obj(R_Replicator)
