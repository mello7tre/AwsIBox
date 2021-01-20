import troposphere.elasticloadbalancing as elb
import troposphere.elasticloadbalancingv2 as elbv2
import troposphere.ec2 as ec2

from .common import *
from .shared import (Parameter, get_endvalue, get_expvalue, get_subvalue,
                     auto_get_props, get_condition, add_obj)
from .route53 import R53_RecordSetEC2LoadBalancer, R53_RecordSetECSLoadBalancer
from .securitygroup import SecurityGroupIngressInstanceELBPorts
from .lambdas import LambdaPermissionLoadBalancing


# Temporary fix for https://github.com/cloudtools/troposphere/issues/1474
elbv2.one_of = my_one_of


# S - V2 LOAD BALANCING #
class ELBV2ListernerRuleECS(elbv2.ListenerRule):
    def __init__(self, title, key, index, mapname, scheme, **kwargs):
        super().__init__(title, **kwargs)

        auto_get_props(self, f'ListenerRules{index}')
        if 'Conditions' not in key:
            self.Conditions = []
            if 'HostHeader' in key:
                self.Conditions.append(elbv2.Condition(
                    Field='host-header',
                    Values=[get_endvalue(f'{mapname}HostHeader', issub=True)]
                ))
            if 'PathPattern' in key:
                self.Conditions.append(elbv2.Condition(
                    Field='path-pattern',
                    Values=[
                        Sub('${Value}', **{'Value': get_endvalue(
                            f'{mapname}PathPattern')})
                    ]
                ))
        if 'Actions' not in key:
            self.Actions = [elbv2.Action(
                Type='forward',
                TargetGroupArn=Ref(f'TargetGroup{scheme}')
            )]
        self.Priority = get_endvalue(f'{mapname}Priority')


# E - V2 LOAD BALANCING #


def LB_ListenersEC2():
    # Resources
    Listeners = []
    for n, v in cfg.Listeners.items():
        mapname = f'Listeners{n}'  # Ex ListenersPort5601

        if cfg.LoadBalancerClassic:
            Listener = elb.Listener(mapname)
            auto_get_props(Listener)
            auto_get_props(Listener, 'ListenerClassic')
            Listeners.append(Listener)

        # resources
        r_SGIInstance = SecurityGroupIngressInstanceELBPorts(
            f'SecurityGroupIngress{mapname}', listener=mapname)

        add_obj(r_SGIInstance)

        # outputs
        Listener_Output = Output(mapname)
        Listener_Output.Value = Sub(
            'Protocol=${Protocol},Access=${Access}',
            **{
                'Protocol': get_endvalue(
                    f'{mapname}Protocol'),
                'Access': get_endvalue(
                    f'{mapname}Access')
            }
        )
        add_obj(Listener_Output)

    return Listeners


def LB_ListenerRulesExternalInternal(index, key, mapname, scheme):
    # resources
    R_RuleHttp = ELBV2ListernerRuleECS(
        f'ListenerHttp{scheme}Rules{index}',
        key=key, index=index, mapname=mapname, scheme=scheme)
    R_RuleHttp.ListenerArn = get_expvalue(
        f'ListenerHttpDefault{scheme}', 'LoadBalancerApplicationStack')
    R_RuleHttp.Condition = 'ListenerLoadBalancerHttpPort'

    R_RuleHttps = ELBV2ListernerRuleECS(
        f'ListenerHttps{scheme}Rules{index}',
        key=key, index=index, mapname=mapname, scheme=scheme)
    R_RuleHttps.ListenerArn = get_expvalue(
        f'ListenerHttpsDefault{scheme}', 'LoadBalancerApplicationStack')
    R_RuleHttps.Condition = 'ListenerLoadBalancerHttpsPort'

    # Create ListenerRule only in stack's specific new Listener
    ListenerHttpPort = cfg.ListenerLoadBalancerHttpPort
    ListenerHttpsPort = cfg.ListenerLoadBalancerHttpsPort

    Protocol = key['Protocol'] if 'Protocol' in key else 'auto'

    RuleHttpAdd = None
    RuleHttpsAdd = None

    if 'NoDefault' in key:
        R_RuleHttp.ListenerArn = Ref(f'ListenerHttp{scheme}')
        R_RuleHttps.ListenerArn = Ref(f'ListenerHttps{scheme}')
        if ListenerHttpPort != 80:
            RuleHttpAdd = True
        if ListenerHttpsPort != 443:
            RuleHttpsAdd = True
    else:
        # by default create http rules on Internal LB
        # and https rules on External one
        if scheme == 'Internal':
            RuleHttpAdd = True
        if scheme == 'External':
            RuleHttpsAdd = True
            # on External can be forced or overriden by key http/https/any
            if Protocol == 'http':
                RuleHttpAdd = True
                RuleHttpsAdd = None
            if Protocol == 'https':
                RuleHttpAdd = None
                RuleHttpsAdd = True
            if Protocol == 'any':
                RuleHttpAdd = True
                RuleHttpsAdd = True

    if RuleHttpAdd:
        add_obj(R_RuleHttp)
    if RuleHttpsAdd:
        add_obj(R_RuleHttps)


