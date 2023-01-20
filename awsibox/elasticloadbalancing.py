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


class ELBV2ListernerRuleECS(elbv2.ListenerRule):
    def __init__(self, title, key, index, mapname, scheme, **kwargs):
        super().__init__(title, **kwargs)

        auto_get_props(self, f"ListenerRules{index}")
        if "Conditions" not in key:
            self.Conditions = []
            if "HostHeader" in key:
                self.Conditions.append(
                    elbv2.Condition(
                        Field="host-header",
                        Values=[get_endvalue(f"{mapname}HostHeader", issub=True)],
                    )
                )
            if "PathPattern" in key:
                self.Conditions.append(
                    elbv2.Condition(
                        Field="path-pattern",
                        Values=[
                            Sub(
                                "${Value}",
                                **{"Value": get_endvalue(f"{mapname}PathPattern")},
                            )
                        ],
                    )
                )
            if "RequestMethod" in key:
                self.Conditions.append(
                    elbv2.Condition(
                        Field="http-request-method",
                        HttpRequestMethodConfig=elbv2.HttpRequestMethodConfig(
                            Values=[get_endvalue(f"{mapname}RequestMethod", issub=True)]
                        ),
                    )
                )
        if "Actions" not in key:
            tg_prefix = key.get("TargetGroupPrefix", "")
            self.Actions = [
                elbv2.ListenerRuleAction(
                    Type="forward",
                    TargetGroupArn=Ref(f"TargetGroup{tg_prefix}{scheme}"),
                )
            ]
        self.Priority = get_endvalue(f"{mapname}Priority")


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


def LB_ListenerRulesExternalInternal(index, key, mapname, scheme):
    # Skip if Rule is only for External/Internal
    only_scheme = key.get("Scheme")
    if only_scheme and only_scheme != scheme:
        return

    # resources
    R_RuleHttp = ELBV2ListernerRuleECS(
        f"ListenerHttp{scheme}Rules{index}",
        key=key,
        index=index,
        mapname=mapname,
        scheme=scheme,
    )
    R_RuleHttp.ListenerArn = get_expvalue(
        f"ListenerHttpDefault{scheme}", "LoadBalancerApplicationStack"
    )

    R_RuleHttps = ELBV2ListernerRuleECS(
        f"ListenerHttps{scheme}Rules{index}",
        key=key,
        index=index,
        mapname=mapname,
        scheme=scheme,
    )
    R_RuleHttps.ListenerArn = get_expvalue(
        f"ListenerHttpsDefault{scheme}", "LoadBalancerApplicationStack"
    )

    # Create ListenerRule only in stack's specific new Listener
    ListenerHttpPort = cfg.ListenerLoadBalancerHttpPort
    ListenerHttpsPort = cfg.ListenerLoadBalancerHttpsPort

    Protocol = key.get("Protocol", "auto")

    RuleHttpAdd = None
    RuleHttpsAdd = None

    if "NoDefault" in key:
        R_RuleHttp.ListenerArn = Ref(f"ListenerHttp{scheme}")
        R_RuleHttps.ListenerArn = Ref(f"ListenerHttps{scheme}")
        if ListenerHttpPort != 80:
            RuleHttpAdd = True
        if ListenerHttpsPort != 443:
            RuleHttpsAdd = True
    else:
        # by default create http rules on Internal LB and https rules on External one
        if scheme == "Internal":
            RuleHttpAdd = True
        if scheme == "External":
            RuleHttpsAdd = True
            # on External can be forced or overriden by key http/https/any
            if Protocol == "http":
                RuleHttpAdd = True
                RuleHttpsAdd = None
            if Protocol == "https":
                RuleHttpAdd = None
                RuleHttpsAdd = True
            if Protocol == "any":
                RuleHttpAdd = True
                RuleHttpsAdd = True

    if RuleHttpAdd:
        add_obj(R_RuleHttp)
    if RuleHttpsAdd:
        add_obj(R_RuleHttps)


