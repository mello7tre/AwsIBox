import troposphere.route53 as r53

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
                     get_subvalue, auto_get_props, get_condition, add_obj)


class R53RecordSet(r53.RecordSetType):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        pass


class R53RecordSetZoneExternal(R53RecordSet):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.HostedZoneId = get_expvalue('HostedZoneIdEnv')
        self.Name = Sub('${AWS::StackName}.${EnvRole}.%s'
                        % cfg.HostedZoneNameRegionEnv)


class R53RecordSetZoneInternal(R53RecordSet):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.HostedZoneId = get_expvalue('HostedZoneIdPrivate')
        self.Name = Sub('${AWS::StackName}.${EnvRole}.%s'
                        % cfg.HostedZoneNamePrivate)


class R53RecordSetCloudFront(R53RecordSetZoneExternal):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.Condition = 'RecordSetCloudFront'
        self.AliasTarget = r53.AliasTarget(
            DNSName=GetAtt('CloudFrontDistribution', 'DomainName'),
            HostedZoneId=cfg.HostedZoneIdCF
        )
        self.Name = Sub('${EnvRole}${RecordSetCloudFrontSuffix}.cdn.%s'
                        % cfg.HostedZoneNameEnv)
        self.Type = 'A'


class R53RecordSetLoadBalancer(R53RecordSet):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.AliasTarget = r53.AliasTarget(
            HostedZoneId=get_endvalue('HostedZoneIdLB')
        )
        self.Type = 'A'


class R53RecordSetEC2LoadBalancerExternal(
        R53RecordSetLoadBalancer, R53RecordSetZoneExternal):
    pass


class R53RecordSetEC2LoadBalancerInternal(
        R53RecordSetLoadBalancer, R53RecordSetZoneInternal):
    pass


class R53RecordSetECSLoadBalancer(R53RecordSetLoadBalancer):
    def __init__(self, title, scheme, **kwargs):
        super().__init__(title, **kwargs)
        self.AliasTarget.DNSName = get_subvalue(
            'dualstack.${1E}',
            f'LoadBalancerApplication{scheme}DNS',
            'LoadBalancerApplicationStack'
        )


class R53RecordSetECSLoadBalancerApplicationExternal(
        R53RecordSetECSLoadBalancer, R53RecordSetZoneExternal):
    pass


class R53RecordSetECSLoadBalancerApplicationInternal(
        R53RecordSetECSLoadBalancer, R53RecordSetZoneInternal):
    pass


class R53RecordSetEFS(R53RecordSet):
    def __init__(self, title, efsname, **kwargs):
        super().__init__(title, **kwargs)
        condname = f'EFSFileSystem{efsname}'
        self.Condition = condname
        self.HostedZoneId = Ref('HostedZonePrivate')
        self.Name = Sub('efs-%s.%s' % (efsname, cfg.HostedZoneNamePrivate))
        self.ResourceRecords = [
            Sub('${%s}.efs.${AWS::Region}.amazonaws.com' % condname)
        ]
        self.Type = 'CNAME'
        self.TTL = '300'


class R53RecordSetRDS(R53RecordSet):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.Type = 'CNAME'
        self.ResourceRecords = [GetAtt('DBInstance', 'Endpoint.Address')]
        self.TTL = '300'


class R53RecordSetRDSExternal(R53RecordSetRDS, R53RecordSetZoneExternal):
    pass


class R53RecordSetRDSInternal(R53RecordSetRDS, R53RecordSetZoneInternal):
    pass


