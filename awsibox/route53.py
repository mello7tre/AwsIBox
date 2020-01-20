import troposphere.route53 as r53

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
    get_subvalue, auto_get_props, get_condition, add_obj)


class R53RecordSet(r53.RecordSetType):
    def setup(self):
        pass


class R53RecordSetZoneExternal(R53RecordSet):
    def setup(self):
        super(R53RecordSetZoneExternal, self).setup()
        self.HostedZoneId = get_expvalue('HostedZoneIdEnv')
        self.Name = Sub('${AWS::StackName}.${EnvRole}.' + cfg.HostedZoneNameRegionEnv)  # Ex. prt-a-d.client-portal.eu-west-1.dev..


class R53RecordSetZoneInternal(R53RecordSet):
    def setup(self):
        super(R53RecordSetZoneInternal, self).setup()
        self.HostedZoneId = get_expvalue('HostedZoneIdPrivate')
        self.Name = Sub('${AWS::StackName}.${EnvRole}.' + cfg.HostedZoneNamePrivate)  # Ex. prt-a-d.client-portal.internal..


class R53RecordSetCloudFront(R53RecordSetZoneExternal):
    def setup(self):
        super(R53RecordSetCloudFront, self).setup()
        self.Condition = 'RecordSetCloudFront'
        self.AliasTarget = r53.AliasTarget(
            DNSName=GetAtt('CloudFrontDistribution', 'DomainName'),
            HostedZoneId=cfg.HostedZoneIdCF
        )
        self.Name = Sub('${EnvRole}${RecordSetCloudFrontSuffix}.cdn.' + cfg.HostedZoneNameEnv)  # Ex. client-portal.cdn.dev..
        self.Type = 'A'


class R53RecordSetLoadBalancer(R53RecordSet):
    def setup(self):
        super(R53RecordSetLoadBalancer, self).setup()
        self.AliasTarget = r53.AliasTarget(
            HostedZoneId=get_endvalue('HostedZoneIdLB')
        )
        self.Type = 'A'


class R53RecordSetEC2LoadBalancerExternal(R53RecordSetLoadBalancer, R53RecordSetZoneExternal):
    pass


class R53RecordSetEC2LoadBalancerInternal(R53RecordSetLoadBalancer, R53RecordSetZoneInternal):
    pass


class R53RecordSetECSLoadBalancer(R53RecordSetLoadBalancer):
    def setup(self, scheme):
        super(R53RecordSetECSLoadBalancer, self).setup()
        self.AliasTarget.DNSName = get_subvalue(
            'dualstack.${1E}',
            'LoadBalancerApplication%sDNS' % scheme,
            'LoadBalancerApplicationStack'
        ) 


class R53RecordSetECSLoadBalancerApplicationExternal(R53RecordSetECSLoadBalancer, R53RecordSetZoneExternal):
    pass


class R53RecordSetECSLoadBalancerApplicationInternal(R53RecordSetECSLoadBalancer, R53RecordSetZoneInternal):
    pass


class R53RecordSetEFS(R53RecordSet):
    def setup(self, efsname):
        super(R53RecordSetEFS, self).setup()
        condname = 'EFSFileSystem' + efsname  # Ex. EFSFileSystemWordPress
        self.Condition = condname
        self.HostedZoneId = Ref('HostedZonePrivate')
        self.Name = Sub('efs-%s.%s' % (efsname, cfg.HostedZoneNamePrivate))
        self.ResourceRecords = [
            Sub('${%s}.efs.${AWS::Region}.amazonaws.com' % condname)
        ]
        self.Type = 'CNAME'
        self.TTL = '300'


class R53RecordSetRDS(R53RecordSet):
    def setup(self):
        super(R53RecordSetRDS, self).setup()
        self.Type = 'CNAME'
        self.ResourceRecords = [GetAtt('DBInstance', 'Endpoint.Address')]
        self.TTL = '300'


