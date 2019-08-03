import troposphere.ec2 as ec2

from shared import *


# S - SECURITY GROUP #
class SecurityGroup(ec2.SecurityGroup):
    def setup(self):
        self.VpcId = get_exported_value('VpcId')


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
        self.FromPort = get_final_value(listener + 'LoadBalancerPort')
        self.ToPort = get_final_value(listener + 'LoadBalancerPort')
        self.SourceSecurityGroupId = Ref('SecurityGroupLoadBalancer')
        self.GroupId = GetAtt('SecurityGroupInstancesRules', 'GroupId')


class SecurityGroupsIngressEcs(SecurityGroupIngress):
    def setup(self, proto, scheme):
        self.Condition = self.title
        self.GroupId = get_exported_value('SecurityGroupLoadBalancerApplication' + scheme)
        self.FromPort = get_final_value('ListenerLoadBalancer' + proto + 'Port')
        self.ToPort = self.FromPort

# E - SECURITY GROUP #


# ############################################
# ### START STACK META CLASSES AND METHODS ###
# ############################################

# S - SECURITY GROUP #
class SecurityGroupRule(ec2.SecurityGroupRule):
    IpProtocol = 'tcp'


class SecurityGroupRuleELBPorts(SecurityGroupRule):
    def setup(self):
        name = self.title  # Ex. Listeners1
        self.FromPort = get_final_value(name + 'LoadBalancerPort')
        self.ToPort = get_final_value(name + 'LoadBalancerPort')


class SecurityGroupRuleNamePorts(SecurityGroupRule):
    def setup(self):
        name = self.title  # Ex. 3306
        self.FromPort = name
        self.ToPort = name


class SecurityGroupRuleEcsService(SecurityGroupRule):
    def setup(self, scheme):
        self.SourceSecurityGroupId = get_exported_value('SecurityGroupLoadBalancerApplication' + scheme)
        self.FromPort = get_final_value('ContainerDefinitions1ContainerPort')
        self.ToPort = self.FromPort

# E - SECURITY GROUP #

# ##########################################
# ### END STACK META CLASSES AND METHODS ###
# ##########################################

class SG_SecurityGroupsExtra(object):
    def __init__(self, Out_String, Out_Map):
        # Parameters
        P_SecurityGroups = Parameter('SecurityGroups')
        P_SecurityGroups.Description = 'SecurityGroups List Extra - ' + SECURITY_GROUPS_DEFAULT + ' for default based on env/role'
        P_SecurityGroups.AllowedPattern = '^(\w*,\w*){' + str(MAX_SECURITY_GROUPS - 1) + '}$'
        P_SecurityGroups.Default = SECURITY_GROUPS_DEFAULT

        cfg.Parameters.extend([
            P_SecurityGroups,
        ])

        # Conditions
        do_no_override(True)
        C_Override = {'SecurityGroupsOverride': Not(
            Equals(Select('0', Split(',', Ref('SecurityGroups'))), '')
        )}

        cfg.Conditions.extend([
            C_Override,
        ])
        do_no_override(False)

        SecurityGroups = []

        for n in range(MAX_SECURITY_GROUPS):
            name = 'SecurityGroup' + str(n)  # Ex SecurityGroup1
            value = Select(n, Split(',', get_final_value('SecurityGroups')))  # Ex. ElasticSearch
            outnamename = 'SecurityGroupName' + str(n)  # Ex. SecurityGroupName1
            outvaluename = 'SecurityGroupValue' + str(n)  # Ex. SecurityGroupValue1

            # conditions
            do_no_override(True)
            c_OverrideCondition = {name: Not(
                Or(
                    And(
                        Condition('SecurityGroupsOverride'),
                        Equals(Select(n, Split(',', Ref('SecurityGroups'))), 'None')
                    ),
                    And(
                        Not(Condition('SecurityGroupsOverride')),
                        Equals(Select(n, Split(',', get_final_value('SecurityGroups'))), 'None')
                    )
                )
            )}
            cfg.Conditions.append(c_OverrideCondition)
            do_no_override(False)

            SecurityGroups.append(If(
                name,
                get_exported_value(value, prefix='SecurityGroup'),
                Ref('AWS::NoValue')
            ))

            # outputs
            Out_String.append('${' + outnamename + '}=${' + outvaluename + '}')
            Out_Map.update({
                outnamename: value,
                outvaluename: If(
                    name,
                    get_exported_value(value, prefix='SecurityGroup'),
                    'None'
                )
            })

        # Outputs
        O_SecurityGroups = Output('SecurityGroups')
        O_SecurityGroups.Value = Sub(','.join(Out_String), **Out_Map)

        cfg.Outputs.extend([
            O_SecurityGroups,
        ])

        self.O_SecurityGroups = O_SecurityGroups

        self.SecurityGroups = SecurityGroups


