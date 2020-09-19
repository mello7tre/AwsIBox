import troposphere.elasticloadbalancing as elb
import troposphere.elasticloadbalancingv2 as elbv2
import troposphere.ec2 as ec2

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
                     get_subvalue, auto_get_props, get_condition, add_obj)
from .route53 import R53_RecordSetEC2LoadBalancer, R53_RecordSetECSLoadBalancer
from .securitygroup import (
    SecurityGroupRuleELBPorts, SecurityGroupIngressInstanceELBPorts,
    SecurityGroupLoadBalancer, SecurityGroupsIngressEcs, SecurityGroup,
    SecurityGroupRuleHttp, SecurityGroupRuleHttps,
    SG_SecurityGroupIngressesECS)
from .lambdas import LambdaPermissionLoadBalancing


# Temporary fix for https://github.com/cloudtools/troposphere/issues/1474
elbv2.one_of = my_one_of


# S - CLASSIC LOAD BALANCING #
class ELBListener(elb.Listener):
    def __init__(self, title, key, **kwargs):
        super().__init__(title, **kwargs)

        auto_get_props(self, key)
        self.PolicyNames = [
            If(
                'LoadBalancerCookieSticky',
                'LBCookieStickinessPolicy',
                Ref('AWS::NoValue')
            )
        ]
        self.SSLCertificateId = If(
            'ListenerLoadBalancerHttpsPort',
            If(
                'LoadBalancerSslCertificateAdHoc',
                Ref('CertificateLoadBalancerAdHocExternal'),
                get_endvalue('RegionalCertificateArn')
            ),
            Ref('AWS::NoValue')
        )


class ELBLoadBalancer(elb.LoadBalancer):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        self.AccessLoggingPolicy = If(
            'LoadBalancerLog',
            elb.AccessLoggingPolicy(
                EmitInterval=get_endvalue('LoadBalancerLog'),
                Enabled=True,
                S3BucketName=Sub(cfg.BucketLogs),
                S3BucketPrefix=''
            ),
            Ref('AWS::NoValue')
        )
        self.ConnectionDrainingPolicy = elb.ConnectionDrainingPolicy(
            Enabled=True,
            Timeout=5
        )
        self.ConnectionSettings = elb.ConnectionSettings(
            IdleTimeout=get_endvalue('LoadBalancerIdleTimeout')
        )
        self.CrossZone = True
        self.HealthCheck = elb.HealthCheck(
            HealthyThreshold=get_endvalue('HealthyThresholdCount'),
            Interval=get_endvalue('HealthCheckIntervalSeconds'),
            Target=get_endvalue('HealthCheckTarget'),
            Timeout=get_endvalue('HealthCheckTimeoutSeconds'),
            UnhealthyThreshold=get_endvalue('UnhealthyThresholdCount')
        )
        self.LBCookieStickinessPolicy = If(
            'LoadBalancerCookieSticky',
            [
                elb.LBCookieStickinessPolicy(
                    PolicyName='LBCookieStickinessPolicy',
                    CookieExpirationPeriod=get_endvalue(
                        'LoadBalancerCookieSticky')
                )
            ],
            Ref('AWS::NoValue')
        )
        self.SecurityGroups = [GetAtt('SecurityGroupLoadBalancer', 'GroupId')]


class ELBLoadBalancerExternal(ELBLoadBalancer):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        self.Scheme = 'internet-facing'
        self.Subnets = Split(',', get_expvalue('SubnetsPublic'))


class ELBLoadBalancerInternal(ELBLoadBalancer):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        self.Scheme = 'internal'
        self.Subnets = Split(',', get_expvalue('SubnetsPrivate'))
# E - CLASSIC LOAD BALANCING #


# S - V2 LOAD BALANCING #
class ELBV2Listener(elbv2.Listener):
    def __init__(self, title, scheme, **kwargs):
        super().__init__(title, **kwargs)

        self.DefaultActions = [elbv2.Action(
            Type='forward',
            TargetGroupArn=Ref(f'TargetGroup{scheme}')
        )]
        self.LoadBalancerArn = Ref(f'LoadBalancerApplication{scheme}')


class ELBV2ListenerHttp(ELBV2Listener):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        self.Port = get_endvalue('ListenerLoadBalancerHttpPort')
        self.Protocol = 'HTTP'