class R53RecordSetRDSExternal(R53RecordSetRDS, R53RecordSetZoneExternal):
    pass


class R53RecordSetRDSInternal(R53RecordSetRDS, R53RecordSetZoneInternal):
    pass


class R53RecordSetCCH(R53RecordSet):
    def setup(self):
        super(R53RecordSetCCH, self).setup()
        self.Condition = 'CacheEnabled'
        self.Type = 'CNAME'
        if cfg.Engine == 'memcached':
            self.ResourceRecords = [GetAtt('CacheCluster', 'ConfigurationEndpoint.Address')]
        if cfg.Engine == 'redis':
            self.ResourceRecords = [GetAtt('CacheCluster', 'RedisEndpoint.Address')]
        self.TTL = '300'


class R53RecordSetCCHExternal(R53RecordSetCCH, R53RecordSetZoneExternal):
    pass


class R53RecordSetCCHInternal(R53RecordSetCCH, R53RecordSetZoneInternal):
    pass


class R53RecordSetNSServiceDiscovery(R53RecordSet):
    def setup(self):
        self.HostedZoneId = Ref('HostedZoneEnv')
        self.Name = Sub('find.' + cfg.HostedZoneNameEnv)
        self.ResourceRecords = GetAtt('PublicDnsNamespace', 'NameServers')
        self.Type = 'NS'
        self.TTL = '300'


# #################################
# ### START STACK INFRA CLASSES ###
# #################################


class R53_RecordSetCloudFront(object):
    def __init__(self):
       # Resources
        R_RecordSet = R53RecordSetCloudFront('RecordSetCloudFront')
        R_RecordSet.setup()

        add_obj([
            R_RecordSet,
        ])


class R53_RecordSetEC2LoadBalancer(object):
    def __init__(self):
        # Resources

        # RecordSet External
        if cfg.RecordSetExternal:
            R_External = R53RecordSetEC2LoadBalancerExternal('RecordSetExternal')
            R_External.setup()

            # LoadBalancerClassic
            if cfg.LoadBalancerClassicExternal:
                R_External.AliasTarget.DNSName = Sub('dualstack.${LoadBalancerClassicExternal.DNSName}')
            elif cfg.LoadBalancerClassicInternal:
                R_External.AliasTarget.DNSName = Sub('dualstack.${LoadBalancerClassicInternal.DNSName}')

            # LoadBalancerApplication
            if cfg.LoadBalancerApplicationExternal:
                R_External.AliasTarget.DNSName = Sub('dualstack.${LoadBalancerApplicationExternal.DNSName}')
            elif cfg.LoadBalancerApplicationInternal:
                R_External.AliasTarget.DNSName = Sub('dualstack.${LoadBalancerApplicationInternal.DNSName}')

            add_obj(R_External)

            # outputs
            O_External = Output('RecordSetExternal')
            O_External.Value = Ref('RecordSetExternal')

            add_obj(O_External)

        # RecordSet Internal
        if cfg.RecordSetInternal:
            R_Internal = R53RecordSetEC2LoadBalancerInternal('RecordSetInternal')
            R_Internal.setup()

            # LoadBalancerClassic
            if cfg.LoadBalancerClassicInternal:
                R_Internal.AliasTarget.DNSName = Sub('dualstack.${LoadBalancerClassicInternal.DNSName}')
            elif cfg.LoadBalancerClassicExternal:
                R_Internal.AliasTarget.DNSName = Sub('dualstack.${LoadBalancerClassicExternal.DNSName}')

            # LoadBalancerApplication
            if cfg.LoadBalancerApplicationInternal:
                R_Internal.AliasTarget.DNSName = Sub('dualstack.${LoadBalancerApplicationInternal.DNSName}')
            elif cfg.LoadBalancerApplicationExternal:
                R_Internal.AliasTarget.DNSName = Sub('dualstack.${LoadBalancerApplicationExternal.DNSName}')

            add_obj(R_Internal)

            # outputs
            O_Internal = Output('RecordSetInternal')
            O_Internal.Value = Ref('RecordSetInternal')

            add_obj(O_Internal)


