import troposphere.ec2 as ec2

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
    get_subvalue, auto_get_props, get_condition)


class EC2VPCPeeringConnection(ec2.VPCPeeringConnection):
    def setup(self):
        self.Condition = 'VPCPeeringConnection'
        self.PeerVpcId = get_expvalue('VpcId-stg', '')
        self.VpcId = get_expvalue('VpcId-dev', '')
        self.Tags = Tags(Name='Dev-Peer-Staging')


class EC2RoutePeeringConnection(ec2.Route):
    def setup(self):
        self.Condition = 'VPCPeeringConnection'
        self.VpcPeeringConnectionId = Ref('VPCPeeringConnectionDevStaging')


class EC2RoutePeeringConnectionDev(EC2RoutePeeringConnection):
    def setup(self):
        super(EC2RoutePeeringConnectionDev, self).setup()
        self.DestinationCidrBlock = get_expvalue('VPCCidr-stg', '')
        self.RouteTableId = get_expvalue('RouteTablePrivate-dev', '')


class EC2RoutePeeringConnectionStg(EC2RoutePeeringConnection):
    def setup(self):
        super(EC2RoutePeeringConnectionStg, self).setup()
        self.DestinationCidrBlock = get_expvalue('VPCCidr-dev', '')
        self.RouteTableId = get_expvalue('RouteTablePrivate-stg', '')


class EC2VPCEndpoint(ec2.VPCEndpoint):
    def setup(self):
        self.RouteTableIds = [ get_expvalue('RouteTablePrivate') ]
        self.VpcId = get_expvalue('VpcId')


class EC2VPCEndpointS3(EC2VPCEndpoint):
    def setup(self):
        super(EC2VPCEndpointS3, self).setup()
        self.ServiceName = Sub('com.amazonaws.${AWS::Region}.s3')

##

class VPC_Endpoint(object):
    def __init__(self, key):
        #Conditions
        do_no_override(True)
        C_S3 = {'EC2VPCEndpointS3': Not(
            Equals(get_endvalue('VPCEndpoint'), 'None')
        )}

        cfg.Conditions.extend([
            C_S3,
        ])
        do_no_override(False)

        # Resources
        R_S3 = EC2VPCEndpointS3('EC2VPCEndpointS3')
        R_S3.setup()
        R_S3.Condition = 'EC2VPCEndpointS3'

        cfg.Resources.extend([
            R_S3,
        ])