class ELBV2ListenerHttps(ELBV2Listener):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        self.Certificates = [elbv2.Certificate(
            CertificateArn=If(
                'LoadBalancerSslCertificateAdHoc',
                Ref('CertificateLoadBalancerAdHocExternal'),
                get_endvalue('RegionalCertificateArn')
            )
        )]
        self.Port = get_endvalue('ListenerLoadBalancerHttpsPort')
        self.Protocol = 'HTTPS'
        self.SslPolicy = get_endvalue('ListenerLoadBalancerSslPolicy')


class ELBV2TargetGroup(elbv2.TargetGroup):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        self.HealthCheckIntervalSeconds = get_endvalue(
            'HealthCheckIntervalSeconds')
        self.HealthCheckTimeoutSeconds = get_endvalue(
            'HealthCheckTimeoutSeconds')
        if cfg.HealthCheckPath != 'None':
            self.HealthCheckPath = get_endvalue(
                'HealthCheckPath')
        self.HealthyThresholdCount = get_endvalue(
            'HealthyThresholdCount')
        self.UnhealthyThresholdCount = get_endvalue(
            'UnhealthyThresholdCount')
        self.TargetGroupAttributes = [
            elbv2.TargetGroupAttribute(
                Key='deregistration_delay.timeout_seconds',
                Value=get_endvalue('TargetGroupDeregistrationDelay')
            ),
            elbv2.TargetGroupAttribute(
                Key='stickiness.enabled',
                Value=If(
                    'TargetGroupCookieSticky',
                    'true',
                    'false',
                )
            ),
            If(
                'TargetGroupCookieSticky',
                elbv2.TargetGroupAttribute(
                    Key='stickiness.lb_cookie.duration_seconds',
                    Value=get_endvalue('TargetGroupCookieSticky')
                ),
                Ref('AWS::NoValue')
            )
        ]
        self.Protocol = get_endvalue('TargetGroupProtocol')
        self.VpcId = get_expvalue('VpcId')


class ELBV2TargetGroupEC2(ELBV2TargetGroup):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        self.Port = get_endvalue('Listeners1InstancePort')


class ELBV2TargetGroupALB(elbv2.TargetGroup):
    def __init__(self, title, lambda_arn, **kwargs):
        super().__init__(title, **kwargs)

        self.Targets = [
            elbv2.TargetDescription(
                Id=lambda_arn,
            )
        ]
        self.TargetType = 'lambda'


class ELBV2TargetGroupECS(ELBV2TargetGroup):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        self.Port = get_endvalue('ContainerDefinitions1ContainerPort')
        self.TargetType = If(
            'NetworkModeAwsVpc',
            'ip',
            Ref('AWS::NoValue')
        )


class ELBV2ListernerRuleECS(elbv2.ListenerRule):
    def __init__(self, title, key, index, mapname, scheme, **kwargs):
        super().__init__(title, **kwargs)

        auto_get_props(
            self, key, mapname=f'ListenerRules{index}', recurse=True)
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


class ELBV2LoadBalancer(elbv2.LoadBalancer):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        self.LoadBalancerAttributes = [
            If(
                'LoadBalancerLog',
                {
                    'Key': 'access_logs.s3.bucket',
                    'Value': Sub(cfg.BucketLogs)
                },
                Ref('AWS::NoValue')
            ),
            If(
                'LoadBalancerLog',
                {
                    'Key': 'access_logs.s3.enabled',
                    'Value': True
                },
                {
                    'Key': 'access_logs.s3.enabled',
                    'Value': False
                },
            ),
            If(
                'LoadBalancerLog',
                {
                    'Key': 'access_logs.s3.prefix',
                    'Value': Sub('${EnvRole}.${AWS::StackName}')
                },
                Ref('AWS::NoValue')
            ),
            If(
                'LoadBalancerHttp2',
                {
                    'Key': 'routing.http2.enabled',
                    'Value': get_endvalue('LoadBalancerHttp2')
                },
                Ref('AWS::NoValue')
            ),
        ]
        self.SecurityGroups = [
            GetAtt('SecurityGroupLoadBalancer', 'GroupId')
        ]


class ELBV2LoadBalancerExternal(ELBV2LoadBalancer):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        self.Scheme = 'internet-facing'
        self.Subnets = Split(',', get_expvalue('SubnetsPublic'))


