import troposphere.ec2 as ec2

from ..common import *
from ..shared import (
    Parameter,
    get_endvalue,
    get_expvalue,
    auto_get_props,
    get_condition,
    add_obj,
)


def SG_SecurityGroupsExtra(Out_String, Out_Map):
    # Parameters
    P_SecurityGroups = Parameter(
        "SecurityGroups",
        Description=f"SecurityGroups List Extra - {SECURITY_GROUPS_DEFAULT} for default based on env/role",
        AllowedPattern=r"^(\w*,\w*){%s}$" % (MAX_SECURITY_GROUPS - 1),
        Default=SECURITY_GROUPS_DEFAULT,
    )

    add_obj([P_SecurityGroups])

    SecurityGroups = []

    for n in range(MAX_SECURITY_GROUPS):
        name = f"SecurityGroup{n}"  # Ex SecurityGroup1
        value = Select(n, Split(",", get_endvalue("SecurityGroups")))
        outnamename = f"SecurityGroupName{n}"
        outvaluename = f"SecurityGroupValue{n}"

        # conditions
        add_obj(
            {
                name: Not(
                    get_condition(
                        "", "equals", "none", Select(n, Split(",", "SecurityGroups"))
                    )
                )
            }
        )

        SecurityGroups.append(
            If(name, get_expvalue(value, prefix="SecurityGroup"), Ref("AWS::NoValue"))
        )

        # outputs
        Out_String.append("${%s}=${%s}" % (outnamename, outvaluename))
        Out_Map.update(
            {
                outnamename: value,
                outvaluename: If(
                    name, get_expvalue(value, prefix="SecurityGroup"), "none"
                ),
            }
        )

    # Outputs
    O_SecurityGroups = Output(
        "SecurityGroups", Value=Sub(",".join(Out_String), **Out_Map)
    )

    add_obj(O_SecurityGroups)

    cfg.SecurityGroupsImport = SecurityGroups


def SG_SecurityGroupsEC2(key):
    Out_String = ["Rules=${SecurityGroupInstancesRules}"]
    Out_Map = {"SecurityGroupInstancesRules": {"Ref": "SecurityGroupInstancesRules"}}

    SecurityGroups = SG_SecurityGroupsExtra(Out_String, Out_Map)


def SG_SecurityGroupsECS(key):
    Out_String = ["Service=${SecurityGroupEcsService}"]
    Out_Map = {"SecurityGroupEcsService": {"Ref": "SecurityGroupEcsService"}}

    SecurityGroups = SG_SecurityGroupsExtra(Out_String, Out_Map)
    # add Condition to Output created by SG_SecurityGroupsExtra
    try:
        cfg.Outputs[
            "SecurityGroups"
        ].Condition = "ECSTaskDefinitionBaseNetworkModeAwsVpc"
    except Exception:
        pass


def SG_SecurityGroupsTSK(key):
    Out_String = []
    Out_Map = {}

    SecurityGroups = SG_SecurityGroupsExtra(Out_String, Out_Map)
    # add Condition to Output created by SG_SecurityGroupsExtra
    try:
        cfg.Outputs[
            "SecurityGroups"
        ].Condition = "ECSTaskDefinitionBaseNetworkModeAwsVpc"
    except Exception:
        pass


def SG_SecurityGroupRules(groupname, ingresses):
    SecurityGroup_Rules = []
    listeners_cfg = {}

    if cfg.LoadBalancer:
        if cfg.LoadBalancerType == "Network":
            return SecurityGroup_Rules

        if cfg.LoadBalancerType == "Classic":
            # get config from ElasticLoadBalancingLoadBalancer key
            for e in cfg.LoadBalancer.replace(",", " ").split():
                listeners_cfg.update(
                    getattr(cfg, f"ElasticLoadBalancingLoadBalancerEC2Classic{e}")[
                        "Listeners"
                    ]
                )
        if cfg.LoadBalancerType == "Application":
            # get config ElasticLoadBalancingV2Listener key
            for n, v in cfg.ElasticLoadBalancingV2Listener.items():
                if v.get("IBOX_ENABLED", True):
                    listeners_cfg[n] = v

    # Trick to populate SecurityGroupIngress using Listeners
    if ingresses:
        # use SecurityGroupIngress
        prefix = f"{groupname}SecurityGroupIngress"
        use_listener = False
        cond_key = "CidrIp"
    else:
        # use cfg.Listeners
        prefix = "Listeners"
        ingresses = listeners_cfg
        use_listener = True
        cond_key = "Access"

    for n, v in ingresses.items():
        if use_listener:
            # Trick to populate SecurityGroupIngress using Listeners
            sg_rootdict = {
                "CidrIp": v.get("Access", "Public"),
                "FromPort": v["LoadBalancerPort"]
                if "LoadBalancerPort" in v
                else v["Port"],
                "ToPort": v["LoadBalancerPort"]
                if "LoadBalancerPort" in v
                else v["Port"],
            }
            kwargs = {"rootdict": sg_rootdict}
        else:
            sg_rootdict = v
            kwargs = {}

        resname = f"{prefix}{n}"
        allowed_ip = sg_rootdict.get("CidrIp") == "AllowedIp"
        allowed_ip_or_public = sg_rootdict.get("AllowedIpOrPublic")
        if allowed_ip:
            for m, w in cfg.AllowedIp.items():
                r_SGRule = ec2.SecurityGroupRule(resname, IpProtocol="tcp")
                auto_get_props(
                    r_SGRule, **kwargs, res_obj_type="AWS::EC2::SecurityGroup"
                )
                auto_get_props(
                    r_SGRule, f"AllowedIp{m}", res_obj_type="AWS::EC2::SecurityGroup"
                )
                SecurityGroup_Rules.append(
                    If(f"AllowedIp{m}", r_SGRule, Ref("AWS::NoValue"))
                )

        if not allowed_ip or allowed_ip_or_public:
            r_SGRule = ec2.SecurityGroupRule(resname, IpProtocol="tcp")
            auto_get_props(r_SGRule, **kwargs, res_obj_type="AWS::EC2::SecurityGroup")

            if allowed_ip and allowed_ip_or_public:
                r_SGRule.CidrIp = "0.0.0.0/0"
                # condition
                c_Public = get_condition(
                    f"{resname}Public", "equals", "0.0.0.0/0", f"{resname}{cond_key}"
                )
                add_obj(c_Public)
                r_SGRule = If(f"{resname}Public", r_SGRule, Ref("AWS::NoValue"))

            SecurityGroup_Rules.append(r_SGRule)

    return SecurityGroup_Rules


