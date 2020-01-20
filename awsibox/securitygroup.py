import troposphere.ec2 as ec2

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
    get_subvalue, auto_get_props, get_condition, add_obj)


# S - SECURITY GROUP #
class SecurityGroup(ec2.SecurityGroup):
    def setup(self):
        self.VpcId = get_expvalue('VpcId')


class SecurityGroupInstanceRules(SecurityGroup):
    def setup(self):
        super(SecurityGroupInstanceRules, self).setup()
        self.GroupDescription = 'Enable Access from LoadBalancer to Instances and between Instances'


class SecurityGroupLoadBalancer(SecurityGroup):
    def setup(self):
        super(SecurityGroupLoadBalancer, self).setup()
        self.GroupDescription = 'Enable access to LoadBalancer'


class SecurityGroupEcsService(SecurityGroup):
    def setup(self):
        super(SecurityGroupEcsService, self).setup()
        self.Condition = 'NetworkModeAwsVpc'
        self.GroupDescription = 'Enable access to Service'
        self.SecurityGroupIngress = []


class SecurityGroupIngress(ec2.SecurityGroupIngress):
    IpProtocol = 'tcp'


class SecurityGroupIngressInstanceELBPorts(SecurityGroupIngress):
    def setup(self, listener):
        name = self.title  # Ex. SecurityGroupIngressListeners1
        self.FromPort = get_endvalue(listener + 'LoadBalancerPort')
        self.ToPort = get_endvalue(listener + 'LoadBalancerPort')
        self.SourceSecurityGroupId = Ref('SecurityGroupLoadBalancer')
        self.GroupId = GetAtt('SecurityGroupInstancesRules', 'GroupId')


class SecurityGroupsIngressEcs(SecurityGroupIngress):
    def setup(self, proto, scheme):
        self.Condition = self.title
        self.GroupId = get_expvalue('SecurityGroupLoadBalancerApplication' + scheme)
        self.FromPort = get_endvalue('ListenerLoadBalancer' + proto + 'Port')
        self.ToPort = self.FromPort

# E - SECURITY GROUP #


# ############################################
# ### START STACK META CLASSES AND METHODS ###
# ############################################

class SecurityGroupRule(ec2.SecurityGroupRule):
    IpProtocol = 'tcp'


class SecurityGroupRuleELBPorts(SecurityGroupRule):
    def setup(self):
        name = self.title  # Ex. Listeners1
        self.FromPort = get_endvalue(name + 'LoadBalancerPort')
        self.ToPort = get_endvalue(name + 'LoadBalancerPort')


class SecurityGroupRuleNamePorts(SecurityGroupRule):
    def setup(self):
        name = self.title  # Ex. 3306
        self.FromPort = name
        self.ToPort = name


class SecurityGroupRuleEcsService(SecurityGroupRule):
    def setup(self, scheme):
        self.SourceSecurityGroupId = get_expvalue('SecurityGroupLoadBalancerApplication' + scheme)
        self.FromPort = get_endvalue('ContainerDefinitions1ContainerPort')
        self.ToPort = self.FromPort


# ##########################################
# ### END STACK META CLASSES AND METHODS ###
# ##########################################

class SG_SecurityGroupsExtra(object):
    def __init__(self, Out_String, Out_Map):
        # if key SecurityGroups not present, set and empty SecurityGroups list and output (not added)
        try: cfg.SecurityGroups
        except:
            self.SecurityGroups = []
            self.O_SecurityGroups = Output('') 
            return

        # Parameters
        P_SecurityGroups = Parameter('SecurityGroups')
        P_SecurityGroups.Description = 'SecurityGroups List Extra - %s for default based on env/role' % SECURITY_GROUPS_DEFAULT
        P_SecurityGroups.AllowedPattern = '^(\w*,\w*){%s}$' % (MAX_SECURITY_GROUPS - 1)
        P_SecurityGroups.Default = SECURITY_GROUPS_DEFAULT

        add_obj([
            P_SecurityGroups,
        ])

        SecurityGroups = []

        for n in range(MAX_SECURITY_GROUPS):
            name = 'SecurityGroup%s' % n  # Ex SecurityGroup1
            value = Select(n, Split(',', get_endvalue('SecurityGroups')))  # Ex. ElasticSearch
            outnamename = 'SecurityGroupName%s' % n  # Ex. SecurityGroupName1
            outvaluename = 'SecurityGroupValue%s' % n  # Ex. SecurityGroupValue1

            # conditions
            add_obj(
                {name: Not(
                    get_condition('', 'equals', 'None',
                        Select(n, Split(',', 'SecurityGroups'))
                    )
                )}
            )

            SecurityGroups.append(If(
                name,
                get_expvalue(value, prefix='SecurityGroup'),
                Ref('AWS::NoValue')
            ))

            # outputs
            Out_String.append('${%s}=${%s}' % (outnamename, outvaluename))
            Out_Map.update({
                outnamename: value,
                outvaluename: If(
                    name,
                    get_expvalue(value, prefix='SecurityGroup'),
                    'None'
                )
            })

        # Outputs
        O_SecurityGroups = Output('SecurityGroups')
        O_SecurityGroups.Value = Sub(','.join(Out_String), **Out_Map)

        add_obj([
            O_SecurityGroups,
        ])

        self.O_SecurityGroups = O_SecurityGroups

        self.SecurityGroups = SecurityGroups


class SG_SecurityGroupIngressesExtra(object):
    def __init__(self, key):
        for n, v in getattr(cfg, key).items():
            resname = key + n
            r_SGI = SecurityGroupIngress(resname)
            auto_get_props(r_SGI, v)

            add_obj(r_SGI)