def LB_ListenerRules():
    for n, v in cfg.ListenerRules.items():
        mapname = f'ListenerRules{n}'  # Ex. ListenerRules1

        # parameters
        p_Priority = Parameter(f'{mapname}Priority')
        p_Priority.Description = (
            'Listener Rule Priority, lesser value = high priority - '
            'empty for default based on env/role')

        add_obj(p_Priority)

        ListenerRule_Out_String = ['Priority=${Priority}']
        ListenerRule_Out_Map = {'Priority': get_endvalue(
            f'{mapname}Priority')}

        if 'HostHeader' in v:
            p_HostHeader = Parameter(f'{mapname}HostHeader')
            p_HostHeader.Description = (
                'Listener Rule HostHeader Condition - '
                'empty for default based on env/role')

            add_obj(p_HostHeader)

            # outputs
            ListenerRule_Out_String.append('HostHeader=${HostHeader}')
            ListenerRule_Out_Map.update({
                'HostHeader': get_endvalue(
                    f'{mapname}HostHeader', issub=True)
            })

        if 'PathPattern' in v:
            p_PathPattern = Parameter(f'{mapname}PathPattern')
            p_PathPattern.Description = (
                'Listener Rule PathPattern Condition - '
                'empty for default based on env/role')

            add_obj(p_PathPattern)

            # outputs
            ListenerRule_Out_String.append('PathPattern=${PathPattern}')
            ListenerRule_Out_Map.update({
                'PathPattern': get_endvalue(
                    f'{mapname}PathPattern', issub=True)
            })

        # resources
        if cfg.LoadBalancerApplicationExternal:
            LB_ListenerRulesExternalInternal(
                index=str(n), key=v, mapname=mapname, scheme='External')

        if cfg.LoadBalancerApplicationInternal:
            LB_ListenerRulesExternalInternal(
                index=str(n), key=v, mapname=mapname, scheme='Internal')

        # outputs
        o_ListenerRule = Output(mapname)
        o_ListenerRule.Value = Sub(
            ','.join(ListenerRule_Out_String), **ListenerRule_Out_Map)

        add_obj(o_ListenerRule)


def LB_ListenersV2EC2():
    LB_ListenersEC2()
    for n in ['External', 'Internal']:
        # resources
        if n not in cfg.LoadBalancerApplication:
            continue
        r_Http = elbv2.Listener(f'ListenerHttp{n}')
        auto_get_props(r_Http, mapname=f'ListenerV2EC2Http{n}')
        add_obj(r_Http)

        if n == 'External':
            r_Https = elbv2.Listener(f'ListenerHttps{n}')
            auto_get_props(r_Https, mapname=f'ListenerV2EC2Https{n}')
            add_obj(r_Https)

    LB_TargetGroupsEC2()


def LB_ListenersV2ECS():
    for n in ['External', 'Internal']:
        # resources
        if n not in cfg.LoadBalancerApplication:
            continue
        if cfg.ListenerLoadBalancerHttpPort not in ['None', 80]:
            # Enable the relative LB SecurityGroupIngress
            cfg.SecurityGroupIngress[
                f'LoadBalancerApplicationHttp{n}']['IBOXENABLED'] = True
            r_Http = elbv2.Listener(f'ListenerHttp{n}')
            auto_get_props(r_Http, mapname=f'ListenerV2ECSHttp{n}')
            add_obj(r_Http)

        if (cfg.ListenerLoadBalancerHttpsPort not in ['None', 443]
                and n == 'External'):
            # Enable the relative LB SecurityGroupIngress
            cfg.SecurityGroupIngress[
                f'LoadBalancerApplicationHttps{n}']['IBOXENABLED'] = True
            r_Https = elbv2.Listener(f'ListenerHttps{n}')
            auto_get_props(r_Https, mapname=f'ListenerV2ECSHttps{n}')
            add_obj(r_Https)

    # Resources
    LB_TargetGroupsECS()
    LB_ListenerRules()


def LB_TargetGroupsEC2():
    for n in ['External', 'Internal']:
        # resources
        if n not in cfg.LoadBalancerApplication:
            continue
        r_TG = elbv2.TargetGroup(f'TargetGroup{n}')
        auto_get_props(r_TG,
                       mapname=f'ElasticLoadBalancingV2TargetGroupEC2')
        add_obj(r_TG)

        cfg.Alarm[f'TargetEC2{n}5XX']['IBOXENABLED'] = True