class R53RecordSetCCH(R53RecordSet):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.Condition = 'CacheEnabled'
        self.Type = 'CNAME'
        self.ResourceRecords = If(
                'EngineMemCached',
                [GetAtt(
                    'ElastiCacheCacheCluster',
                    'ConfigurationEndpoint.Address')],
                If(
                    'ReplicationGroup',
                    [GetAtt(
                        'ElastiCacheReplicationGroup',
                        'PrimaryEndPoint.Address')],
                    [GetAtt(
                        'ElastiCacheCacheCluster',
                        'RedisEndpoint.Address')],
                )
            )
        # if cfg.Engine == 'memcached':
        #     self.ResourceRecords = [GetAtt(
        #         'CacheCluster', 'ConfigurationEndpoint.Address')]
        # if cfg.Engine == 'redis':
        #     self.ResourceRecords = [GetAtt(
        #         'CacheCluster', 'RedisEndpoint.Address')]
        self.TTL = '300'


class R53RecordSetCCHRO(R53RecordSetCCH):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.Condition = 'ReplicationGroup'
        self.ResourceRecords = [Sub(
            '${RECORD0}-ro.'
            '${RECORD1}.'
            '${RECORD2}.'
            '${RECORD3}.'
            '${RECORD4}.'
            '${RECORD5}.'
            '${RECORD6}.'
            '${RECORD7}', **{
                'RECORD0': Select(0, Split('.', GetAtt(
                    'ElastiCacheReplicationGroup',
                    'PrimaryEndPoint.Address'))),
                'RECORD1': Select(1, Split('.', GetAtt(
                    'ElastiCacheReplicationGroup',
                    'PrimaryEndPoint.Address'))),
                'RECORD2': Select(2, Split('.', GetAtt(
                    'ElastiCacheReplicationGroup',
                    'PrimaryEndPoint.Address'))),
                'RECORD3': Select(3, Split('.', GetAtt(
                    'ElastiCacheReplicationGroup',
                    'PrimaryEndPoint.Address'))),
                'RECORD4': Select(4, Split('.', GetAtt(
                    'ElastiCacheReplicationGroup',
                    'PrimaryEndPoint.Address'))),
                'RECORD5': Select(5, Split('.', GetAtt(
                    'ElastiCacheReplicationGroup',
                    'PrimaryEndPoint.Address'))),
                'RECORD6': Select(6, Split('.', GetAtt(
                    'ElastiCacheReplicationGroup',
                    'PrimaryEndPoint.Address'))),
                'RECORD7': Select(7, Split('.', GetAtt(
                    'ElastiCacheReplicationGroup',
                    'PrimaryEndPoint.Address'))),
            }
        )]


class R53RecordSetCCHExternal(R53RecordSetCCH, R53RecordSetZoneExternal):
    pass


class R53RecordSetCCHInternal(R53RecordSetCCH, R53RecordSetZoneInternal):
    pass


class R53RecordSetCCHExternalRO(R53RecordSetCCHRO, R53RecordSetZoneExternal):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.Name = Sub('${AWS::StackName}.${EnvRole}_ro.%s'
                        % cfg.HostedZoneNameRegionEnv)


class R53RecordSetCCHInternalRO(R53RecordSetCCHRO, R53RecordSetZoneInternal):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.Name = Sub('${AWS::StackName}.${EnvRole}_ro.%s'
                        % cfg.HostedZoneNamePrivate)


class R53RecordSetNSServiceDiscovery(R53RecordSet):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.HostedZoneId = Ref('HostedZoneEnv')
        self.Name = Sub('find.%s' % cfg.HostedZoneNameEnv)
        self.ResourceRecords = GetAtt('PublicDnsNamespace', 'NameServers')
        self.Type = 'NS'
        self.TTL = '300'


class R53RecordApiGatewayDomainName(R53RecordSetZoneExternal):
    def __init__(self, title, name, domain_name, zoneid_name, **kwargs):
        super().__init__(title, **kwargs)
        self.AliasTarget = r53.AliasTarget(
            DNSName=GetAtt(name, domain_name),
            HostedZoneId=GetAtt(name, zoneid_name)
        )
        self.Name = Ref(name)
        self.Type = 'A'


# #################################
# ### START STACK INFRA CLASSES ###
# #################################


class R53_RecordSetCloudFront(object):
    def __init__(self):
        # Resources
        R_RecordSet = R53RecordSetCloudFront('RecordSetCloudFront')

        add_obj([
            R_RecordSet,
        ])


