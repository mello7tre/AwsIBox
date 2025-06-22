from troposphere import (
    ec2,
    Ref,
    If,
    Output,
    Sub,
    GetAtt,
    Export,
    And,
    Condition,
    Join,
    Base64,
)

from .. import cfg
from ..shared import (
    get_expvalue,
    auto_get_props,
    get_condition,
    add_obj,
    import_user_data,
    get_dictvalue,
    get_endvalue,
)


def EC2_LaunchTemplate(key):
    # Set cfg attributes used in user-data ELB Checks
    if cfg.LoadBalancerType == "Classic":
        for n in cfg.LoadBalancer.replace(",", " ").split():
            setattr(
                cfg,
                "EC2InstanceUserDataELBClassicCheckLoadBalancerName",
                Ref(f"LoadBalancerClassic{n}"),
            )
    if cfg.LoadBalancerType in ["Application", "Network"]:
        for n, v in getattr(cfg, "ElasticLoadBalancingV2TargetGroup", {}).items():
            # check for enabled only for EC2 ones
            if n.startswith("EC2") and v.get("IBOX_ENABLED", True):
                setattr(
                    cfg,
                    "EC2InstanceUserDataELBV2CheckTargetGroupArn",
                    Ref(f"ElasticLoadBalancingV2TargetGroup{n}"),
                )

    # Resources
    R_LaunchTemplate = ec2.LaunchTemplate(
        "LaunchTemplate",
        LaunchTemplateName=Sub("${AWS::StackName}-${EnvRole}"),
    )

    LaunchTemplateData = ec2.LaunchTemplateData("LaunchTemplateData")
    auto_get_props(
        LaunchTemplateData,
        "LaunchTemplateData",
        res_obj_type="AWS::EC2::LaunchTemplate",
    )

    R_LaunchTemplate.LaunchTemplateData = LaunchTemplateData

    ud_envrole = getattr(cfg, "IBOX_ROLE_EX", getattr(cfg, "envrole"))
    # try to get a complete user-data conf in package or in Ext dir
    user_data = import_user_data(ud_envrole)

    if not user_data:
        # if not found build a dynamic one
        for user_data_section in [
            "INIT",
            "PACKAGE",
            "SETUP",
            "APPS",
            "SERVICE",
            "ELBCHECK",
            ud_envrole,
            "END",
        ]:
            user_data.extend(import_user_data(f"SCRIPTS/{user_data_section}"))

    user_data = Join("", user_data)
    LaunchTemplateData.UserData = Base64(user_data)

    if getattr(cfg, "BottleRocket", False):
        # use if condition with both bottlerocket custom and standard cfg
        LaunchTemplateData.UserData = Base64(
            If(
                "BottleRocket",
                Join(
                    "\n",
                    [
                        get_endvalue(f"BottleRocketUserData{n}Line")
                        for n in cfg.BottleRocketUserData
                    ],
                ),
                user_data,
            ),
        )

    add_obj(R_LaunchTemplate)

    # add Medata Tags to LaunchTemplate TagSpecifications
    if hasattr(cfg, "MetadataTags"):
        for n in R_LaunchTemplate.LaunchTemplateData.TagSpecifications:
            if n.ResourceType in ["instance", "volume"]:
                n.Tags.tags.extend(
                    [
                        {"Key": n, "Value": v}
                        for n, v in get_dictvalue(
                            cfg.MetadataTags, mapname="MetadataTags"
                        ).items()
                    ],
                )


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
        expname = v.get("Export")
        if expname:
            o_SG.Export = Export(
                outname if expname is True else Sub(f"{outname}-{expname}")
            )

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
                    # current Condition if exist
                    sgi_condition = getattr(r_SGI, "Condition", None)
                    # set the base one
                    r_SGI.Condition = f"AllowedIp{m}"
                    if sgi_condition:
                        # There is already a Condition, dinamically create a new one
                        r_SGI.Condition = f"{sgi_condition}And{r_SGI.Condition}"
                        add_obj(
                            {
                                r_SGI.Condition: And(
                                    Condition(f"AllowedIp{m}"), Condition(sgi_condition)
                                )
                            }
                        )
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