class SG_SecurityGroupsEC2(object):
    def __init__(self):
        Out_String = ['Rules=${SecurityGroupInstancesRules}']
        Out_Map = {
            'SecurityGroupInstancesRules': {
                'Ref': 'SecurityGroupInstancesRules'
            },
        }


        # Resources
        SG_Extra = SG_SecurityGroupsExtra(Out_String, Out_Map)

        R_SGInstance = SecurityGroupInstanceRules('SecurityGroupInstancesRules')
        R_SGInstance.setup()

        add_obj([
            R_SGInstance,
        ])

        self.SecurityGroups = SG_Extra.SecurityGroups


class SG_SecurityGroupsECS(object):
    def __init__(self):
        Out_String = ['Service=${SecurityGroupEcsService}']
        Out_Map = {
            'SecurityGroupEcsService': {
                'Ref': 'SecurityGroupEcsService'
            },
        }

        # Resources
        SG_Extra = SG_SecurityGroupsExtra(Out_String, Out_Map)

        SG_Extra.O_SecurityGroups.Condition = 'NetworkModeAwsVpc'

        self.SecurityGroups = SG_Extra.SecurityGroups


class SG_SecurityGroupsTSK(object):
    def __init__(self):
        Out_String = []
        Out_Map = {}

        # Resources
        SG_Extra = SG_SecurityGroupsExtra(Out_String, Out_Map)

        SG_Extra.O_SecurityGroups.Condition = 'NetworkModeAwsVpc'

        self.SecurityGroups = SG_Extra.SecurityGroups


def SG_SecurityGroupIngressBaseInstance():
    Securitygroup_Rules = []

    for n, v in cfg.AllowedIp.items():
        name = 'AllowedIp%s' % n
        # conditions
        add_obj(get_condition(name, 'not_equals', 'None', name + 'Enabled'))

        # resources
        Rule = SecurityGroupRule()
        Rule.FromPort = '22'
        Rule.ToPort = '22'
        Rule.CidrIp=get_endvalue(name + 'Ip')

        Securitygroup_Rules.append(
            If(
                name,
                Rule,
                Ref('AWS::NoValue')
            )
        )

    Securitygroup_Rules.append(
        ec2.SecurityGroupRule(
            CidrIp='0.0.0.0/0',
            FromPort='8',
            IpProtocol='icmp',
            ToPort='-1'
        )
    )

    return Securitygroup_Rules


class SG_SecurityGroupRES(object):
    def __init__(self, key):
        for n, v in getattr(cfg, key).items():
            name = 'SecurityGroup%s' % n  # Ex. SecurityGroupElasticSearchClient
            outname = name if n != 'ElasticSearchClient' else 'SecurityGroup' + n.replace('Client', '')  # Ex. SecurityGroupElasticSearch

            # resources
            r_Base = SecurityGroup(name)
            r_Base.setup()
            r_Base.GroupDescription = get_endvalue('SecurityGroupBase' + n)

            if n == 'BaseInstance':
                r_Base.SecurityGroupIngress = SG_SecurityGroupIngressBaseInstance()

            add_obj(r_Base)

            # outputs
            o_Base = Output(outname)
            o_Base.Value = GetAtt(name, 'GroupId')
            o_Base.Export = Export(outname)

            add_obj(o_Base)


class SG_SecurityGroupIngressesExtraService(object):
    def __init__(self, key, service):  # Ex service=RDS
        Securitygroup_Rules = []
        for n, v in getattr(cfg, key).items():
            name = str(v['FromPort'])  # Ex 3306
            for i in cfg.AllowedIp:
                ipname = 'AllowedIp%s' % i  # Ex. AllowedIp1
                condnameprivate = 'SecurityGroupRulePrivatePort' + name + ipname  # Ex. SecurityGroupRulePrivatePorts3306AllowedIp1

                # conditions
                add_obj([
                    get_condition(ipname, 'not_equals', 'None', ipname + 'Enabled'),
                    {condnameprivate: And(
                        Condition(ipname),
                        get_condition('', 'equals', 'Private', service + 'Access')
                    )},
                ])

                SGRule = SecurityGroupRuleNamePorts(name)
                SGRule.setup()
                SGRule.CidrIp = get_endvalue(ipname + 'Ip')

                Securitygroup_Rules.append(
                    If( 
                        condnameprivate,
                        SGRule,
                        Ref('AWS::NoValue'),
                    )
                )

            SGRule = SecurityGroupRuleNamePorts(name)
            SGRule.setup()
            SGRule.CidrIp = '0.0.0.0/0'

            Securitygroup_Rules.append(
                If(
                    service + 'Public',
                    SGRule,
                    Ref('AWS::NoValue'),
                )
            )

        # Resources
        SG_SecurityGroupIngressesExtra(key=key)

        R_SG = SecurityGroup('SecurityGroup' + service)
        R_SG.setup()
        R_SG.GroupDescription = 'Enable access to ' + service
        R_SG.SecurityGroupIngress = Securitygroup_Rules

        add_obj([
            R_SG,
        ])

        # Outputs
        O_SG = Output('SecurityGroup')
        O_SG.Value = GetAtt('SecurityGroup' + service, 'GroupId')

        add_obj([
            O_SG,
        ])

class SG_SecurityGroupIngressesExtraRDS(SG_SecurityGroupIngressesExtraService):
    def __init__(self, **kwargs):
        super(SG_SecurityGroupIngressesExtraRDS, self).__init__(service='RDS', **kwargs)


class SG_SecurityGroupIngressesExtraCCH(SG_SecurityGroupIngressesExtraService):
    def __init__(self, **kwargs):
        super(SG_SecurityGroupIngressesExtraCCH, self).__init__(service='CCH', **kwargs)