class SG_SecurityGroupIngressesExtra(object):
    def __init__(self, key):
        for n, v in RP_cmm[key].iteritems():
            resname = key + n
            r_SGI = SecurityGroupIngress(resname)
            auto_get_props(r_SGI, v)

            cfg.Resources.append(r_SGI)


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

        cfg.Resources.extend([
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


class SG_SecurityGroupRES(object):
    def __init__(self, key):
        for n, v in RP_cmm['SecurityGroupBase'].iteritems():
            name = 'SecurityGroup%s' % n  # Ex. SecurityGroupElasticSearchClient
            outname = name if n != 'ElasticSearchClient' else 'SecurityGroup' + n.replace('Client', '')  # Ex. SecurityGroupElasticSearch
            # resources
            r_Base = SecurityGroup(name)
            r_Base.setup()
            r_Base.GroupDescription = get_final_value('SecurityGroupBase' + n)

            cfg.Resources.append(r_Base)

            # outputs
            o_Base = Output(outname)
            o_Base.Value = GetAtt(name, 'GroupId')
            o_Base.Export = Export(outname)

            cfg.Outputs.append(o_Base)

        Securitygroup_Rules = []
        for n, v in RP_cmm['AllowedIp'].iteritems():
            name = 'AllowedIp%s' % n
            # conditions
            do_no_override(True)
            cfg.Conditions.append({
                name: Not(Equals(get_final_value(name + 'Enabled'), 'None'))
            })
            do_no_override(False)

            # resources
            Rule = SecurityGroupRule()
            Rule.FromPort = '22'
            Rule.ToPort = '22'
            Rule.CidrIp=get_final_value(name + 'Ip')
            
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

        # Resources
        R_BaseInstance = SecurityGroup('SecurityGroupBaseInstance')
        R_BaseInstance.setup()
        R_BaseInstance.GroupDescription = 'Enable ICMP Ping [ALL] and SSH [192.168.36.0/23]'
        # R_BaseInstance.GroupDescription='Enable ICMP Ping [ALL] and SSH [' + ','.join(securitygroups_description['resources-env']) + ']'
        R_BaseInstance.SecurityGroupIngress = Securitygroup_Rules

        cfg.Resources.extend([
            R_BaseInstance,
        ])

        # Outputs
        O_BaseInstance = Output('SecurityGroupBaseInstance')
        O_BaseInstance.Value = GetAtt('SecurityGroupBaseInstance', 'GroupId')
        O_BaseInstance.Export = Export('SecurityGroupBaseInstance')

        cfg.Outputs.extend([
            O_BaseInstance,
        ])


class SG_SecurityGroupIngressesExtraService(object):
    def __init__(self, key, service):  # Ex service=RDS
        Securitygroup_Rules = []
        for n, v in RP_cmm[key].iteritems():
            name = str(v['FromPort'])  # Ex 3306
            for i in RP_cmm['AllowedIp']:
                ipname = 'AllowedIp' + str(i)  # Ex. AllowedIp1
                condnameprivate = 'SecurityGroupRulePrivatePort' + name + ipname  # Ex. SecurityGroupRulePrivatePorts3306AllowedIp1

                # conditions
                do_no_override(True)
                c_AllowedIp = {ipname: Not(
                    Equals(get_final_value(ipname + 'Enabled'), 'None')
                )}

                c_SGRulePrivate = {condnameprivate: And(
                    Condition(ipname),
                    Equals(get_final_value(service + 'Access'), 'Private')
                )}

                cfg.Conditions.extend([
                    c_AllowedIp,
                    c_SGRulePrivate,
                ])
                do_no_override(False)

                SGRule = SecurityGroupRuleNamePorts(name)
                SGRule.setup()
                SGRule.CidrIp = get_final_value(ipname + 'Ip')

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

        cfg.Resources.extend([
            R_SG,
        ])

        # Outputs
        O_SG = Output('SecurityGroup')
        O_SG.Value = GetAtt('SecurityGroup' + service, 'GroupId')

        cfg.Outputs.extend([
            O_SG,
        ])

class SG_SecurityGroupIngressesExtraRDS(SG_SecurityGroupIngressesExtraService):
    def __init__(self, **kwargs):
        super(SG_SecurityGroupIngressesExtraRDS, self).__init__(service='RDS', **kwargs)


class SG_SecurityGroupIngressesExtraCCH(SG_SecurityGroupIngressesExtraService):
    def __init__(self, **kwargs):
        super(SG_SecurityGroupIngressesExtraCCH, self).__init__(service='CCH', **kwargs)


# Need to stay as last lines
import_modules(globals())
