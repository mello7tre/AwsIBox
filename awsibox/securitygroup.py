import troposphere.ec2 as ec2

from .common import *
from .shared import (Parameter, get_endvalue, get_expvalue, get_subvalue,
                     auto_get_props, get_condition, add_obj)


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


class SecurityGroupIngress(ec2.SecurityGroupIngress):
    IpProtocol = 'tcp'


class SecurityGroupRule(ec2.SecurityGroupRule):
    IpProtocol = 'tcp'


class SecurityGroupIngressInstanceELBPorts(SecurityGroupIngress):
    def __init__(self, title, listener, **kwargs):
        super().__init__(title, **kwargs)
        name = self.title  # Ex. SecurityGroupIngressListeners1
        self.FromPort = get_endvalue(f'{listener}InstancePort')
        self.ToPort = get_endvalue(f'{listener}InstancePort')
        self.SourceSecurityGroupId = Ref('SecurityGroupLoadBalancer')
        self.GroupId = GetAtt('SecurityGroupInstancesRules', 'GroupId')


class SecurityGroupEcsService(SecurityGroup):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.Condition = 'NetworkModeAwsVpc'
        self.GroupDescription = 'Enable access to Service'
        self.SecurityGroupIngress = []


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


def SG_SecurityGroupRules(groupname, ingresses):
    SecurityGroup_Rules = []
    kwargs = {}

    # Trick to populate SecurityGroupIngress using cfg.Listeners
    if ingresses:
        # use SecurityGroupIngress
        prefix = f'{groupname}SecurityGroupIngress'
        use_listener = False
        cond_key = 'CidrIp'
    else:
        # use cfg.Listeners
        prefix = 'Listeners'
        ingresses = cfg.Listeners
        use_listener = True
        cond_key = 'Access'

    for n, v in ingresses.items():
        if use_listener:
            # Trick to populate SecurityGroupIngress using cfg.Listeners
            v['CidrIp'] = v['Access']
            v['FromPort'] = v['LoadBalancerPort']
            v['ToPort'] = v['LoadBalancerPort']
            kwargs = {'rootdict': v}

        resname = f'{prefix}{n}'
        allowed_ip = v.get('CidrIp') == 'AllowedIp'
        allowed_ip_or_public = v.get('AllowedIpOrPublic')
        if allowed_ip:
            for m, w in cfg.AllowedIp.items():
                r_SGRule = SecurityGroupRule(resname)
                auto_get_props(r_SGRule, **kwargs)
                auto_get_props(r_SGRule, f'AllowedIp{m}')
                SecurityGroup_Rules.append(If(
                    f'AllowedIp{m}',
                    r_SGRule,
                    Ref('AWS::NoValue')))

        if not allowed_ip or allowed_ip_or_public:
            r_SGRule = SecurityGroupRule(resname)
            auto_get_props(r_SGRule, **kwargs)

            if allowed_ip and allowed_ip_or_public:
                r_SGRule.CidrIp = '0.0.0.0/0'
                # condition
                c_Public = get_condition(
                    f'{resname}Public', 'equals', '0.0.0.0/0',
                    f'{resname}{cond_key}')
                add_obj(c_Public)
                r_SGRule = If(
                    f'{resname}Public', r_SGRule, Ref('AWS::NoValue'))

            SecurityGroup_Rules.append(r_SGRule)

    return SecurityGroup_Rules


def SG_SecurityGroup(key):
    for n, v in getattr(cfg, key).items():
        resname = f'{key}{n}'

        # resources
        r_SG = SecurityGroup(resname)
        auto_get_props(r_SG)
        try:
            ingresses = v['SecurityGroupIngress']
        except Exception:
            pass
        else:
            r_SG.SecurityGroupIngress = SG_SecurityGroupRules(
                resname, ingresses)

        try:
            outname = v['OutputName']
        except Exception:
            outname = resname
        else:
            outname = f'{key}{outname}'

        # outputs
        o_SG = Output(outname)
        o_SG.Value = GetAtt(resname, 'GroupId')
        if v.get('Export'):
            o_SG.Export = Export(outname)

        add_obj(r_SG)
        # add output only if not already present (can be created by IBOXOUTPUT)
        try:
            cfg.Outputs[outname]
        except Exception:
            add_obj(o_SG)


def SG_SecurityGroupIngresses(key):
    for n, v in getattr(cfg, key).items():
        if not v.get('IBOXENABLED', True):
            continue
        resname = f'{key}{n}'
        try:
            allowed_ip = (v['CidrIp'] == 'AllowedIp')
        except Exception:
            pass
        else:
            if allowed_ip:
                for m, w in cfg.AllowedIp.items():
                    r_SGI = SecurityGroupIngress(f'{resname}{m}')
                    auto_get_props(r_SGI, resname)
                    auto_get_props(r_SGI, f'AllowedIp{m}')
                    r_SGI.Condition = f'AllowedIp{m}'
                    add_obj(r_SGI)
                continue

        r_SGI = SecurityGroupIngress(resname)
        auto_get_props(r_SGI)
        add_obj(r_SGI)
