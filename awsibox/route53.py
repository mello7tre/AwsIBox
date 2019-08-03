import troposphere.route53 as r53

from shared import *


# S - ROUTE53 #
class R53RecordSet(r53.RecordSetType):
    def setup(self):
        pass


class R53RecordSetZoneExternal(R53RecordSet):
    def setup(self):
        super(R53RecordSetZoneExternal, self).setup()
        self.HostedZoneId = get_exported_value('HostedZoneIdEnv')
        self.Name = Sub('${AWS::StackName}.${EnvRole}.' + get_final_value('HostedZoneNameRegionEnv'))  # Ex. prt-a-d.client-portal.eu-west-1.dev..


class R53RecordSetZoneInternal(R53RecordSet):
    def setup(self):
        super(R53RecordSetZoneInternal, self).setup()
        self.HostedZoneId = get_exported_value('HostedZoneIdPrivate')
        self.Name = Sub('${AWS::StackName}.${EnvRole}.' + get_final_value('HostedZoneNamePrivate'))  # Ex. prt-a-d.client-portal.internal..


class R53RecordSetCloudFront(R53RecordSetZoneExternal):
    def setup(self):
        super(R53RecordSetCloudFront, self).setup()
        self.Condition = 'RecordSetCloudFront'
        self.AliasTarget = r53.AliasTarget(
            DNSName=GetAtt('CloudFrontDistribution', 'DomainName'),
            HostedZoneId=get_final_value('HostedZoneIdCF')
        )
        self.Name = Sub('${EnvRole}${RecordSetCloudFrontSuffix}.cdn.' + get_final_value('HostedZoneNameEnv'))  # Ex. client-portal.cdn.dev..
        self.Type = 'A'


class R53RecordSetLoadBalancer(R53RecordSet):
    def setup(self):
        super(R53RecordSetLoadBalancer, self).setup()
        self.AliasTarget = r53.AliasTarget(
            HostedZoneId=get_final_value('HostedZoneIdLB')
        )
        self.Type = 'A'


class R53RecordSetEC2LoadBalancerExternal(R53RecordSetLoadBalancer, R53RecordSetZoneExternal):
    pass


class R53RecordSetEC2LoadBalancerInternal(R53RecordSetLoadBalancer, R53RecordSetZoneInternal):
    pass