def LB_TargetGroupsECS():
    for n in ['External', 'Internal']:
        # resources
        if n not in cfg.LoadBalancerApplication:
            continue
        r_TG = elbv2.TargetGroup(f'TargetGroup{n}')
        auto_get_props(r_TG,
                       mapname=f'ElasticLoadBalancingV2TargetGroupECS')
        add_obj(r_TG)

        cfg.Alarm[f'Target{n}5XX']['IBOXENABLED'] = True


def LB_TargetGroupsALB():
    lambda_name = 'ServiceUnavailable'
    lambda_arn = get_expvalue(f'Lambda{lambda_name}Arn')
    perm_name = f'LambdaPermission{lambda_name}LoadBalancerApplication'

    for n in ['External', 'Internal']:
        # resources
        if n not in cfg.LoadBalancerApplication:
            continue
        r_TG = elbv2.TargetGroup(f'TargetGroupServiceUnavailable{n}')
        auto_get_props(r_TG,
                       mapname=f'ElasticLoadBalancingV2TargetGroupALB')
        r_TG.DependsOn = f'{perm_name}{n}'
        r_TG.Condition = f'LoadBalancerApplication{n}'

        r_LambdaPermission = LambdaPermissionLoadBalancing(
            f'{perm_name}{n}', name=lambda_arn)
        r_LambdaPermission.Condition = f'LoadBalancerApplication{n}'

        o_TargetGroup = Output(f'TargetGroupServiceUnavailable{n}')
        o_TargetGroup.Condition = f'LoadBalancerApplication{n}'
        o_TargetGroup.Value = Ref(f'TargetGroupServiceUnavailable{n}')

        add_obj([
            r_TG,
            r_LambdaPermission,
            o_TargetGroup])


def LB_ElasticLoadBalancingClassicEC2():
    Listeners = LB_ListenersEC2()
    for n, v in cfg.ElasticLoadBalancingLoadBalancer.items():
        # resources
        if n not in cfg.LoadBalancerClassic:
            continue
        r_LB = elb.LoadBalancer(f'LoadBalancerClassic{n}')
        auto_get_props(r_LB, mapname=f'ElasticLoadBalancingLoadBalancer{n}')
        r_LB.Listeners = Listeners

        add_obj(r_LB)
        cfg.Alarm[f'Backend{n}5XX']['IBOXENABLED'] = True


def LB_ElasticLoadBalancingApplicationEC2():
    for n, v in cfg.ElasticLoadBalancingV2LoadBalancer.items():
        # resources
        if n not in cfg.LoadBalancerApplication:
            continue
        r_LB = elbv2.LoadBalancer(f'LoadBalancerApplication{n}')
        auto_get_props(r_LB, mapname=f'ElasticLoadBalancingV2LoadBalancer{n}')
        add_obj(r_LB)

    LB_ListenersV2EC2()


def LB_ElasticLoadBalancingEC2(key):
    # Resources
    R53_RecordSetEC2LoadBalancer()

    if cfg.LoadBalancerClassic:
        LB_ElasticLoadBalancingClassicEC2()

    if cfg.LoadBalancerApplication:
        LB_ElasticLoadBalancingApplicationEC2()


def LB_ElasticLoadBalancingALB(key):
    for n, v in cfg.ElasticLoadBalancingV2LoadBalancerALB.items():
        # resources
        if n not in cfg.LoadBalancerApplication:
            continue
        r_LB = elbv2.LoadBalancer(f'LoadBalancerApplication{n}')
        auto_get_props(r_LB,
                       mapname=f'ElasticLoadBalancingV2LoadBalancerALB{n}')

        r_ListenerHttp = elbv2.Listener(f'ListenerHttpDefault{n}')
        auto_get_props(r_ListenerHttp, mapname=f'ListenerV2ALBHttp{n}')

        if n == 'External':
            # Https enabled only for External ELB
            r_ListenerHttps = elbv2.Listener(f'ListenerHttpsDefault{n}')
            auto_get_props(r_ListenerHttps, mapname=f'ListenerV2ALBHttps{n}')
            add_obj(r_ListenerHttps)

        add_obj([
            r_LB,
            r_ListenerHttp])

    # Resources
    # Create TargetGroups pointing to LambdaServiceUnavailable
    try:
        cfg.ServiceUnavailable
    except Exception:
        pass
    else:
        LB_TargetGroupsALB()


def LB_ElasticLoadBalancingECS(key):
    # Resources
    LB_ListenersV2ECS()
    R53_RecordSetECSLoadBalancer()