def SG_SecurityGroup(key):
    for n, v in getattr(cfg, key).items():
        if not v.get("IBOX_ENABLED", True):
            continue
        # harcode original title, as is used this way in other part of code/cfg
        mapname = f"{key}{n}"
        resname = f"SecurityGroup{n}"

        # get IBOX_LINKED_OBJ keys
        linked_obj_name = v.get("IBOX_LINKED_OBJ_NAME", "")
        linked_obj_index = v.get("IBOX_LINKED_OBJ_INDEX", "")

        # resources
        r_SG = ec2.SecurityGroup(resname, VpcId=get_expvalue("VpcId"))
        auto_get_props(
            r_SG,
            mapname=mapname,
            linked_obj_name=linked_obj_name,
            linked_obj_index=linked_obj_index,
        )

        try:
            ingress = v["SecurityGroupIngress"]
            if ingress:
                # SecurityGroupIngress is not empty, check if is "complete" (have IpProtocol)
                r_SG.to_dict()
            else:
                raise ValueError
        except KeyError:
            # key SecurityGroupIngress do not exist
            pass
        except ValueError:
            # to_dict failed or SecurityGroupIngress is empty, populate it using SG_SecurityGroupRules
            r_SG.SecurityGroupIngress = SG_SecurityGroupRules(
                mapname, v["SecurityGroupIngress"]
            )

        try:
            outname = v["OutputName"]
        except Exception:
            outname = resname
        else:
            outname = f"SecurityGroup{outname}"

        # outputs
        o_SG = Output(outname)
        o_SG.Value = GetAtt(resname, "GroupId")
        if v.get("Export"):
            o_SG.Export = Export(outname)

        if v.get("Condition"):
            o_SG.Condition = v.get("Condition")

        add_obj(r_SG)
        # add output only if not already present (can be created by IBOXOUTPUT)
        try:
            cfg.Outputs[outname]
        except Exception:
            if not v.get("IBOX_NO_OUTPUT"):
                add_obj(o_SG)


def SG_SecurityGroupIngresses(key):
    for n, v in getattr(cfg, key).items():
        if not v.get("IBOX_ENABLED", True):
            continue
        mapname = f"{key}{n}"
        resname = f"SecurityGroupIngress{n}"

        # get IBOX_LINKED_OBJ keys
        linked_obj_name = v.get("IBOX_LINKED_OBJ_NAME", "")
        linked_obj_index = v.get("IBOX_LINKED_OBJ_INDEX", "")

        try:
            allowed_ip = v["CidrIp"] == "AllowedIp"
        except Exception:
            pass
        else:
            if allowed_ip:
                for m, w in cfg.AllowedIp.items():
                    r_SGI = ec2.SecurityGroupIngress(f"{resname}{m}", IpProtocol="tcp")
                    auto_get_props(r_SGI, mapname)
                    auto_get_props(r_SGI, f"AllowedIp{m}")
                    r_SGI.Condition = f"AllowedIp{m}"
                    add_obj(r_SGI)
                continue

        r_SGI = ec2.SecurityGroupIngress(resname, IpProtocol="tcp")
        auto_get_props(
            r_SGI,
            mapname,
            linked_obj_name=linked_obj_name,
            linked_obj_index=linked_obj_index,
        )
        add_obj(r_SGI)