class ELBV2LoadBalancerInternal(ELBV2LoadBalancer):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        self.Scheme = 'internal'
        self.Subnets = Split(',', get_expvalue('SubnetsPrivate'))


class ELBV2LoadBalancerExternalALB(ELBV2LoadBalancerExternal):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        self.Condition = 'LoadBalancerApplicationExternal'
        self.SecurityGroups = [
            get_expvalue('SecurityGroupLoadBalancerApplicationExternal'),
            GetAtt(
                'SecurityGroupLoadBalancerApplicationExternal', 'GroupId'),
        ]


class ELBV2LoadBalancerInternalALB(ELBV2LoadBalancerInternal):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        self.Condition = 'LoadBalancerApplicationInternal'
        self.SecurityGroups = [
            get_expvalue('SecurityGroupLoadBalancerApplicationInternal'),
            GetAtt(
                'SecurityGroupLoadBalancerApplicationInternal', 'GroupId'),
        ]


class ELBV2ListenerAction404(elbv2.Action):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.FixedResponseConfig = elbv2.FixedResponseConfig('')
        self.FixedResponseConfig.ContentType = 'text/plain'
        self.FixedResponseConfig.MessageBody = '404 Not Found\n'
        self.FixedResponseConfig.StatusCode = '404'
        self.Type = 'fixed-response'


# E - V2 LOAD BALANCING #


# #################################
# ### START STACK INFRA CLASSES ###
# #################################

class LB_Listeners(object):
    def __init__(self):
        # Conditions
        for i in cfg.AllowedIp:
            condname = f'AllowedIp{i}'  # Ex. AllowedIp1

            c_Enabled = get_condition(
                condname, 'not_equals', 'None', f'{condname}Enabled')

            add_obj(c_Enabled)


class LB_ListenersEC2(LB_Listeners):
    def __init__(self):
        super().__init__()

        # Resources
        Listeners = []
        Securitygroup_Rules = []
        SecuritygroupIngress_InstanceRules = []
        for n, v in cfg.Listeners.items():
            mapname = f'Listeners{n}'  # Ex Listeners1

            if cfg.LoadBalancerClassic:
                Listener = ELBListener(mapname, key=v)
                Listeners.append(Listener)

            for i in cfg.AllowedIp:
                ipname = f'AllowedIp{i}'  # Ex. AllowedIp1
                condnameprivate = f'SecurityGroupRulePrivate{mapname}{ipname}'
                condnamepublic = f'SecurityGroupRulePublic{mapname}'

                # conditions
                c_LoadBalancerAccessAllowedIp = {condnameprivate: And(
                    Condition(ipname),
                    get_condition('', 'equals', 'Private',
                                  f'{mapname}LoadBalancerAccess')
                )}

                add_obj(c_LoadBalancerAccessAllowedIp)

                SGRule = SecurityGroupRuleELBPorts(mapname)
                SGRule.CidrIp = get_endvalue(f'{ipname}Ip')

                Securitygroup_Rules.append(
                    If(
                        condnameprivate,
                        SGRule,
                        Ref('AWS::NoValue'),
                    )
                )

            # conditions
            c_LoadBalancerAccessPublic = get_condition(
                condnamepublic,
                'equals', 'Public', f'{mapname}LoadBalancerAccess')
            add_obj(c_LoadBalancerAccessPublic)

            SGRule = SecurityGroupRuleELBPorts(mapname)
            SGRule.CidrIp = '0.0.0.0/0'

            Securitygroup_Rules.append(
                If(
                    condnamepublic,
                    SGRule,
                    Ref('AWS::NoValue'),
                )
            )

            # resources
            r_SGIInstance = SecurityGroupIngressInstanceELBPorts(
                f'SecurityGroupIngress{mapname}', listener=mapname)

            add_obj(r_SGIInstance)

            # outputs
            Listener_Output = Output(mapname)
            Listener_Output.Value = Sub(
                '${LoadBalancerPort}.${Protocol}.${LoadBalancerAccess}',
                **{
                    'LoadBalancerPort': get_endvalue(
                        f'{mapname}LoadBalancerPort'),
                    'Protocol': get_endvalue(
                        f'{mapname}Protocol'),
                    'LoadBalancerAccess': get_endvalue(
                        f'{mapname}LoadBalancerAccess')
                }
            )
            add_obj(Listener_Output)

        R_SG = SecurityGroupLoadBalancer('SecurityGroupLoadBalancer')
        R_SG.SecurityGroupIngress = Securitygroup_Rules

        add_obj([
            R_SG,
        ])

        # Outputs
        O_SG = Output('SecurityGroupLoadBalancer')
        O_SG.Value = Ref('SecurityGroupLoadBalancer')

        add_obj([
            O_SG,
        ])

        self.Listeners = Listeners


