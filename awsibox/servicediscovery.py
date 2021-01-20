import troposphere.servicediscovery as srvd

from .common import *
from .shared import (Parameter, get_endvalue, get_expvalue, get_subvalue,
                     auto_get_props, get_condition, add_obj)


class ServiceDiscoveryPublicDnsNamespace(srvd.PublicDnsNamespace):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.Description = 'Service Discovery'
        self.Name = Sub(f'find.{cfg.HostedZoneNameEnv}')


def SRVD_ServiceDiscoveryRES(key):
    # Resources
    R_PublicDnsNamespace = ServiceDiscoveryPublicDnsNamespace(
        'PublicDnsNamespace')

    # Outputs
    O_PublicDnsNamespace = Output(
        'ServiceDiscoveryPublicDnsNamespaceId')
    O_PublicDnsNamespace.Value = Ref(
        'PublicDnsNamespace')
    O_PublicDnsNamespace.Export = Export(
        'ServiceDiscoveryPublicDnsNamespaceId')

    add_obj([
        R_PublicDnsNamespace,
        O_PublicDnsNamespace])
