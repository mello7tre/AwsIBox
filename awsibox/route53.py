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


def R53_RecordSetEC2LoadBalancer():
    # Resources
    # RecordSet External
    if "External" in cfg.RecordSet:
        R_External = r53.RecordSetType("RecordSetExternal")
        auto_get_props(R_External, "Route53RecordSetEC2LoadBalancerExternal")

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
        auto_get_props(R_Internal, "Route53RecordSetEC2LoadBalancerInternal")

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
                R_External, "Route53RecordSetECSLoadBalancerTargetExternalExternal"
            )
        else:
            auto_get_props(
                R_External, "Route53RecordSetECSLoadBalancerTargetInternalExternal"
            )

        # outputs
        O_External = Output("RecordSetExternal")
        O_External.Value = Ref("RecordSetExternal")

        add_obj([R_External, O_External])

    if "Internal" in cfg.RecordSet:
        R_Internal = r53.RecordSetType("RecordSetInternal")

        if "Internal" in cfg.LoadBalancer:
            auto_get_props(
                R_Internal, "Route53RecordSetECSLoadBalancerTargetInternalInternal"
            )
        else:
            auto_get_props(
                R_Internal, "Route53RecordSetECSLoadBalancerTargetExternalInternal"
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
        auto_get_props(r_Record, f"Route53RecordSetRDS{n}")
        r_Record.title = f"RecordSet{n}"

        # outputs
        o_Record = Output(f"RecordSet{n}")
        o_Record.Value = Ref(f"RecordSet{n}")

        add_obj([r_Record, o_Record])