class LB_ListenerRulesExternalInternal(object):
    def __init__(self, index, key, mapname, scheme):
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


class LB_ListenerRules(object):
    def __init__(self):
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


class LB_ListenersV2ECSExternal(object):
    def __init__(self):
        if cfg.ListenerLoadBalancerHttpPort not in ['None', 80]:
            R_ListenerHttp = ELBV2ListenerHttp(
                'ListenerHttpExternal', scheme='External')
            R_ListenerHttp.LoadBalancerArn = get_expvalue(
                'LoadBalancerApplicationExternal',
                'LoadBalancerApplicationStack')

            add_obj(R_ListenerHttp)

            SG_SecurityGroupIngressesECS(scheme='External', proto='Http')

        if cfg.ListenerLoadBalancerHttpsPort not in ['None', 443]:
            R_ListenerHttps = ELBV2ListenerHttps(
                'ListenerHttpsExternal', scheme='External')
            R_ListenerHttps.Condition = 'ListenerLoadBalancerHttpsPort'
            R_ListenerHttps.LoadBalancerArn = get_expvalue(
                'LoadBalancerApplicationExternal',
                'LoadBalancerApplicationStack')

            add_obj(R_ListenerHttps)

            SG_SecurityGroupIngressesECS(scheme='External', proto='Https')


class LB_ListenersV2ECSInternal(object):
    def __init__(self):
        if cfg.ListenerLoadBalancerHttpPort not in ['None', 80]:
            R_ListenerHttp = ELBV2ListenerHttp(
                'ListenerHttpInternal', scheme='Internal')
            R_ListenerHttp.LoadBalancerArn = get_expvalue(
                'LoadBalancerApplicationInternal',
                'LoadBalancerApplicationStack')

            add_obj(R_ListenerHttp)

            SG_SecurityGroupIngressesECS(scheme='Internal', proto='Http')


class LB_ListenersV2EC2(LB_ListenersEC2):
    def __init__(self):
        super().__init__()
        # Resources
        if cfg.LoadBalancerApplicationExternal:
            R_ListenerHttpExternal = ELBV2ListenerHttp(
                'ListenerHttpExternal', scheme='External')
            R_ListenerHttpExternal.Condition = 'ListenerLoadBalancerHttpPort'

            R_ListenerHttpsExternal = ELBV2ListenerHttps(
                'ListenerHttpsExternal', scheme='External')
            R_ListenerHttpsExternal.Condition = 'ListenerLoadBalancerHttpsPort'

            add_obj([
                R_ListenerHttpExternal,
                R_ListenerHttpsExternal,
            ])

        if cfg.LoadBalancerApplicationInternal:
            R_ListenerHttpInternal = ELBV2ListenerHttp(
                'ListenerHttpInternal', scheme='Internal')
            R_ListenerHttpInternal.Condition = 'ListenerLoadBalancerHttpPort'

            add_obj([
                R_ListenerHttpInternal,
            ])

        LB_TargetGroupsEC2()


class LB_ListenersV2ECS(LB_Listeners):
    def __init__(self):
        super().__init__()
        # Resources
        if cfg.LoadBalancerApplicationExternal:
            LB_ListenersV2ECSExternal()

        if cfg.LoadBalancerApplicationInternal:
            LB_ListenersV2ECSInternal()

        LB_TargetGroupsECS()
        LB_ListenerRules()


