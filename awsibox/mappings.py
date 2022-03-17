import sys
import os
import copy
from pprint import pprint, pformat

from . import cfg


def get_envregion_mapping():
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


def get_ec2_mapping():
    mappings = {}

    #   #START##MAP INSTANCE TYPE EPHEMERAL####
    map_eph = {
        "InstaceEphemeral0": [
            "m3.medium",
            "m3.large",
            "m3.xlarge",
            "m3.2xlarge",
            "c3.large",
            "c3.xlarge",
            "c3.2xlarge",
            "c3.4xlarge",
            "g2.2xlarge",
            "r3.large",
            "r3.xlarge",
            "r3.2xlarge",
            "r3.4xlarge",
            "i2.xlarge",
            "i2.2xlarge",
            "i2.4xlarge",
            "d2.xlarge",
            "d2.2xlarge",
            "d2.4xlarge",
        ],
        "InstaceEphemeral1": [
            "m3.xlarge",
            "m3.2xlarge",
            "c3.large",
            "c3.xlarge",
            "c3.2xlarge",
            "c3.4xlarge",
            "i2.2xlarge",
            "i2.4xlarge",
            "d2.xlarge",
            "d2.2xlarge",
            "d2.4xlarge",
        ],
        "InstaceEphemeral2": [
            "i2.4xlarge",
            "d2.xlarge",
            "d2.2xlarge",
            "d2.4xlarge",
        ],
    }

    mappings["InstanceTypes"] = {}

    for i in cfg.INSTANCE_LIST:
        mappings["InstanceTypes"].update(
            {
                i: {
                    "InstaceEphemeral0": "1"
                    if i in map_eph["InstaceEphemeral0"]
                    else "0",
                    "InstaceEphemeral1": "1"
                    if i in map_eph["InstaceEphemeral1"]
                    else "0",
                    "InstaceEphemeral2": "1"
                    if i in map_eph["InstaceEphemeral2"]
                    else "0",
                }
            }
        )
    #   #END##MAP INSTANCE TYPE EPHEMERAL####

    return mappings


def get_azones_mapping():
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


class Mappings(object):
    def __init__(self, key):
        for n, v in getattr(cfg, key).items():
            if n == "EnvRegion":
                mapping = get_envregion_mapping()
            if n == "EC2":
                mapping = get_ec2_mapping()
            if n == "AZones":
                mapping = get_azones_mapping()

            cfg.Mappings.update(mapping)