def LB_ListenerRules():
    for n, v in cfg.ListenerRules.items():
        mapname = f"ListenerRules{n}"  # Ex. ListenerRules1

        # parameters
        p_Priority = Parameter(
            f"{mapname}Priority",
            Description="Listener Rule Priority, lesser value = high priority - empty for default based on env/role",
        )

        add_obj(p_Priority)

        ListenerRule_Out_String = ["Priority=${Priority}"]
        ListenerRule_Out_Map = {"Priority": get_endvalue(f"{mapname}Priority")}

        if "HostHeader" in v:
            p_HostHeader = Parameter(
                f"{mapname}HostHeader",
                Description="Listener Rule HostHeader Condition - empty for default based on env/role",
            )

            add_obj(p_HostHeader)

            # outputs
            ListenerRule_Out_String.append("HostHeader=${HostHeader}")
            ListenerRule_Out_Map.update(
                {"HostHeader": get_endvalue(f"{mapname}HostHeader", issub=True)}
            )

        if "PathPattern" in v:
            p_PathPattern = Parameter(
                f"{mapname}PathPattern",
                Description="Listener Rule PathPattern Condition - empty for default based on env/role",
            )

            add_obj(p_PathPattern)

            # outputs
            ListenerRule_Out_String.append("PathPattern=${PathPattern}")
            ListenerRule_Out_Map.update(
                {"PathPattern": get_endvalue(f"{mapname}PathPattern", issub=True)}
            )

        # resources
        for lb in cfg.LoadBalancer:
            LB_ListenerRulesExternalInternal(
                index=str(n), key=v, mapname=mapname, scheme=lb
            )

        # outputs
        o_ListenerRule = Output(mapname)
        o_ListenerRule.Value = Sub(
            ",".join(ListenerRule_Out_String), **ListenerRule_Out_Map
        )

        add_obj(o_ListenerRule)


def LB_ListenersV2ECS():
    for n in ["External", "Internal"]:
        # resources
        if n not in cfg.LoadBalancer:
            continue
        if cfg.ListenerLoadBalancerHttpPort not in ["none", 80]:
            # Enable the relative LB SecurityGroupIngress
            cfg.SecurityGroupIngress[f"LoadBalancerApplicationHttp{n}"][
                "IBOX_ENABLED"
            ] = True
            r_Http = elbv2.Listener(f"ListenerHttp{n}")
            auto_get_props(r_Http, mapname=f"ListenerV2ECSHttp{n}")
            add_obj(r_Http)

        if cfg.ListenerLoadBalancerHttpsPort not in ["none", 443] and n == "External":
            # Enable the relative LB SecurityGroupIngress
            cfg.SecurityGroupIngress[f"LoadBalancerApplicationHttps{n}"][
                "IBOX_ENABLED"
            ] = True
            r_Https = elbv2.Listener(f"ListenerHttps{n}")
            auto_get_props(r_Https, mapname=f"ListenerV2ECSHttps{n}")
            add_obj(r_Https)

    # Resources
    LB_TargetGroupsECS()
    LB_ListenerRules()


def LB_TargetGroupsECS():
    for n in cfg.ElasticLoadBalancingV2TargetGroupECS:
        # resources
        if n in ["External", "Internal"] and n not in cfg.LoadBalancer:
            continue
        r_TG = elbv2.TargetGroup(f"TargetGroup{n}")
        auto_get_props(r_TG, mapname=f"ElasticLoadBalancingV2TargetGroupECS{n}")
        add_obj(r_TG)

        try:
            cfg.Alarm[f"Target{n}5XX"]["IBOX_ENABLED"] = True
        except Exception:
            pass


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

        cfg.Alarm[f"Backend{lb}5XX"]["IBOX_ENABLED"] = True


def LB_ElasticLoadBalancingApplicationEC2():
    for lb in cfg.LoadBalancer:
        r_LB = elbv2.LoadBalancer(f"LoadBalancerApplication{lb}")
        auto_get_props(r_LB, mapname=f"ElasticLoadBalancingV2LoadBalancerAPP{lb}")
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
        getattr(cfg, f"ElasticLoadBalancingV2TargetGroupEC2LoadBalancerApplication{lb}")[
            "IBOX_ENABLED"
        ] = True

        cfg.Alarm[f"TargetEC2{lb}5XX"]["IBOX_ENABLED"] = True

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
        auto_get_props(r_LB, mapname=f"ElasticLoadBalancingV2LoadBalancerNET{lb}")
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
    # Resources
    LB_ListenersV2ECS()
    enable_recordset("ECS")
