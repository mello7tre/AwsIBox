import troposphere.ec2 as ec2

from .common import *
from .shared import (Parameter, get_endvalue, get_expvalue, get_subvalue,
                     auto_get_props, get_condition, add_obj)


class EC2VPCPeeringConnection(ec2.VPCPeeringConnection):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.Condition = 'VPCPeeringConnection'
        self.PeerVpcId = get_expvalue('VpcId-stg', '')
        self.VpcId = get_expvalue('VpcId-dev', '')
        self.Tags = Tags(Name='Dev-Peer-Staging')


class EC2RouteNatGateway(ec2.Route):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.DestinationCidrBlock = '0.0.0.0/0'
        self.NatGatewayId = Ref('NatGateway')
        self.RouteTableId = Ref('RouteTablePrivate')


class EC2RouteInternetGateway(ec2.Route):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.DestinationCidrBlock = '0.0.0.0/0'
        self.GatewayId = Ref('InternetGateway')
        self.RouteTableId = Ref('RouteTablePublic')


class EC2RoutePeeringConnection(ec2.Route):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.Condition = 'VPCPeeringConnection'
        self.VpcPeeringConnectionId = Ref('VPCPeeringConnectionDevStaging')


class EC2RoutePeeringConnectionDev(EC2RoutePeeringConnection):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.DestinationCidrBlock = get_expvalue('VPCCidr-stg', '')
        self.RouteTableId = get_expvalue('RouteTablePrivate-dev', '')


class EC2RoutePeeringConnectionStg(EC2RoutePeeringConnection):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.DestinationCidrBlock = get_expvalue('VPCCidr-dev', '')
        self.RouteTableId = get_expvalue('RouteTablePrivate-stg', '')


class EC2VPCEndpoint(ec2.VPCEndpoint):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.RouteTableIds = [get_expvalue('RouteTablePrivate')]
        self.VpcId = get_expvalue('VpcId')


class EC2VPCEndpointS3(EC2VPCEndpoint):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.ServiceName = Sub('com.amazonaws.${AWS::Region}.s3')


class EC2VPC(ec2.VPC):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.CidrBlock = Ref('VPCCidrBlock')
        self.EnableDnsSupport = True
        self.EnableDnsHostnames = True


class EC2Subnet(ec2.Subnet):
    def __init__(self, title, zone, **kwargs):
        super().__init__(title, **kwargs)
        self.AvailabilityZone = Sub('${AWS::Region}%s' % zone.lower())
        self.VpcId = Ref('VPC')


class EC2SubnetPrivate(EC2Subnet):
    def __init__(self, title, zone, **kwargs):
        super().__init__(title, zone, **kwargs)
        self.CidrBlock = Ref(f'SubnetCidrBlockPrivate{zone}')
        self.MapPublicIpOnLaunch = False
        self.Tags = Tags(Name=Sub('${VPCName}-Private%s' % zone))


class EC2SubnetPublic(EC2Subnet):
    def __init__(self, title, zone, **kwargs):
        super().__init__(title, zone, **kwargs)
        self.CidrBlock = Ref(f'SubnetCidrBlockPublic{zone}')
        self.MapPublicIpOnLaunch = True
        self.Tags = Tags(Name=Sub('${VPCName}-Public%s' % zone))


class EC2RouteTable(ec2.RouteTable):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.VpcId = Ref('VPC')


class EC2SubnetRouteTableAssociationPrivate(ec2.SubnetRouteTableAssociation):
    def __init__(self, title, zone, **kwargs):
        super().__init__(title, **kwargs)
        self.RouteTableId = Ref('RouteTablePrivate')
        self.SubnetId = Ref(f'SubnetPrivate{zone}')


class EC2SubnetRouteTableAssociationPublic(ec2.SubnetRouteTableAssociation):
    def __init__(self, title, zone, **kwargs):
        super().__init__(title, **kwargs)
        self.RouteTableId = Ref('RouteTablePublic')
        self.SubnetId = Ref(f'SubnetPublic{zone}')
##


def VPC_Endpoint(key):
    # Conditions
    c_VPCEndpoint = get_condition(
        'EC2VPCEndpointS3', 'not_equals', 'None', 'VPCEndpoint')

    add_obj(c_VPCEndpoint)

    # Resources
    R_S3 = EC2VPCEndpointS3('EC2VPCEndpointS3')
    R_S3.Condition = 'EC2VPCEndpointS3'

    add_obj([
        R_S3])


