import troposphere.servicediscovery as srvd

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
                     get_subvalue, auto_get_props, get_condition, add_obj)


class ServiceDiscoveryPublicDnsNamespace(srvd.PublicDnsNamespace):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.Description = 'Service Discovery'
        self.Name = Sub(f'find.{cfg.HostedZoneNameEnv}')


class SRVD_ServiceDiscoveryRES(object):
    def __init__(self, key):
        resname = 'PublicDnsNamespace'
        mapname = 'ServiceDiscovery'
        # Parameters
        P_PublicDnsNamespace = Parameter(f'{mapname}Enabled')
        P_PublicDnsNamespace.Description = (
            'Create {mapaname}{resname} - '
            'can be created in only one Region - '
            'empty for default based on env/role')
        
        P_PublicDnsNamespaceId = Parameter(f'{mapname}Id')
        P_PublicDnsNamespaceId.Description = (
            f'Id of {mapname }{resname} - required in all Regions where '
            f'{resname} is not created - '
            'empty for default based on env/role')

        add_obj([
            P_PublicDnsNamespace,
            P_PublicDnsNamespaceId,
        ])

        # Conditions
        C_Enabled = get_condition(
            resname, 'not_equals', 'None', f'{mapname}Enabled')

        add_obj(C_Enabled)

        # Resources
        R_PublicDnsNamespace = ServiceDiscoveryPublicDnsNamespace(
            resname)
        R_PublicDnsNamespace.Condition = resname

        add_obj([
            R_PublicDnsNamespace,
        ])

        # Outputs
        O_PublicDnsNamespace = Output(
            f'ServiceDiscovery{resname}Id')
        O_PublicDnsNamespace.Value = If(
            resname,
            Ref(resname),
            Ref(f'{mapname}Id'),
        )
        O_PublicDnsNamespace.Export = Export(
            f'ServiceDiscovery{resname}Id')

        add_obj([
            O_PublicDnsNamespace,
        ])
