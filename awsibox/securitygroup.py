import troposphere.ec2 as ec2

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
                     get_subvalue, auto_get_props, get_condition, add_obj)


class SecurityGroup(ec2.SecurityGroup):
    # troposphere ec2 is quite old and SecurityGroupIngress is only a list
    # without the obj type, this break auto_get_props, fix it overriding
    props = {
        'GroupName': (str, False),
        'GroupDescription': (str, True),
        'SecurityGroupEgress': (list, False),
        'SecurityGroupIngress': ([ec2.SecurityGroupRule], False),
        'VpcId': (str, False),
        'Tags': ((Tags, list), False),
    }

    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.VpcId = get_expvalue('VpcId')


class SecurityGroupLoadBalancer(SecurityGroup):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.GroupDescription = 'Enable access to LoadBalancer'


class SecurityGroupEcsService(SecurityGroup):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.Condition = 'NetworkModeAwsVpc'
        self.GroupDescription = 'Enable access to Service'
        self.SecurityGroupIngress = []


class SecurityGroupIngress(ec2.SecurityGroupIngress):
    IpProtocol = 'tcp'


class SecurityGroupIngressInstanceELBPorts(SecurityGroupIngress):
    def __init__(self, title, listener, **kwargs):
        super().__init__(title, **kwargs)
        name = self.title  # Ex. SecurityGroupIngressListeners1
        self.FromPort = get_endvalue(f'{listener}LoadBalancerPort')
        self.ToPort = get_endvalue(f'{listener}LoadBalancerPort')
        self.SourceSecurityGroupId = Ref('SecurityGroupLoadBalancer')
        self.GroupId = GetAtt('SecurityGroupInstancesRules', 'GroupId')


class SecurityGroupsIngressEcs(SecurityGroupIngress):
    def __init__(self, title, proto, scheme, **kwargs):
        super().__init__(title, **kwargs)
        self.Condition = self.title
        self.GroupId = get_expvalue(
            f'SecurityGroupLoadBalancerApplication{scheme}',
            'LoadBalancerApplicationStack')
        self.FromPort = get_endvalue(
            f'ListenerLoadBalancer{proto}Port')
        self.ToPort = self.FromPort


class SecurityGroupRule(ec2.SecurityGroupRule):
    IpProtocol = 'tcp'


class SecurityGroupRuleELBPorts(SecurityGroupRule):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        name = self.title  # Ex. Listeners1
        self.FromPort = get_endvalue(f'{name}LoadBalancerPort')
        self.ToPort = get_endvalue(f'{name}LoadBalancerPort')


class SecurityGroupRuleNamePorts(SecurityGroupRule):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        name = self.title  # Ex. 3306
        self.FromPort = name
        self.ToPort = name


class SecurityGroupRuleEcsService(SecurityGroupRule):
    def __init__(self, scheme, **kwargs):
        super().__init__(**kwargs)
        self.SourceSecurityGroupId = get_expvalue(
            f'SecurityGroupLoadBalancerApplication{scheme}')
        self.FromPort = get_endvalue('ContainerDefinitions1ContainerPort')
        self.ToPort = self.FromPort


