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


##


def EC2_Subnet(key):
    o_subnetprivate = []
    o_subnetpublic = []

    for i in range(cfg.AZones["MAX"]):
        zone_name = cfg.AZoneNames[i]
        zone_cond = f"Zone{zone_name}"

        # parameters
        p_SubnetCidrBlockPrivate = Parameter(f"SubnetCidrBlockPrivate{zone_name}")
        p_SubnetCidrBlockPrivate.Description = (
            f"Ip Class Range for Private Subnet in Zone {zone_name}"
        )
        p_SubnetCidrBlockPrivate.Default = cfg.VPC_DEFAULT_SUBNETS_CIDR_BLOCK_PRIVATE[i]

        p_SubnetCidrBlockPublic = Parameter(f"SubnetCidrBlockPublic{zone_name}")
        p_SubnetCidrBlockPublic.Description = (
            f"Ip Class Range for Public Subnet in zone {zone_name}"
        )
        p_SubnetCidrBlockPublic.Default = cfg.VPC_DEFAULT_SUBNETS_CIDR_BLOCK_PUBLIC[i]

        add_obj([p_SubnetCidrBlockPrivate, p_SubnetCidrBlockPublic])

        # conditions
        c_Zone = {
            zone_cond: Equals(
                FindInMap("AvabilityZones", Ref("AWS::Region"), f"Zone{i}"), "True"
            )
        }

        add_obj(c_Zone)

        # resources

        r_SubnetPrivate = EC2SubnetPrivate(f"SubnetPrivate{zone_name}", zone=zone_name)
        r_SubnetPrivate.Condition = zone_cond

        r_SubnetPublic = EC2SubnetPublic(f"SubnetPublic{zone_name}", zone=zone_name)
        r_SubnetPublic.Condition = zone_cond

        r_SubnetRouteTableAssociationPrivate = EC2SubnetRouteTableAssociationPrivate(
            f"SubnetRouteTableAssociationPrivate{zone_name}", zone=zone_name
        )
        r_SubnetRouteTableAssociationPrivate.Condition = zone_cond

        r_SubnetRouteTableAssociationPublic = EC2SubnetRouteTableAssociationPublic(
            f"SubnetRouteTableAssociationPublic{zone_name}", zone=zone_name
        )
        r_SubnetRouteTableAssociationPublic.Condition = zone_cond

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
    O_SubnetsPrivate = Output("SubnetsPrivate")
    O_SubnetsPrivate.Value = Join(",", o_subnetprivate)
    O_SubnetsPrivate.Export = Export("SubnetsPrivate")

    O_SubnetsPublic = Output("SubnetsPublic")
    O_SubnetsPublic.Value = Join(",", o_subnetpublic)
    O_SubnetsPublic.Export = Export("SubnetsPublic")

    add_obj([O_SubnetsPrivate, O_SubnetsPublic])