class R53RecordSetECSLoadBalancer(R53RecordSetLoadBalancer):
    def setup(self, scheme):
        super(R53RecordSetECSLoadBalancer, self).setup()
        #scheme = RP_cmm['LoadBalancerApplication']
        self.AliasTarget.DNSName = get_sub_mapex(
            'dualstack.${1E}',
            'LoadBalancerApplication' + scheme + 'DNS',
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
        self.Name = Sub('efs-' + efsname + '.' + get_final_value('HostedZoneNamePrivate'))
        self.ResourceRecords = [
            Sub('${' + condname + '}.efs.${AWS::Region}.amazonaws.com')
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
        if RP_cmm['Engine'] == 'memcached':
            self.ResourceRecords = [GetAtt('CacheCluster', 'ConfigurationEndpoint.Address')]
        if RP_cmm['Engine'] == 'redis':
            self.ResourceRecords = [GetAtt('CacheCluster', 'RedisEndpoint.Address')]
        self.TTL = '300'


class R53RecordSetCCHExternal(R53RecordSetCCH, R53RecordSetZoneExternal):
    pass


class R53RecordSetCCHInternal(R53RecordSetCCH, R53RecordSetZoneInternal):
    pass


class R53RecordSetNSServiceDiscovery(R53RecordSet):
    def setup(self):
        self.HostedZoneId = Ref('HostedZoneEnv')
        self.Name = Sub('find.' + RP_cmm['HostedZoneNameEnv'])
        self.ResourceRecords = GetAtt('PublicDnsNamespace', 'NameServers')
        self.Type = 'NS'
        self.TTL = '300'


class R53HostedZonePrivate(r53.HostedZone):
    def setup(self):
        self.HostedZoneConfig = r53.HostedZoneConfiguration(
            Comment=Sub('${EnvShort} private zone ${AWS::Region}')
        )
        self.Name = Sub(get_final_value('HostedZoneNamePrivate'))
        self.VPCs = [
            r53.HostedZoneVPCs(
                VPCId=get_exported_value('VpcId'),
                VPCRegion=Ref('AWS::Region')
            )
        ]


class R53HostedZoneEnv(r53.HostedZone):
    def setup(self):
        self.Condition = self.title  # Ex. HostedZoneEnv
        self.HostedZoneConfig = r53.HostedZoneConfiguration(
            Comment=Sub('${EnvShort} public zone')
        )
        self.Name = Sub(get_final_value('HostedZoneNameEnv'))


class R53HostedZoneEnvExtra1(r53.HostedZone):
    def setup(self):
        self.Condition = self.title  # Ex. HostedZoneEnvExtra1
        self.HostedZoneConfig = r53.HostedZoneConfiguration(
            Comment=Sub('${EnvShort} attico public zone')
        )
        self.Name = Sub('${EnvShort}.attico.it')

# E - ROUTE53 #

# #################################
# ### START STACK INFRA CLASSES ###
# #################################

# S - ROUTE53 #
class R53_RecordSetCloudFront(object):
    def __init__(self):
        # Conditions
        C_RecordSet = {'RecordSetCloudFront': And(
            Condition('CloudFrontDistribution'),
            Not(
                Equals(get_final_value('RecordSetCloudFront'), 'None')
            )
        )}

        cfg.Conditions.extend([
            C_RecordSet,
        ])

        # Resources
        R_RecordSet = R53RecordSetCloudFront('RecordSetCloudFront')
        R_RecordSet.setup()

        cfg.Resources.extend([
            R_RecordSet,
        ])

        # Outputs
        O_CloudFront = Output('RecordSetCloudFront')
        O_CloudFront.Condition = 'RecordSetCloudFront'
        O_CloudFront.Value = Sub('${RecordSet} --> ${CloudFrontDistribution.DomainName}', **{'RecordSet': R_RecordSet.Name})

        cfg.Outputs.extend([
            O_CloudFront
        ])


class R53_RecordSetEC2LoadBalancer(object):
    def __init__(self):
        # Resources
        if 'External' in RP_cmm['RecordSet']:
            R_External = R53RecordSetEC2LoadBalancerExternal('RecordSetExternal')
            R_External.setup()
            if 'LoadBalancerClassic' in RP_cmm:
                if 'External' in RP_cmm['LoadBalancerClassic']:
                    R_External.AliasTarget.DNSName = Sub('dualstack.${LoadBalancerClassicExternal.DNSName}')
                elif 'Internal' in RP_cmm['LoadBalancerClassic']:
                    R_External.AliasTarget.DNSName = Sub('dualstack.${LoadBalancerClassicInternal.DNSName}')
            if 'LoadBalancerApplication' in RP_cmm:
                if 'External' in RP_cmm['LoadBalancerApplication']:
                    R_External.AliasTarget.DNSName = Sub('dualstack.${LoadBalancerApplicationExternal.DNSName}')
                elif 'Internal' in RP_cmm['LoadBalancerApplication']:
                    R_External.AliasTarget.DNSName = Sub('dualstack.${LoadBalancerApplicationInternal.DNSName}')

            cfg.Resources.append(R_External)

            # outputs
            O_External = Output('RecordSetExternal')
            O_External.Value = Ref('RecordSetExternal')

            cfg.Outputs.append(O_External)

        if 'Internal' in RP_cmm['RecordSet']:
            R_Internal = R53RecordSetEC2LoadBalancerInternal('RecordSetInternal')
            R_Internal.setup()
            if 'LoadBalancerClassic' in RP_cmm:
                if 'Internal' in RP_cmm['LoadBalancerClassic']:
                    R_Internal.AliasTarget.DNSName = Sub('dualstack.${LoadBalancerClassicInternal.DNSName}')
                elif 'External' in RP_cmm['LoadBalancerClassic']:
                    R_Internal.AliasTarget.DNSName = Sub('dualstack.${LoadBalancerClassicExternal.DNSName}')
            if 'LoadBalancerApplication' in RP_cmm:
                if 'Internal' in RP_cmm['LoadBalancerApplication']:
                    R_Internal.AliasTarget.DNSName = Sub('dualstack.${LoadBalancerApplicationInternal.DNSName}')
                elif 'External' in RP_cmm['LoadBalancerApplication']:
                    R_Internal.AliasTarget.DNSName = Sub('dualstack.${LoadBalancerApplicationExternal.DNSName}')

            cfg.Resources.append(R_Internal)

            # outputs
            O_Internal = Output('RecordSetInternal')
            O_Internal.Value = Ref('RecordSetInternal')

            cfg.Outputs.append(O_Internal)
# E - ROUTE53 #


class R53_RecordSetECSLoadBalancer(object):
    def __init__(self):
        # Resources
        if 'External' in RP_cmm['RecordSet']:
            R_External = R53RecordSetECSLoadBalancerApplicationExternal('RecordSetExternal')

            if 'External' in RP_cmm['LoadBalancerApplication']:
                R_External.setup(scheme='External')
            else:
                R_External.setup(scheme='Internal')

            cfg.Resources.append(R_External)
            
            # outputs
            O_External = Output('RecordSetExternal')
            O_External.Value = Ref('RecordSetExternal')

            cfg.Outputs.append(O_External)

        if 'Internal' in RP_cmm['RecordSet']:
            R_Internal = R53RecordSetECSLoadBalancerApplicationInternal('RecordSetInternal')

            if 'Internal' in RP_cmm['LoadBalancerApplication']:
                R_Internal.setup(scheme='Internal')
            else:
                R_Internal.setup(scheme='External')

            cfg.Resources.append(R_Internal)

            # outputs
            O_Internal = Output('RecordSetInternal')
            O_Internal.Value = Ref('RecordSetInternal')

            cfg.Outputs.append(O_Internal)


class R53_RecordSetRDS(object):
    def __init__(self):
        # Resources
        if 'External' in RP_cmm['RecordSet']:
            R_External = R53RecordSetRDSExternal('RecordSetExternal')
            R_External.setup()
            cfg.Resources.append(R_External)

            # outputs
            O_External = Output('RecordSetExternal')
            O_External.Value = Ref('RecordSetExternal')

            cfg.Outputs.append(O_External)

        if 'Internal' in RP_cmm['RecordSet']:
            R_Internal = R53RecordSetRDSInternal('RecordSetInternal')
            R_Internal.setup()
            cfg.Resources.append(R_Internal)

            # outputs
            O_Internal = Output('RecordSetInternal')
            O_Internal.Value = Ref('RecordSetInternal')

            cfg.Outputs.append(O_Internal)


class R53_RecordSetCCH(object):
    def __init__(self):
        # Resources
        if 'External' in RP_cmm['RecordSet']:
            R_External = R53RecordSetCCHExternal('RecordSetExternal')
            R_External.setup()
            cfg.Resources.append(R_External)

            # outputs
            O_External = Output('RecordSetExternal')
            O_External.Value = Ref('RecordSetExternal')
            O_External.Condition = 'CacheEnabled'

            cfg.Outputs.append(O_External)

        if 'Internal' in RP_cmm['RecordSet']:
            R_Internal = R53RecordSetCCHInternal('RecordSetInternal')
            R_Internal.setup()
            cfg.Resources.append(R_Internal)

            # outputs
            O_Internal = Output('RecordSetInternal')
            O_Internal.Value = Ref('RecordSetInternal')
            O_Internal.Condition = 'CacheEnabled'

            cfg.Outputs.append(O_Internal)


class R53_HostedZones(object):
    def __init__(self, key):
        # Conditions
        do_no_override(True)
        C_Env = {'HostedZoneEnv': Not(
            Equals(get_final_value('HostedZoneEnv'), 'None')
        )}

        
        C_EnvExtra1 = {'HostedZoneEnvExtra1': Not(
            Equals(get_final_value('HostedZoneEnvExtra1'), 'None')
        )}
        do_no_override(False)

        cfg.Conditions.extend([
            C_Env,
            C_EnvExtra1,
        ])

        # Resources
        R_Private = R53HostedZonePrivate('HostedZonePrivate')
        R_Private.setup()

        R_Env = R53HostedZoneEnv('HostedZoneEnv')
        R_Env.setup()

        R_EnvExtra1 = R53HostedZoneEnvExtra1('HostedZoneEnvExtra1')
        R_EnvExtra1.setup()

        cfg.Resources.extend([
            R_Private,
            R_Env,
            R_EnvExtra1,
        ])

        # Outputs
        O_Private = Output('HostedZoneIdPrivate')
        O_Private.Value = Ref('HostedZonePrivate')
        O_Private.Export = Export('HostedZoneIdPrivate')

        O_PrivateName = Output('HostedZoneNamePrivate')
        O_PrivateName.Value =  Sub(get_final_value('HostedZoneNamePrivate'))

        O_Env = Output('HostedZoneIdEnv')
        O_Env.Value = If(
            'HostedZoneEnv',
            Ref('HostedZoneEnv'),
            get_final_value('HostedZoneIdEnv')
        )
        O_Env.Export = Export('HostedZoneIdEnv')

        O_EnvName = Output('HostedZoneNameEnv')
        O_EnvName.Value = Sub(get_final_value('HostedZoneNameEnv'))

        O_EnvNameRegion = Output('HostedZoneNameRegionEnv')
        O_EnvNameRegion.Value = Sub(get_final_value('HostedZoneNameRegionEnv'))

        cfg.Outputs.extend([
            O_Private,
            O_PrivateName,
            O_Env,
            O_EnvName,
            O_EnvNameRegion,
        ])

# Need to stay as last lines
import_modules(globals())