def SG_SecurityGroupsExtra(Out_String, Out_Map):
    # if key SecurityGroups not present,
    # set and empty SecurityGroups list and output (not added)
    try:
        cfg.SecurityGroups
    except Exception:
        return []

    # Parameters
    P_SecurityGroups = Parameter('SecurityGroups')
    P_SecurityGroups.Description = (
        'SecurityGroups List Extra - '
        f'{SECURITY_GROUPS_DEFAULT} for default based on env/role')
    P_SecurityGroups.AllowedPattern = (
        r'^(\w*,\w*){%s}$' % (MAX_SECURITY_GROUPS - 1))
    P_SecurityGroups.Default = SECURITY_GROUPS_DEFAULT

    add_obj([
        P_SecurityGroups])

    SecurityGroups = []

    for n in range(MAX_SECURITY_GROUPS):
        name = f'SecurityGroup{n}'  # Ex SecurityGroup1
        value = Select(
            n, Split(',', get_endvalue('SecurityGroups')))
        outnamename = f'SecurityGroupName{n}'
        outvaluename = f'SecurityGroupValue{n}'

        # conditions
        add_obj({name: Not(get_condition(
            '', 'equals', 'None', Select(n, Split(',', 'SecurityGroups'))))})

        SecurityGroups.append(If(
            name,
            get_expvalue(value, prefix='SecurityGroup'),
            Ref('AWS::NoValue')))

        # outputs
        Out_String.append('${%s}=${%s}' % (outnamename, outvaluename))
        Out_Map.update({
            outnamename: value,
            outvaluename: If(
                name,
                get_expvalue(value, prefix='SecurityGroup'),
                'None')})

    # Outputs
    O_SecurityGroups = Output('SecurityGroups')
    O_SecurityGroups.Value = Sub(','.join(Out_String), **Out_Map)

    add_obj([
        O_SecurityGroups])

    return SecurityGroups


def SG_SecurityGroupIngressesExtra(key):
    for n, v in getattr(cfg, key).items():
        resname = f'{key}{n}'
        r_SGI = SecurityGroupIngress(resname)
        auto_get_props(r_SGI)

        add_obj(r_SGI)


def SG_SecurityGroupsEC2():
    Out_String = ['Rules=${SecurityGroupInstancesRules}']
    Out_Map = {
        'SecurityGroupInstancesRules': {
            'Ref': 'SecurityGroupInstancesRules'}}

    # Resources
    R_SGInstance = SecurityGroup(
        'SecurityGroupInstancesRules')
    R_SGInstance.GroupDescription = (
        'Enable Access from LoadBalancer to Instances '
        'and between Instances')

    add_obj([
        R_SGInstance])

    return SG_SecurityGroupsExtra(Out_String, Out_Map)


def SG_SecurityGroupsECS():
    Out_String = ['Service=${SecurityGroupEcsService}']
    Out_Map = {
        'SecurityGroupEcsService': {
            'Ref': 'SecurityGroupEcsService'}}

    SecurityGroups = SG_SecurityGroupsExtra(Out_String, Out_Map)
    # add Condition to Output created by SG_SecurityGroupsExtra
    try:
        cfg.Outputs['SecurityGroups'].Condition = 'NetworkModeAwsVpc'
    except Exception:
        pass

    return SecurityGroups


def SG_SecurityGroupsTSK():
    Out_String = []
    Out_Map = {}

    SecurityGroups = SG_SecurityGroupsExtra(Out_String, Out_Map)
    # add Condition to Output created by SG_SecurityGroupsExtra
    try:
        cfg.Outputs['SecurityGroups'].Condition = 'NetworkModeAwsVpc'
    except Exception:
        pass

    return SecurityGroups


def SG_SecurityGroupRulesBaseInstance():
    Securitygroup_Rules = []

    for n, v in cfg.AllowedIp.items():
        name = f'AllowedIp{n}'
        # conditions
        add_obj(get_condition(name, 'not_equals', 'None', f'{name}Enabled'))

        # resources
        Rule = SecurityGroupRule()
        Rule.FromPort = '22'
        Rule.ToPort = '22'
        Rule.CidrIp = get_endvalue(f'{name}Ip')

        Securitygroup_Rules.append(
            If(
                name,
                Rule,
                Ref('AWS::NoValue')))

    Securitygroup_Rules.append(
        ec2.SecurityGroupRule(
            CidrIp='0.0.0.0/0',
            FromPort='8',
            IpProtocol='icmp',
            ToPort='-1'))

    return Securitygroup_Rules