class R53_RecordSetEC2LoadBalancer(object):
    def __init__(self):
        # Resources

        # RecordSet External
        if cfg.RecordSetExternal:
            R_External = R53RecordSetEC2LoadBalancerExternal(
                'RecordSetExternal')

            # LoadBalancerClassic
            if cfg.LoadBalancerClassicExternal:
                R_External.AliasTarget.DNSName = Sub(
                    'dualstack.${LoadBalancerClassicExternal.DNSName}')
            elif cfg.LoadBalancerClassicInternal:
                R_External.AliasTarget.DNSName = Sub(
                    'dualstack.${LoadBalancerClassicInternal.DNSName}')

            # LoadBalancerApplication
            if cfg.LoadBalancerApplicationExternal:
                R_External.AliasTarget.DNSName = Sub(
                    'dualstack.${LoadBalancerApplicationExternal.DNSName}')
            elif cfg.LoadBalancerApplicationInternal:
                R_External.AliasTarget.DNSName = Sub(
                    'dualstack.${LoadBalancerApplicationInternal.DNSName}')

            add_obj(R_External)

            # outputs
            O_External = Output('RecordSetExternal')
            O_External.Value = Ref('RecordSetExternal')

            add_obj(O_External)

        # RecordSet Internal
        if cfg.RecordSetInternal:
            R_Internal = R53RecordSetEC2LoadBalancerInternal(
                'RecordSetInternal')

            # LoadBalancerClassic
            if cfg.LoadBalancerClassicInternal:
                R_Internal.AliasTarget.DNSName = Sub(
                    'dualstack.${LoadBalancerClassicInternal.DNSName}')
            elif cfg.LoadBalancerClassicExternal:
                R_Internal.AliasTarget.DNSName = Sub(
                    'dualstack.${LoadBalancerClassicExternal.DNSName}')

            # LoadBalancerApplication
            if cfg.LoadBalancerApplicationInternal:
                R_Internal.AliasTarget.DNSName = Sub(
                    'dualstack.${LoadBalancerApplicationInternal.DNSName}')
            elif cfg.LoadBalancerApplicationExternal:
                R_Internal.AliasTarget.DNSName = Sub(
                    'dualstack.${LoadBalancerApplicationExternal.DNSName}')

            add_obj(R_Internal)

            # outputs
            O_Internal = Output('RecordSetInternal')
            O_Internal.Value = Ref('RecordSetInternal')

            add_obj(O_Internal)


class R53_RecordSetECSLoadBalancer(object):
    def __init__(self):
        # Resources
        if cfg.RecordSetExternal:
            if cfg.LoadBalancerApplicationExternal:
                R_External = R53RecordSetECSLoadBalancerApplicationExternal(
                    'RecordSetExternal', scheme='External')
            else:
                R_External = R53RecordSetECSLoadBalancerApplicationExternal(
                    'RecordSetExternal', scheme='Internal')

            add_obj(R_External)

            # outputs
            O_External = Output('RecordSetExternal')
            O_External.Value = Ref('RecordSetExternal')

            add_obj(O_External)

        if cfg.RecordSetInternal:

            if cfg.LoadBalancerApplicationInternal:
                R_Internal = R53RecordSetECSLoadBalancerApplicationInternal(
                    'RecordSetInternal', scheme='Internal')
            else:
                R_Internal = R53RecordSetECSLoadBalancerApplicationInternal(
                    'RecordSetInternal', scheme='External')

            add_obj(R_Internal)

            # outputs
            O_Internal = Output('RecordSetInternal')
            O_Internal.Value = Ref('RecordSetInternal')

            add_obj(O_Internal)


