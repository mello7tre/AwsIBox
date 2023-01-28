import troposphere.elasticloadbalancing as elb
import troposphere.elasticloadbalancingv2 as elbv2
import troposphere.ec2 as ec2

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
from .ec2 import SecurityGroupIngressInstanceELBPorts


# Temporary fix for https://github.com/cloudtools/troposphere/issues/1474
elbv2.one_of = my_one_of

# Fix troposphere/elasticloadbalancing.py LBCookieStickinessPolicy is a List and do not use class LBCookieStickinessPolicy
elb.LoadBalancer.props["LBCookieStickinessPolicy"] = (
    [elb.LBCookieStickinessPolicy],
    False,
)
elb.LoadBalancer.props["Listeners"] = ([elb.Listener], False)


def enable_recordset(rtype):
    prefix = f"Route53RecordSet"
    if "External" in cfg.RecordSet:
        if "External" in cfg.LoadBalancer:
            record = getattr(cfg, f"{prefix}{rtype}ExternalLoadBalancerExternal")
        else:
            record = getattr(cfg, f"{prefix}{rtype}ExternalLoadBalancerInternal")
        record["IBOX_ENABLED"] = True
    if "Internal" in cfg.RecordSet:
        if "Internal" in cfg.LoadBalancer:
            record = getattr(cfg, f"{prefix}{rtype}InternalLoadBalancerInternal")
        else:
            record = getattr(cfg, f"{prefix}{rtype}InternalLoadBalancerExternal")
        record["IBOX_ENABLED"] = True


def LB_ElasticLoadBalancingClassicEC2():
    for lb in cfg.LoadBalancer:
        # update SecurityGroupInstancesRules Ingress using Listeners
        for n in getattr(cfg, f"ElasticLoadBalancingLoadBalancer{lb}")["Listeners"]:
            r_SGIInstance = SecurityGroupIngressInstanceELBPorts(
                f"SecurityGroupIngressListeners{n}",
                FromPort=get_endvalue(
                    f"ElasticLoadBalancingLoadBalancer{lb}Listeners{n}InstancePort"
                ),
                SourceSecurityGroupId=Ref("SecurityGroupLoadBalancer"),
                ToPort=get_endvalue(
                    f"ElasticLoadBalancingLoadBalancer{lb}Listeners{n}InstancePort"
                ),
            )
            add_obj(r_SGIInstance)

        # LoadBalancer
        r_LB = elb.LoadBalancer(f"LoadBalancerClassic{lb}")
        auto_get_props(r_LB, mapname=f"ElasticLoadBalancingLoadBalancer{lb}")
        add_obj(r_LB)

        cfg.CloudWatchAlarm[f"Backend{lb}5XX"]["IBOX_ENABLED"] = True


def LB_ElasticLoadBalancingApplicationEC2():
    for lb in cfg.LoadBalancer:
        r_LB = elbv2.LoadBalancer(f"LoadBalancerApplication{lb}")
        auto_get_props(
            r_LB, mapname=f"ElasticLoadBalancingV2LoadBalancerEC2Application{lb}"
        )
        add_obj(r_LB)

        # enable Listeners
        if lb == "External":
            getattr(cfg, f"ElasticLoadBalancingV2ListenerEC2Https{lb}")[
                "IBOX_ENABLED"
            ] = True
        else:
            getattr(cfg, f"ElasticLoadBalancingV2ListenerEC2Http{lb}")[
                "IBOX_ENABLED"
            ] = True
        # enable TargetGroups
        getattr(
            cfg, f"ElasticLoadBalancingV2TargetGroupEC2LoadBalancerApplication{lb}"
        )["IBOX_ENABLED"] = True

        cfg.CloudWatchAlarm[f"TargetEC2{lb}5XX"]["IBOX_ENABLED"] = True

    # update SecurityGroupInstancesRules giving access from LB to Target Ports
    for n, v in cfg.ElasticLoadBalancingV2TargetGroup.items():
        if v.get("IBOX_ENABLED", True):
            r_SGIInstance = SecurityGroupIngressInstanceELBPorts(
                f"SecurityGroupIngressListeners{n}",
                FromPort=get_endvalue(f"ElasticLoadBalancingV2TargetGroup{n}Port"),
                SourceSecurityGroupId=Ref("SecurityGroupLoadBalancer"),
                ToPort=get_endvalue(f"ElasticLoadBalancingV2TargetGroup{n}Port"),
            )
            add_obj(r_SGIInstance)


def LB_ElasticLoadBalancingNetworkEC2():
    for lb in cfg.LoadBalancer:
        r_LB = elbv2.LoadBalancer(f"LoadBalancerNetwork{lb}")
        auto_get_props(
            r_LB, mapname=f"ElasticLoadBalancingV2LoadBalancerEC2Network{lb}"
        )
        add_obj(r_LB)

        # enable Listeners
        getattr(cfg, f"ElasticLoadBalancingV2ListenerEC2TCP{lb}")["IBOX_ENABLED"] = True
        # enable TargetGroups
        getattr(cfg, f"ElasticLoadBalancingV2TargetGroupEC2LoadBalancerNetwork{lb}")[
            "IBOX_ENABLED"
        ] = True

    # update SecurityGroupInstancesRules giving access to Target Ports
    for n, v in cfg.ElasticLoadBalancingV2TargetGroup.items():
        if v.get("IBOX_ENABLED", True):
            r_SGIInstance = SecurityGroupIngressInstanceELBPorts(
                f"SecurityGroupIngressListeners{n}",
                FromPort=get_endvalue(f"ElasticLoadBalancingV2TargetGroup{n}Port"),
                CidrIp="0.0.0.0/0",
                ToPort=get_endvalue(f"ElasticLoadBalancingV2TargetGroup{n}Port"),
            )
            add_obj(r_SGIInstance)


def LB_ElasticLoadBalancingEC2(key):
    if not cfg.LoadBalancer:
        return
    enable_recordset("EC2")

    if cfg.LoadBalancerType == "Classic":
        LB_ElasticLoadBalancingClassicEC2()

    if cfg.LoadBalancerType == "Application":
        LB_ElasticLoadBalancingApplicationEC2()

    if cfg.LoadBalancerType == "Network":
        LB_ElasticLoadBalancingNetworkEC2()


def LB_ElasticLoadBalancingECS(key):
    if not cfg.LoadBalancer:
        return
    enable_recordset("ECS")

    for lb in cfg.LoadBalancer:
        # TargetGroup
        r_TG = elbv2.TargetGroup(f"TargetGroup{lb}")
        auto_get_props(
            r_TG,
            mapname=f"ElasticLoadBalancingV2TargetGroupECSLoadBalancerApplication{lb}",
        )
        add_obj(r_TG)

        try:
            cfg.CloudWatchAlarm[f"Target{lb}5XX"]["IBOX_ENABLED"] = True
        except Exception:
            pass

        if lb == "External":
            getattr(cfg, f"ElasticLoadBalancingV2ListenerRuleHttps{lb}Rules1")[
                "IBOX_ENABLED"
            ] = True
        else:
            getattr(cfg, f"ElasticLoadBalancingV2ListenerRuleHttp{lb}Rules1")[
                "IBOX_ENABLED"
            ] = True
