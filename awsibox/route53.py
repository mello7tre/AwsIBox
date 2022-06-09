import troposphere.route53 as r53

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


class R53RecordSetEFS(r53.RecordSetType):
    def __init__(self, title, efsname, **kwargs):
        super().__init__(title, **kwargs)
        condname = f"EFSFileSystem{efsname}"
        self.Condition = condname
        self.HostedZoneId = Ref("HostedZonePrivate")
        self.Name = Sub("efs-%s.%s" % (efsname, cfg.HostedZoneNamePrivate))
        self.ResourceRecords = [
            Sub("${%s}.efs.${AWS::Region}.amazonaws.com" % condname)
        ]
        self.Type = "CNAME"
        self.TTL = "300"


class R53RecordSetNSServiceDiscovery(r53.RecordSetType):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.HostedZoneId = Ref("HostedZoneEnv")
        self.Name = Sub("find.%s" % cfg.HostedZoneNameEnv)
        self.ResourceRecords = GetAtt("PublicDnsNamespace", "NameServers")
        self.Type = "NS"
        self.TTL = "300"


def R53_RecordSetEC2LoadBalancer():
    # Resources
    # RecordSet External
    if "External" in cfg.RecordSet:
        R_External = r53.RecordSetType("RecordSetExternal")
        auto_get_props(R_External, "R53RecordSetEC2LoadBalancerExternal")

        if "External" in cfg.LoadBalancer:
            R_External.AliasTarget.DNSName = GetAtt(
                f"LoadBalancer{cfg.LoadBalancerType}External", "DNSName"
            )
        elif "Internal" in cfg.LoadBalancer:
            R_External.AliasTarget.DNSName = GetAtt(
                f"LoadBalancer{cfg.LoadBalancerType}Internal", "DNSName"
            )

        # outputs
        O_External = Output("RecordSetExternal")
        O_External.Value = Ref("RecordSetExternal")

        add_obj([R_External, O_External])

    # RecordSet Internal
    if "Internal" in cfg.RecordSet:
        R_Internal = r53.RecordSetType("RecordSetInternal")
        auto_get_props(R_Internal, "R53RecordSetEC2LoadBalancerInternal")

        if "Internal" in cfg.LoadBalancer:
            R_Internal.AliasTarget.DNSName = GetAtt(
                f"LoadBalancer{cfg.LoadBalancerType}Internal", "DNSName"
            )
        if "External" in cfg.LoadBalancer:
            R_Internal.AliasTarget.DNSName = GetAtt(
                f"LoadBalancer{cfg.LoadBalancerType}External", "DNSName"
            )

        # outputs
        O_Internal = Output("RecordSetInternal")
        O_Internal.Value = Ref("RecordSetInternal")

        add_obj([R_Internal, O_Internal])

    # fix bad for networkloadbalancer having different HostedZoneId
    if cfg.LoadBalancerType == "Network":
        for r in [R_External, R_Internal]:
            r.AliasTarget.HostedZoneId = get_endvalue("HostedZoneIdLBNET")


def R53_RecordSetECSLoadBalancer():
    # Resources
    if "External" in cfg.RecordSet:
        R_External = r53.RecordSetType("RecordSetExternal")

        if "External" in cfg.LoadBalancer:
            auto_get_props(
                R_External, "R53RecordSetECSLoadBalancerTargetExternalExternal"
            )
        else:
            auto_get_props(
                R_External, "R53RecordSetECSLoadBalancerTargetInternalExternal"
            )

        # outputs
        O_External = Output("RecordSetExternal")
        O_External.Value = Ref("RecordSetExternal")

        add_obj([R_External, O_External])

    if "Internal" in cfg.RecordSet:
        R_Internal = r53.RecordSetType("RecordSetInternal")

        if "Internal" in cfg.LoadBalancer:
            auto_get_props(
                R_Internal, "R53RecordSetECSLoadBalancerTargetInternalInternal"
            )
        else:
            auto_get_props(
                R_Internal, "R53RecordSetECSLoadBalancerTargetExternalInternal"
            )

        # outputs
        O_Internal = Output("RecordSetInternal")
        O_Internal.Value = Ref("RecordSetInternal")

        add_obj([R_Internal, O_Internal])


def R53_RecordSetRDS(rds_resname):
    for n in ["External", "Internal"]:
        if n not in cfg.RecordSet:
            continue
        # resources
        r_Record = r53.RecordSetType(rds_resname)
        auto_get_props(r_Record, f"R53RecordSetRDS{n}")
        r_Record.title = f"RecordSet{n}"

        # outputs
        o_Record = Output(f"RecordSet{n}")
        o_Record.Value = Ref(f"RecordSet{n}")

        add_obj([r_Record, o_Record])


def R53_HostedZones(key):
    for n, v in getattr(cfg, key).items():
        mapname = f"{key}{n}"
        resname = v["ResourceName"]
        output_zonename = resname.replace("HostedZone", "HostedZoneName")
        output_zoneidname = resname.replace("HostedZone", "HostedZoneId")
        # parameters
        if n.startswith("Public"):
            p_HostedZone = Parameter(f"{mapname}Enabled")
            p_HostedZone.Description = (
                f"Create Public {resname} - can be created in only one "
                "Region - empty for default based on env/role"
            )

            p_HostedZoneId = Parameter(f"{mapname}Id")
            p_HostedZoneId.Description = (
                f"Id of Public {resname} - required in all Regions where"
                " HostedZonePublicEnv is not created - "
                "empty for default based on env/role"
            )

            add_obj([p_HostedZone, p_HostedZoneId])

            # conditions
            c_Enabled = get_condition(resname, "equals", "yes", f"{mapname}Enabled")

            add_obj(c_Enabled)

        # resources
        r_HostedZone = r53.HostedZone(resname)
        auto_get_props(r_HostedZone, mapname)

        if n.startswith("Public"):
            r_HostedZone.Condition = resname

        # outputs
        o_HostedZoneName = Output(output_zonename)
        # o_HostedZoneName.Value = Sub(cfg.HostedZoneNamePrivate)
        o_HostedZoneName.Value = get_endvalue(f"{mapname}Name")

        o_HostedZoneId = Output(output_zoneidname)
        o_HostedZoneId.Value = (
            If(resname, Ref(resname), get_endvalue(f"{mapname}Id"))
            if n.startswith("Public")
            else Ref(resname)
        )
        o_HostedZoneId.Export = Export(output_zoneidname)

        add_obj([r_HostedZone, o_HostedZoneName, o_HostedZoneId])