class LB_ListenersV2ALB(object):
    def __init__(self):
        # Resources
        if cfg.LoadBalancerApplicationExternal:
            # CREATE SPECIFIC CLASS - EXTERNAL INTERNAL AS PARAMETER
            R_ListenerHttp = ELBV2ListenerHttp(
                'ListenerHttpDefaultExternal', scheme='External')
            # Now that AWS allow to send a fixed response, there is no need
            # to have a DefaultTarget Group pointing to nothing
            # R_ListenerHttp.DefaultActions[0].TargetGroupArn=Ref(
            #    'TargetGroupDefaultExternal')
            R_ListenerHttp.DefaultActions[0] = ELBV2ListenerAction404()
            R_ListenerHttp.Condition = 'LoadBalancerApplicationExternal'

            R_ListenerHttps = ELBV2ListenerHttps(
                'ListenerHttpsDefaultExternal', scheme='External')
            # Now that AWS allow to send a fixed response, there is no need
            # to have a DefaultTarget Group pointing to nothing
            # R_ListenerHttps.DefaultActions[0].TargetGroupArn=Ref(
            #    'TargetGroupDefaultExternal')
            R_ListenerHttps.DefaultActions[0] = ELBV2ListenerAction404()
            R_ListenerHttps.Certificates[0].CertificateArn = get_endvalue(
                'RegionalCertificateArn')
            R_ListenerHttps.Condition = 'LoadBalancerApplicationExternal'

            R_SGExternal = SecurityGroup(
                'SecurityGroupLoadBalancerApplicationExternal')
            R_SGExternal.Condition = 'LoadBalancerApplicationExternal'
            R_SGExternal.GroupDescription = Sub(
                'Access to LoadBalancerApplicationExternal ${AWS::StackName}')
            R_SGExternal.SecurityGroupIngress = [
                SecurityGroupRuleHttp(),
                SecurityGroupRuleHttps(),
            ]

            R_SGInternal = SecurityGroup(
                'SecurityGroupLoadBalancerApplicationInternal')
            R_SGInternal.Condition = 'LoadBalancerApplicationInternal'
            R_SGInternal.GroupDescription = Sub(
                'Access to LoadBalancerApplicationInternal ${AWS::StackName}')
            R_SGInternal.SecurityGroupIngress = [
                SecurityGroupRuleHttp(),
            ]

            add_obj([
                R_ListenerHttp,
                R_ListenerHttps,
                R_SGExternal,
                R_SGInternal,
            ])

            # Outputs
            O_ListenerHttp = Output('ListenerHttpDefaultExternal')
            O_ListenerHttp.Condition = 'LoadBalancerApplicationExternal'
            O_ListenerHttp.Value = Ref('ListenerHttpDefaultExternal')
            O_ListenerHttp.Export = Export(Sub(
                'ListenerHttpDefaultExternal-${AWS::StackName}'))

            O_ListenerHttps = Output('ListenerHttpsDefaultExternal')
            O_ListenerHttps.Condition = 'LoadBalancerApplicationExternal'
            O_ListenerHttps.Value = Ref('ListenerHttpsDefaultExternal')
            O_ListenerHttps.Export = Export(Sub(
                'ListenerHttpsDefaultExternal-${AWS::StackName}'))

            O_SGExternal = Output(
                'SecurityGroupLoadBalancerApplicationExternal')
            O_SGExternal.Condition = 'LoadBalancerApplicationExternal'
            O_SGExternal.Value = GetAtt(
                'SecurityGroupLoadBalancerApplicationExternal', 'GroupId')
            O_SGExternal.Export = Export(Sub(
                'SecurityGroupLoadBalancerApplicationExternal-'
                '${AWS::StackName}'))

            O_SGInternal = Output(
                'SecurityGroupLoadBalancerApplicationInternal')
            O_SGInternal.Condition = 'LoadBalancerApplicationInternal'
            O_SGInternal.Value = GetAtt(
                'SecurityGroupLoadBalancerApplicationInternal', 'GroupId')
            O_SGInternal.Export = Export(Sub(
                'SecurityGroupLoadBalancerApplicationInternal-'
                '${AWS::StackName}'))

            add_obj([
                O_ListenerHttp,
                O_ListenerHttps,
                O_SGExternal,
                O_SGInternal,
            ])

        if cfg.LoadBalancerApplicationInternal:
            R_ListenerHttp = ELBV2ListenerHttp(
                'ListenerHttpDefaultInternal', scheme='Internal')
            # Now that AWS allow to send a fixed response, there is no need
            # to have a DefaultTarget Group pointing to nothing
            # R_ListenerHttp.DefaultActions[0].TargetGroupArn=Ref(
            #    'TargetGroupDefaultInternal')
            R_ListenerHttp.DefaultActions[0] = ELBV2ListenerAction404()
            R_ListenerHttp.Condition = 'LoadBalancerApplicationInternal'

            R_SGInternal = SecurityGroup(
                'SecurityGroupLoadBalancerApplicationInternal')
            R_SGInternal.Condition = 'LoadBalancerApplicationInternal'
            R_SGInternal.GroupDescription = Sub(
                'Access to LoadBalancerApplicationInternal ${AWS::StackName}')
            R_SGInternal.SecurityGroupIngress = [
                SecurityGroupRuleHttp(),
            ]

            add_obj([
                R_ListenerHttp,
                R_SGInternal,
            ])

            # Outputs
            O_ListenerHttp = Output('ListenerHttpDefaultInternal')
            O_ListenerHttp.Condition = 'LoadBalancerApplicationInternal'
            O_ListenerHttp.Value = Ref('ListenerHttpDefaultInternal')
            O_ListenerHttp.Export = Export(Sub(
                'ListenerHttpDefaultInternal-${AWS::StackName}'))

            O_SGInternal = Output(
                'SecurityGroupLoadBalancerApplicationInternal')
            O_SGInternal.Condition = 'LoadBalancerApplicationInternal'
            O_SGInternal.Value = GetAtt(
                'SecurityGroupLoadBalancerApplicationInternal', 'GroupId')
            O_SGInternal.Export = Export(Sub(
                'SecurityGroupLoadBalancerApplicationInternal-'
                '${AWS::StackName}'))

            add_obj([
                O_ListenerHttp,
            ])


