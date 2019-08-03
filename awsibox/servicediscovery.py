import troposphere.servicediscovery  as srvd

from shared import *


class ServiceDiscoveryPublicDnsNamespace(srvd.PublicDnsNamespace):
    def setup(self):
        self.Description = 'Service Discovery'
        self.Name = Sub('find.' + RP_cmm['HostedZoneNameEnv'])


class SRVD_ServiceDiscoveryRES(object):
    def __init__(self, key):
        # Resources
        R_PublicDnsNamespace = ServiceDiscoveryPublicDnsNamespace('PublicDnsNamespace')
        R_PublicDnsNamespace.setup()

        cfg.Resources.extend([
            R_PublicDnsNamespace,
        ])

        # Outputs
        O_PublicDnsNamespace = Output('ServiceDiscoveryPublicDnsNamespaceId')
        O_PublicDnsNamespace.Value = Ref('PublicDnsNamespace')
        O_PublicDnsNamespace.Export = Export('ServiceDiscoveryPublicDnsNamespaceId')

        cfg.Outputs.extend([
            O_PublicDnsNamespace,
        ])

# Need to stay as last lines
import_modules(globals())