class R53_RecordSetECSLoadBalancer(object):
    def __init__(self):
        # Resources
        if cfg.RecordSetExternal:
            R_External = R53RecordSetECSLoadBalancerApplicationExternal('RecordSetExternal')

            if cfg.LoadBalancerApplicationExternal:
                R_External.setup(scheme='External')
            else:
                R_External.setup(scheme='Internal')

            add_obj(R_External)
            
            # outputs
            O_External = Output('RecordSetExternal')
            O_External.Value = Ref('RecordSetExternal')

            add_obj(O_External)

        if cfg.RecordSetInternal:
            R_Internal = R53RecordSetECSLoadBalancerApplicationInternal('RecordSetInternal')

            if cfg.LoadBalancerApplicationInternal:
                R_Internal.setup(scheme='Internal')
            else:
                R_Internal.setup(scheme='External')

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
            R_External.setup()
            add_obj(R_External)

            # outputs
            O_External = Output('RecordSetExternal')
            O_External.Value = Ref('RecordSetExternal')

            add_obj(O_External)

        if cfg.RecordSetInternal:
            R_Internal = R53RecordSetRDSInternal('RecordSetInternal')
            R_Internal.setup()
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
            R_External.setup()
            add_obj(R_External)

            # outputs
            O_External = Output('RecordSetExternal')
            O_External.Value = Ref('RecordSetExternal')
            O_External.Condition = 'CacheEnabled'

            add_obj(O_External)

        if cfg.RecordSetInternal:
            R_Internal = R53RecordSetCCHInternal('RecordSetInternal')
            R_Internal.setup()
            add_obj(R_Internal)

            # outputs
            O_Internal = Output('RecordSetInternal')
            O_Internal.Value = Ref('RecordSetInternal')
            O_Internal.Condition = 'CacheEnabled'

            add_obj(O_Internal)


class R53_HostedZones(object):
    def __init__(self, key):
        for n, v in getattr(cfg, key).items():
            mapname = key + n
            resname = v['ResourceName']
            output_zonename = resname.replace('HostedZone', 'HostedZoneName')
            output_zoneidname = resname.replace('HostedZone', 'HostedZoneId')
            # parameters
            if n.startswith('Public'):
                p_HostedZone = Parameter(mapname + 'Enabled')
                p_HostedZone.Description = 'Create Public %s - can be created in only one Region - empty for default based on env/role' % resname

                p_HostedZoneId = Parameter(mapname + 'Id')
                p_HostedZoneId.Description = 'Id of Public %s - required in all Regions where HostedZonePublicEnv is not created - empty for default based on env/role' % resname

                add_obj([
                    p_HostedZone,
                    p_HostedZoneId,
                ])

                # conditions
                add_obj([
                    get_condition(resname, 'not_equals', 'None', mapname + 'Enabled')
                ])

            # resources
            r_HostedZone = r53.HostedZone(v['ResourceName'])
            auto_get_props(r_HostedZone, v, recurse=True, mapname=mapname)
            if n.startswith('Public'):
                r_HostedZone.Condition = resname

            add_obj(r_HostedZone)

            # outputs
            o_HostedZoneName = Output(output_zonename)
            #o_HostedZoneName.Value = Sub(cfg.HostedZoneNamePrivate)
            o_HostedZoneName.Value = get_endvalue(mapname + 'Name')
                
            o_HostedZoneId = Output(output_zoneidname)
            o_HostedZoneId.Value = If(resname, Ref(resname), get_endvalue(mapname + 'Id')) if n.startswith('Public') else Ref(resname)
            o_HostedZoneId.Export = Export(output_zoneidname)

            add_obj([
                o_HostedZoneName,
                o_HostedZoneId,
            ])