class LB_TargetGroups(object):
    def __init__(self):
        # Conditions
        add_obj(get_condition(
            'TargetGroupCookieSticky', 'not_equals', 'None'))


class LB_TargetGroupsEC2(LB_TargetGroups):
    def __init__(self):
        super().__init__()
        # Resources
        if cfg.LoadBalancerApplicationExternal:
            R_TargetGroup = ELBV2TargetGroupEC2('TargetGroupExternal')

            add_obj(R_TargetGroup)

            cfg.Alarm['TargetEC2External5XX']['Enabled'] = True

        if cfg.LoadBalancerApplicationInternal:
            R_TargetGroup = ELBV2TargetGroupEC2('TargetGroupInternal')

            add_obj(R_TargetGroup)

            cfg.Alarm['TargetEC2Internal5XX']['Enabled'] = True


class LB_TargetGroupsECS(LB_TargetGroups):
    def __init__(self):
        super().__init__()
        # Resources
        if cfg.LoadBalancerApplicationExternal:
            R_TargetGroup = ELBV2TargetGroupECS('TargetGroupExternal')

            add_obj(R_TargetGroup)

            cfg.Alarm['TargetExternal5XX']['Enabled'] = True

        if cfg.LoadBalancerApplicationInternal:
            R_TargetGroup = ELBV2TargetGroupECS('TargetGroupInternal')

            add_obj(R_TargetGroup)

            cfg.Alarm['TargetInternal5XX']['Enabled'] = True


class LB_TargetGroupsALB(object):
    def __init__(self):
        lambda_name = 'ServiceUnavailable'
        lambda_arn = get_expvalue(f'Lambda{lambda_name}Arn')
        perm_name = f'LambdaPermission{lambda_name}LoadBalancerApplication'

        # Resources
        if cfg.LoadBalancerApplicationExternal:
            R_TargetGroup = ELBV2TargetGroupALB(
                'TargetGroupServiceUnavailableExternal', lambda_arn=lambda_arn)
            R_TargetGroup.Condition = 'LoadBalancerApplicationExternal'
            R_TargetGroup.DependsOn = f'{perm_name}External'

            R_Permission = LambdaPermissionLoadBalancing(
                f'{perm_name}External', name=lambda_arn)

            R_Permission.Condition = 'LoadBalancerApplicationExternal'

            O_TargetGroup = Output('TargetGroupServiceUnavailableExternal')
            O_TargetGroup.Condition = 'LoadBalancerApplicationExternal'
            O_TargetGroup.Value = Ref('TargetGroupServiceUnavailableExternal')

            add_obj([
                R_TargetGroup,
                R_Permission,
                O_TargetGroup,
            ])

        if cfg.LoadBalancerApplicationInternal:
            R_TargetGroup = ELBV2TargetGroupALB(
                'TargetGroupServiceUnavailableInternal', lambda_arn=lambda_arn)
            R_TargetGroup.Condition = 'LoadBalancerApplicationInternal'
            R_TargetGroup.DependsOn = f'{perm_name}Internal'

            R_Permission = LambdaPermissionLoadBalancing(
                f'{perm_name}Internal', name=lambda_arn)

            R_Permission.Condition = 'LoadBalancerApplicationInternal'

            O_TargetGroup = Output('TargetGroupServiceUnavailableInternal')
            O_TargetGroup.Condition = 'LoadBalancerApplicationInternal'
            O_TargetGroup.Value = Ref('TargetGroupServiceUnavailableInternal')

            add_obj([
                R_TargetGroup,
                R_Permission,
                O_TargetGroup,
            ])


