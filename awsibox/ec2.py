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


class SecurityGroup(ec2.SecurityGroup):
    # troposphere ec2 is quite old and SecurityGroupIngress is only a list
    # without the obj type, this break auto_get_props, fix it overriding
    props = {
        "GroupName": (str, False),
        "GroupDescription": (str, True),
        "SecurityGroupEgress": (list, False),
        "SecurityGroupIngress": ([ec2.SecurityGroupRule], False),
        "VpcId": (str, False),
        "Tags": ((Tags, list), False),
    }

    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.VpcId = get_expvalue("VpcId")


class SecurityGroupIngress(ec2.SecurityGroupIngress):
    IpProtocol = "tcp"


class SecurityGroupRule(ec2.SecurityGroupRule):
    IpProtocol = "tcp"


class SecurityGroupIngressInstanceELBPorts(SecurityGroupIngress):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        name = self.title  # Ex. SecurityGroupIngressListeners1
        self.GroupId = GetAtt("SecurityGroupInstancesRules", "GroupId")


class SecurityGroupEcsService(SecurityGroup):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.Condition = "NetworkModeAwsVpc"
        self.GroupDescription = "Enable access to Service"
        self.SecurityGroupIngress = []


class SecurityGroupRuleEcsService(SecurityGroupRule):
    def __init__(self, scheme, **kwargs):
        super().__init__(**kwargs)
        self.SourceSecurityGroupId = get_expvalue(
            f"SecurityGroupLoadBalancerApplication{scheme}"
        )
        self.FromPort = get_endvalue("ContainerDefinitions1ContainerPort")
        self.ToPort = self.FromPort


class EC2Subnet(ec2.Subnet):
    def __init__(self, title, zone, **kwargs):
        super().__init__(title, **kwargs)
        self.AvailabilityZone = Sub("${AWS::Region}%s" % zone.lower())
        self.VpcId = Ref("VPC")


class EC2SubnetPrivate(EC2Subnet):
    def __init__(self, title, zone, **kwargs):
        super().__init__(title, zone, **kwargs)
        self.CidrBlock = Ref(f"SubnetCidrBlockPrivate{zone}")
        self.MapPublicIpOnLaunch = False
        self.Tags = Tags(Name=Sub("${VPCName}-Private%s" % zone))


class EC2SubnetPublic(EC2Subnet):
    def __init__(self, title, zone, **kwargs):
        super().__init__(title, zone, **kwargs)
        self.CidrBlock = Ref(f"SubnetCidrBlockPublic{zone}")
        self.MapPublicIpOnLaunch = True
        self.Tags = Tags(Name=Sub("${VPCName}-Public%s" % zone))


class EC2SubnetRouteTableAssociationPrivate(ec2.SubnetRouteTableAssociation):
    def __init__(self, title, zone, **kwargs):
        super().__init__(title, **kwargs)
        self.RouteTableId = Ref("RouteTablePrivate")
        self.SubnetId = Ref(f"SubnetPrivate{zone}")


class EC2SubnetRouteTableAssociationPublic(ec2.SubnetRouteTableAssociation):
    def __init__(self, title, zone, **kwargs):
        super().__init__(title, **kwargs)
        self.RouteTableId = Ref("RouteTablePublic")
        self.SubnetId = Ref(f"SubnetPublic{zone}")


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
        cfg.Outputs["SecurityGroups"].Condition = "NetworkModeAwsVpc"
    except Exception:
        pass


def SG_SecurityGroupsTSK(key):
    Out_String = []
    Out_Map = {}

    SecurityGroups = SG_SecurityGroupsExtra(Out_String, Out_Map)
    # add Condition to Output created by SG_SecurityGroupsExtra
    try:
        cfg.Outputs["SecurityGroups"].Condition = "NetworkModeAwsVpc"
    except Exception:
        pass