class R53_RecordSetRDS(object):
    def __init__(self):
        # Resources
        if cfg.RecordSetExternal:
            R_External = R53RecordSetRDSExternal('RecordSetExternal')
            add_obj(R_External)

            # outputs
            O_External = Output('RecordSetExternal')
            O_External.Value = Ref('RecordSetExternal')

            add_obj(O_External)

        if cfg.RecordSetInternal:
            R_Internal = R53RecordSetRDSInternal('RecordSetInternal')
            add_obj(R_Internal)

            # outputs
            O_Internal = Output('RecordSetInternal')
            O_Internal.Value = Ref('RecordSetInternal')

            add_obj(O_Internal)


class R53_RecordSetCCH(object):
    def __init__(self):
        # Resources
        if cfg.RecordSetExternal:
            R_External = R53RecordSetCCHExternal('RecordSetExternal')
            R_ExternalRO = R53RecordSetCCHExternalRO('RecordSetExternalRO')
            add_obj([
                R_External,
                R_ExternalRO,
            ])

            # outputs
            O_External = Output('RecordSetExternal')
            O_External.Value = Ref('RecordSetExternal')
            O_External.Condition = 'CacheEnabled'

            O_ExternalRO = Output('RecordSetExternalRO')
            O_ExternalRO.Value = Ref('RecordSetExternalRO')
            O_ExternalRO.Condition = 'ReplicationGroup'

            add_obj([
                O_External,
                O_ExternalRO,
            ])

        if cfg.RecordSetInternal:
            R_Internal = R53RecordSetCCHInternal('RecordSetInternal')
            R_InternalRO = R53RecordSetCCHInternalRO('RecordSetInternalRO')
            add_obj([
                R_Internal,
                R_InternalRO,
            ])

            # outputs
            O_Internal = Output('RecordSetInternal')
            O_Internal.Value = Ref('RecordSetInternal')
            O_Internal.Condition = 'CacheEnabled'

            O_InternalRO = Output('RecordSetInternalRO')
            O_InternalRO.Value = Ref('RecordSetInternalRO')
            O_InternalRO.Condition = 'ReplicationGroup'

            add_obj([
                O_Internal,
                O_InternalRO,
            ])


class R53_HostedZones(object):
    def __init__(self, key):
        for n, v in getattr(cfg, key).items():
            mapname = f'{key}{n}'
            resname = v['ResourceName']
            output_zonename = resname.replace('HostedZone', 'HostedZoneName')
            output_zoneidname = resname.replace('HostedZone', 'HostedZoneId')
            # parameters
            if n.startswith('Public'):
                p_HostedZone = Parameter(f'{mapname}Enabled')
                p_HostedZone.Description = (
                    f'Create Public {resname} - can be created in only one '
                    'Region - empty for default based on env/role')

                p_HostedZoneId = Parameter(f'{mapname}Id')
                p_HostedZoneId.Description = (
                    f'Id of Public {resname} - required in all Regions where'
                    ' HostedZonePublicEnv is not created - '
                    'empty for default based on env/role')

                add_obj([
                    p_HostedZone,
                    p_HostedZoneId,
                ])

                # conditions
                c_Enabled = get_condition(
                    resname, 'not_equals', 'None', f'{mapname}Enabled')

                add_obj(c_Enabled)

            # resources
            r_HostedZone = r53.HostedZone(v['ResourceName'])
            auto_get_props(r_HostedZone, v, recurse=True, mapname=mapname)

            if n.startswith('Public'):
                r_HostedZone.Condition = resname

            add_obj(r_HostedZone)

            # outputs
            o_HostedZoneName = Output(output_zonename)
            # o_HostedZoneName.Value = Sub(cfg.HostedZoneNamePrivate)
            o_HostedZoneName.Value = get_endvalue(f'{mapname}Name')

            o_HostedZoneId = Output(output_zoneidname)
            o_HostedZoneId.Value = If(
                resname,
                Ref(resname),
                get_endvalue(f'{mapname}Id')
            ) if n.startswith('Public') else Ref(resname)
            o_HostedZoneId.Export = Export(output_zoneidname)

            add_obj([
                o_HostedZoneName,
                o_HostedZoneId,
            ])