class LB_ElasticLoadBalancingApplication(object):
    def __init__(self):
        # Parameters
        P_Http2 = Parameter('LoadBalancerHttp2')
        P_Http2.Description = (
            'Load Balancer Http2 - empty for default based on env/role')
        P_Http2.AllowedValues = ['', 'true', 'false']

        add_obj([
            P_Http2,
        ])

        # Conditions
        add_obj(get_condition('LoadBalancerHttp2', 'not_equals', 'None'))


class LB_ElasticLoadBalancingClassicEC2(LB_ListenersEC2):
    def __init__(self):
        super().__init__()
        # Conditions
        add_obj(get_condition(
            'LoadBalancerCookieSticky', 'not_equals', 'None'))

        # Resources
        if cfg.LoadBalancerClassicExternal:
            R_ELBExternal = ELBLoadBalancerExternal(
                'LoadBalancerClassicExternal')
            R_ELBExternal.Listeners = self.Listeners

            add_obj(R_ELBExternal)

            cfg.Alarm['BackendExternal5XX']['Enabled'] = True

        if cfg.LoadBalancerClassicInternal:
            R_ELBInternal = ELBLoadBalancerInternal(
                'LoadBalancerClassicInternal')
            R_ELBInternal.Listeners = self.Listeners

            add_obj(R_ELBInternal)

            cfg.Alarm['BackendInternal5XX']['Enabled'] = True

        # Outputs
        O_HealthCheck = Output('HealthCheck')
        O_HealthCheck.Value = Sub(
            'Type=${Type},Target=${Target},Interval=${Interval},'
            'Timeout=${Timeout},Healthy=${Healthy},Unhealthy=${Unhealthy}',
            **{
                'Type': get_endvalue('HealthCheckType'),
                'Target': get_endvalue('HealthCheckTarget')
                if cfg.HealthCheckTarget != 'None' else '',
                'Interval': get_endvalue('HealthCheckIntervalSeconds'),
                'Timeout': get_endvalue('HealthCheckTimeoutSeconds'),
                'Healthy': get_endvalue('HealthyThresholdCount'),
                'Unhealthy': get_endvalue('UnhealthyThresholdCount'),
            }
        )

        add_obj([
            O_HealthCheck,
        ])


class LB_ElasticLoadBalancingApplicationEC2(object):
    def __init__(self):
        LB_ElasticLoadBalancingApplication()
        # Resources
        if cfg.LoadBalancerApplicationExternal:
            R_ELBExternal = ELBV2LoadBalancerExternal(
                'LoadBalancerApplicationExternal')

            add_obj([
                R_ELBExternal,
            ])

        if cfg.LoadBalancerApplicationInternal:
            R_ELBInternal = ELBV2LoadBalancerInternal(
                'LoadBalancerApplicationInternal')

            add_obj([
                R_ELBInternal,
            ])

        LB_ListenersV2EC2()

        # outputs
        O_HealthCheck = Output('HealthCheck')
        O_HealthCheck.Value = Sub(
            'Type=${Type},Path=${Path},Interval=${Interval},'
            'Timeout=${Timeout},Healthy=${Healthy},Unhealthy=${Unhealthy}',
            **{
                'Type': get_endvalue('HealthCheckType'),
                'Path': get_endvalue('HealthCheckPath')
                if cfg.HealthCheckPath != 'None' else '',
                'Interval': get_endvalue('HealthCheckIntervalSeconds'),
                'Timeout': get_endvalue('HealthCheckTimeoutSeconds'),
                'Healthy': get_endvalue('HealthyThresholdCount'),
                'Unhealthy': get_endvalue('UnhealthyThresholdCount'),
            }
        )

        add_obj([
            O_HealthCheck,
        ])