def VPC_VPC(key):
    vpc_net = '10.80'
    o_subnetprivate = []
    o_subnetpublic = []

    # Resources
    R_VPC = ec2.VPC('VPC')
    auto_get_props(R_VPC, f'{key}Base')

    R_RouteTablePrivate = EC2RouteTable('RouteTablePrivate')
    R_RouteTablePrivate.Tags = Tags(Name=Sub('${VPCName}-Private'))

    R_RouteTablePublic = EC2RouteTable('RouteTablePublic')
    R_RouteTablePublic.Tags = Tags(Name=Sub('${VPCName}-Public'))

    R_InternetGateway = ec2.InternetGateway('InternetGateway')
    R_InternetGateway.Tags = Tags(Name=Ref('VPCName'))

    R_VPCGatewayAttachment = ec2.VPCGatewayAttachment(
        'VPCGatewayAttachment')
    R_VPCGatewayAttachment.InternetGatewayId = Ref('InternetGateway')
    R_VPCGatewayAttachment.VpcId = Ref('VPC')

    if cfg.NatGateway != 'None':
        # resources
        R_EIPNat = ec2.EIP('EIPNat')
        R_EIPNat.Domain = 'vpc'

        R_NatGateway = ec2.NatGateway('NatGateway')
        R_NatGateway.AllocationId = GetAtt('EIPNat', 'AllocationId')
        R_NatGateway.SubnetId = Ref('SubnetPublicA')

        R_RouteNatGateway = EC2RouteNatGateway('RouteNatGateway')

        # outputs
        O_EIPNat = Output('EIPNat')
        O_EIPNat.Value = Ref('EIPNat')

        add_obj([
            R_NatGateway,
            R_RouteNatGateway,
            R_EIPNat,
            O_EIPNat])

    R_RouteInternetGateway = EC2RouteInternetGateway(
        'RouteInternetGateway')

    add_obj([
        R_VPC,
        R_RouteTablePrivate,
        R_RouteTablePublic,
        R_InternetGateway,
        R_VPCGatewayAttachment,
        R_RouteInternetGateway])

    for i in range(cfg.AZones['MAX']):
        zone_name = cfg.AZoneNames[i]
        zone_cond = f'Zone{zone_name}'

        # parameters
        p_SubnetCidrBlockPrivate = Parameter(
            f'SubnetCidrBlockPrivate{zone_name}')
        p_SubnetCidrBlockPrivate.Description = (
            f'Ip Class Range for Private Subnet in Zone {zone_name}')
        p_SubnetCidrBlockPrivate.Default = f'{vpc_net}.{i * 16}.0/20'

        p_SubnetCidrBlockPublic = Parameter(
            f'SubnetCidrBlockPublic{zone_name}')
        p_SubnetCidrBlockPublic.Description = (
            f'Ip Class Range for Public Subnet in zone {zone_name}')
        p_SubnetCidrBlockPublic.Default = f'{vpc_net}.{i + 200}.0/24'

        add_obj([
            p_SubnetCidrBlockPrivate,
            p_SubnetCidrBlockPublic])

        # conditions
        c_Zone = {zone_cond: Equals(
            FindInMap(
                'AvabilityZones',
                Ref('AWS::Region'),
                f'Zone{i}'
            ),
            'True')}

        add_obj(c_Zone)

        # resources

        r_SubnetPrivate = EC2SubnetPrivate(
            f'SubnetPrivate{zone_name}', zone=zone_name)
        r_SubnetPrivate.Condition = zone_cond

        r_SubnetPublic = EC2SubnetPublic(
            f'SubnetPublic{zone_name}', zone=zone_name)
        r_SubnetPublic.Condition = zone_cond

        r_SubnetRouteTableAssociationPrivate = (
            EC2SubnetRouteTableAssociationPrivate(
                f'SubnetRouteTableAssociationPrivate{zone_name}',
                zone=zone_name))
        r_SubnetRouteTableAssociationPrivate.Condition = zone_cond

        r_SubnetRouteTableAssociationPublic = (
            EC2SubnetRouteTableAssociationPublic(
                f'SubnetRouteTableAssociationPublic{zone_name}',
                zone=zone_name))
        r_SubnetRouteTableAssociationPublic.Condition = zone_cond

        add_obj([
            r_SubnetPrivate,
            r_SubnetPublic,
            r_SubnetRouteTableAssociationPrivate,
            r_SubnetRouteTableAssociationPublic])

        # outputs
        o_subnetprivate.append(If(
            zone_cond,
            Ref(f'SubnetPrivate{zone_name}'),
            Ref('AWS::NoValue')
        ))

        o_subnetpublic.append(If(
            zone_cond,
            Ref(f'SubnetPublic{zone_name}'),
            Ref('AWS::NoValue')
        ))

    # Outputs
    O_SubnetsPrivate = Output('SubnetsPrivate')
    O_SubnetsPrivate.Value = Join(',', o_subnetprivate)
    O_SubnetsPrivate.Export = Export('SubnetsPrivate')

    O_SubnetsPublic = Output('SubnetsPublic')
    O_SubnetsPublic.Value = Join(',', o_subnetpublic)
    O_SubnetsPublic.Export = Export('SubnetsPublic')

    add_obj([
        O_SubnetsPrivate,
        O_SubnetsPublic])