def SG_SecurityGroupRulesService(port, name):
    Securitygroup_Rules = []

    for i in cfg.AllowedIp:
        ipname = f'AllowedIp{i}'
        condnameprivate = (
            f'SecurityGroupRulePrivatePort{port}{ipname}')

        # conditions
        c_Enabled = get_condition(
            ipname, 'not_equals', 'None', f'{ipname}Enabled')

        c_Access = {condnameprivate: And(
            Condition(ipname),
            get_condition('', 'equals', 'Private', f'{name}Access')
        )}

        add_obj([
            c_Enabled,
            c_Access])

        SGRule = SecurityGroupRuleNamePorts(port)
        SGRule.CidrIp = get_endvalue(f'{ipname}Ip')

        Securitygroup_Rules.append(
            If(
                condnameprivate,
                SGRule,
                Ref('AWS::NoValue')))

    SGRule = SecurityGroupRuleNamePorts(port)
    SGRule.CidrIp = '0.0.0.0/0'

    Securitygroup_Rules.append(
        If(
            f'{name}Public',
            SGRule,
            Ref('AWS::NoValue')))

    return Securitygroup_Rules


def SG_SecurityGroupRES(key):
    for n, v in getattr(cfg, key).items():
        name = f'SecurityGroup{n}'
        # bad fix
        if n != 'ElasticSearchClient':
            outname = name
        else:
            outname = 'SecurityGroup%s' % n.replace('Client', '')

        # resources
        r_Base = SecurityGroup(name)
        r_Base.GroupDescription = get_endvalue(f'SecurityGroupBase{n}')

        if n == 'BaseInstance':
            r_Base.SecurityGroupIngress = SG_SecurityGroupRulesBaseInstance()

        # outputs
        o_Base = Output(outname)
        o_Base.Value = GetAtt(name, 'GroupId')
        o_Base.Export = Export(outname)

        add_obj([
            r_Base,
            o_Base])


def SG_SecurityGroupService(name):
    Securitygroup_Rules = []
    for n, v in getattr(cfg, 'SecurityGroupIngress').items():
        port = str(v['FromPort'])
        Securitygroup_Rules.extend(SG_SecurityGroupRulesService(port, name))

    R_SG = SecurityGroup(f'SecurityGroup{name}')
    R_SG.GroupDescription = f'Enable access to {name}'
    R_SG.SecurityGroupIngress = Securitygroup_Rules

    # Outputs
    O_SG = Output('SecurityGroup')
    O_SG.Value = GetAtt(f'SecurityGroup{name}', 'GroupId')

    add_obj([
        R_SG,
        O_SG])


def SG_SecurityGroupIngressesECS(scheme, proto):
    resname_public = (
        'SecurityGroupIngressLoadBalancerApplicationPublic'
        f'{proto}{scheme}')

    # Conditions
    c_Public = {
        resname_public: And(
            Condition(f'ListenerLoadBalancer{proto}Port'),
            Condition('LoadBalancerPublic'),
        )
    }

    add_obj(c_Public)

    # Resources
    R_SGIPublic = SecurityGroupsIngressEcs(
        resname_public, proto=proto, scheme=scheme)
    R_SGIPublic.CidrIp = '0.0.0.0/0'

    add_obj(R_SGIPublic)

    for i in cfg.AllowedIp:
        ipname = f'AllowedIp{i}'  # Ex. AllowedIp1
        resname_private = (
            f'SecurityGroupIngressLoadBalancerApplicationPrivate{proto}'
            f'{scheme}{ipname}')

        # conditions
        c_AllowedIpPrivate = {resname_private: And(
            Condition(ipname),
            Not(Condition('LoadBalancerPublic')),
            Condition(f'ListenerLoadBalancer{proto}Port')
        )}

        add_obj(c_AllowedIpPrivate)

        # resources
        r_SGIPrivate = SecurityGroupsIngressEcs(
            resname_private, proto=proto, scheme=scheme)
        r_SGIPrivate.CidrIp = get_endvalue(f'{ipname}Ip')

        add_obj(r_SGIPrivate)