class LB_ElasticLoadBalancingEC2(object):
    def __init__(self, key):
        # Resources
        R53_RecordSetEC2LoadBalancer()

        if cfg.LoadBalancerClassic:
            LB_ElasticLoadBalancingClassicEC2()

        if cfg.LoadBalancerApplication:
            LB_ElasticLoadBalancingApplicationEC2()


class LB_ElasticLoadBalancingALB(object):
    def __init__(self, key):
        LB_ElasticLoadBalancingApplication()

        if cfg.LoadBalancerApplicationExternal:
            # Resources
            R_ELB = ELBV2LoadBalancerExternalALB(
                'LoadBalancerApplicationExternal')

            add_obj(R_ELB)

            # Outputs
            O_ELB = Output('LoadBalancerApplicationExternal')
            O_ELB.Condition = 'LoadBalancerApplicationExternal'
            O_ELB.Value = Ref('LoadBalancerApplicationExternal')
            O_ELB.Export = Export(Sub(
                'LoadBalancerApplicationExternal-${AWS::StackName}'))

            O_ELBDNS = Output('LoadBalancerApplicationExternalDNS')
            O_ELBDNS.Condition = 'LoadBalancerApplicationExternal'
            O_ELBDNS.Value = GetAtt(
                'LoadBalancerApplicationExternal', 'DNSName')
            O_ELBDNS.Export = Export(Sub(
                'LoadBalancerApplicationExternalDNS-${AWS::StackName}'))

            O_ELBFullName = Output('LoadBalancerApplicationExternalFullName')
            O_ELBFullName.Condition = 'LoadBalancerApplicationExternal'
            O_ELBFullName.Value = GetAtt(
                'LoadBalancerApplicationExternal', 'LoadBalancerFullName')
            O_ELBFullName.Export = Export(Sub(
                'LoadBalancerApplicationExternalFullName-${AWS::StackName}'))

            add_obj([
                O_ELB,
                O_ELBDNS,
                O_ELBFullName,
            ])

        if cfg.LoadBalancerApplicationInternal:
            # Resources
            R_ELB = ELBV2LoadBalancerInternalALB(
                'LoadBalancerApplicationInternal')

            add_obj(R_ELB)

            # Outputs
            O_ELB = Output('LoadBalancerApplicationInternal')
            O_ELB.Condition = 'LoadBalancerApplicationInternal'
            O_ELB.Value = Ref('LoadBalancerApplicationInternal')
            O_ELB.Export = Export(Sub(
                'LoadBalancerApplicationInternal-${AWS::StackName}'))

            O_ELBDNS = Output('LoadBalancerApplicationInternalDNS')
            O_ELBDNS.Condition = 'LoadBalancerApplicationInternal'
            O_ELBDNS.Value = GetAtt(
                'LoadBalancerApplicationInternal', 'DNSName')
            O_ELBDNS.Export = Export(Sub(
                'LoadBalancerApplicationInternalDNS-${AWS::StackName}'))

            O_ELBFullName = Output('LoadBalancerApplicationInternalFullName')
            O_ELBFullName.Condition = 'LoadBalancerApplicationInternal'
            O_ELBFullName.Value = GetAtt(
                'LoadBalancerApplicationInternal', 'LoadBalancerFullName')
            O_ELBFullName.Export = Export(Sub(
                'LoadBalancerApplicationInternalFullName-${AWS::StackName}'))

            add_obj([
                O_ELB,
                O_ELBDNS,
                O_ELBFullName,
            ])

        # Resources
        LB_ListenersV2ALB()
        # Create TargetGroups pointing to LambdaServiceUnavailable
        try:
            cfg.ServiceUnavailable
        except Exception:
            pass
        else:
            LB_TargetGroupsALB()


class LB_ElasticLoadBalancingECS(object):
    def __init__(self, key):
        # Resources
        LB_ListenersV2ECS()
        R53_RecordSetECSLoadBalancer()