def SG_SecurityGroupRules(groupname, ingresses):
    SecurityGroup_Rules = []

    if cfg.LoadBalancer:
        if cfg.LoadBalancerType == "Network":
            return SecurityGroup_Rules

        listeners_cfg = {}
        if cfg.LoadBalancerType == "Classic":
            # get config from ElasticLoadBalancingLoadBalancer key
            for e in cfg.LoadBalancer:
                listeners_cfg.update(
                    getattr(cfg, f"ElasticLoadBalancingLoadBalancer{e}")["Listeners"]
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
                r_SGRule = SecurityGroupRule(resname)
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
            r_SGRule = SecurityGroupRule(resname)
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
        # harcode original title, as is used this way in other part of code/cfg
        mapname = f"{key}{n}"
        resname = f"SecurityGroup{n}"

        # resources
        r_SG = SecurityGroup(resname)
        auto_get_props(r_SG, mapname=mapname)
        try:
            ingresses = v["SecurityGroupIngress"]
        except Exception:
            pass
        else:
            r_SG.SecurityGroupIngress = SG_SecurityGroupRules(mapname, ingresses)

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
        try:
            allowed_ip = v["CidrIp"] == "AllowedIp"
        except Exception:
            pass
        else:
            if allowed_ip:
                for m, w in cfg.AllowedIp.items():
                    r_SGI = SecurityGroupIngress(f"{resname}{m}")
                    auto_get_props(r_SGI, mapname)
                    auto_get_props(r_SGI, f"AllowedIp{m}")
                    r_SGI.Condition = f"AllowedIp{m}"
                    add_obj(r_SGI)
                continue

        r_SGI = SecurityGroupIngress(resname)
        auto_get_props(r_SGI, mapname)
        add_obj(r_SGI)


def EC2_Subnet(key):
    o_subnetprivate = []
    o_subnetpublic = []

    for i in range(cfg.AZones["MAX"]):
        zone_name = cfg.AZoneNames[i]
        zone_cond = f"Zone{zone_name}"

        # parameters
        p_SubnetCidrBlockPrivate = Parameter(
            f"SubnetCidrBlockPrivate{zone_name}",
            Description=f"Ip Class Range for Private Subnet in Zone {zone_name}",
            Default=cfg.VPC_DEFAULT_SUBNETS_CIDR_BLOCK_PRIVATE[i],
        )

        p_SubnetCidrBlockPublic = Parameter(
            f"SubnetCidrBlockPublic{zone_name}",
            Description=f"Ip Class Range for Public Subnet in zone {zone_name}",
            Default=cfg.VPC_DEFAULT_SUBNETS_CIDR_BLOCK_PUBLIC[i],
        )

        add_obj([p_SubnetCidrBlockPrivate, p_SubnetCidrBlockPublic])

        # conditions
        c_Zone = {
            zone_cond: Equals(
                FindInMap("AvabilityZones", Ref("AWS::Region"), f"Zone{i}"), "True"
            )
        }

        add_obj(c_Zone)

        # resources

        r_SubnetPrivate = EC2SubnetPrivate(
            f"SubnetPrivate{zone_name}", zone=zone_name, Condition=zone_cond
        )

        r_SubnetPublic = EC2SubnetPublic(
            f"SubnetPublic{zone_name}", zone=zone_name, Condition=zone_cond
        )

        r_SubnetRouteTableAssociationPrivate = EC2SubnetRouteTableAssociationPrivate(
            f"SubnetRouteTableAssociationPrivate{zone_name}",
            zone=zone_name,
            Condition=zone_cond,
        )

        r_SubnetRouteTableAssociationPublic = EC2SubnetRouteTableAssociationPublic(
            f"SubnetRouteTableAssociationPublic{zone_name}",
            zone=zone_name,
            Condition=zone_cond,
        )

        add_obj(
            [
                r_SubnetPrivate,
                r_SubnetPublic,
                r_SubnetRouteTableAssociationPrivate,
                r_SubnetRouteTableAssociationPublic,
            ]
        )

        # outputs
        o_subnetprivate.append(
            If(zone_cond, Ref(f"SubnetPrivate{zone_name}"), Ref("AWS::NoValue"))
        )

        o_subnetpublic.append(
            If(zone_cond, Ref(f"SubnetPublic{zone_name}"), Ref("AWS::NoValue"))
        )

    # Outputs
    O_SubnetsPrivate = Output(
        "SubnetsPrivate",
        Value=Join(",", o_subnetprivate),
        Export=Export("SubnetsPrivate"),
    )

    O_SubnetsPublic = Output(
        "SubnetsPublic", Value=Join(",", o_subnetpublic), Export=Export("SubnetsPublic")
    )

    add_obj([O_SubnetsPrivate, O_SubnetsPublic])
