import troposphere.elasticloadbalancing as elb
import troposphere.elasticloadbalancingv2 as elbv2
import troposphere.ec2 as ec2

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
    get_subvalue, auto_get_props, get_condition)
from .route53 import R53_RecordSetEC2LoadBalancer, R53_RecordSetECSLoadBalancer
from .securitygroup import (SecurityGroupRuleELBPorts,SecurityGroupIngressInstanceELBPorts,
    SecurityGroupLoadBalancer, SecurityGroupsIngressEcs)


# S - CLASSIC LOAD BALANCING #
class ELBListener(elb.Listener):
    def setup(self, key):
        auto_get_props(self, key)
        self.PolicyNames = [
            If('LoadBalancerCookieSticky', 'LBCookieStickinessPolicy', Ref('AWS::NoValue'))
        ]
        self.SSLCertificateId = If(
            'ListenerLoadBalancerHttpsPort',
            If(
                'LoadBalancerSslCertificateAdHoc',
                Ref('CertificateLoadBalancerAdHocExternal'),
                get_endvalue('LoadBalancerSslCertificateArn')
            ),
            Ref('AWS::NoValue')
        )


class ELBLoadBalancer(elb.LoadBalancer):
    def setup(self):
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
                    CookieExpirationPeriod=get_endvalue('LoadBalancerCookieSticky')
                )
            ],
            Ref('AWS::NoValue')
        )
        self.SecurityGroups = [GetAtt('SecurityGroupLoadBalancer', 'GroupId')]


class ELBLoadBalancerExternal(ELBLoadBalancer):
    def setup(self):
        super(ELBLoadBalancerExternal, self).setup()
        self.Scheme = 'internet-facing'
        self.Subnets = Split(',', get_expvalue('SubnetsPublic'))


class ELBLoadBalancerInternal(ELBLoadBalancer):
    def setup(self):
        super(ELBLoadBalancerInternal, self).setup()
        self.Scheme = 'internal'
        self.Subnets = Split(',', get_expvalue('SubnetsPrivate'))
# E - CLASSIC LOAD BALANCING #


# S - V2 LOAD BALANCING #
class ELBV2Listener(elbv2.Listener):
    def setup(self, scheme):  # Ex. scheme = External/Internal
        self.DefaultActions = [elbv2.Action(
            Type='forward',
            TargetGroupArn=Ref('TargetGroup' + scheme)
        )]
        self.LoadBalancerArn = Ref('LoadBalancerApplication' + scheme)


class ELBV2ListenerHttp(ELBV2Listener):
    def setup(self, **kwargs):
        super(ELBV2ListenerHttp, self).setup(**kwargs)
        self.Port = get_endvalue('ListenerLoadBalancerHttpPort')
        self.Protocol = 'HTTP'


class ELBV2ListenerHttps(ELBV2Listener):
    def setup(self, **kwargs):
        super(ELBV2ListenerHttps, self).setup(**kwargs)
        self.Certificates = [elbv2.Certificate(
            CertificateArn=If(
                'LoadBalancerSslCertificateAdHoc',
                Ref('CertificateLoadBalancerAdHocExternal'),
                get_endvalue('LoadBalancerSslCertificateArn')
            )
        )]
        self.Port = get_endvalue('ListenerLoadBalancerHttpsPort')
        self.Protocol = 'HTTPS'


class ELBV2TargetGroup(elbv2.TargetGroup):
    def setup(self):
        self.HealthCheckIntervalSeconds = get_endvalue('HealthCheckIntervalSeconds')
        self.HealthCheckTimeoutSeconds = get_endvalue('HealthCheckTimeoutSeconds')
        if cfg.HealthCheckPath != 'None':
            self.HealthCheckPath = get_endvalue('HealthCheckPath')
        self.HealthyThresholdCount = get_endvalue('HealthyThresholdCount')
        self.UnhealthyThresholdCount = get_endvalue('UnhealthyThresholdCount')
        self.TargetGroupAttributes = [
            elbv2.TargetGroupAttribute(
                Key='deregistration_delay.timeout_seconds',
                Value=get_endvalue('TargetGroupDeregistrationDelay')
            ),
            If(
                'TargetGroupCookieSticky',
                elbv2.TargetGroupAttribute(
                    Key='stickiness.enabled',
                    Value='true'
                ),
                Ref('AWS::NoValue')
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
        self.VpcId = get_expvalue('VpcId')


class ELBV2TargetGroupEC2(ELBV2TargetGroup):
    def setup(self):
        super(ELBV2TargetGroupEC2, self).setup()
        self.Port = get_endvalue('Listeners1InstancePort')
        self.Protocol = get_endvalue('Listeners1Protocol')


class ELBV2TargetGroupALB(elbv2.TargetGroup):
    def setup(self):
        self.Port = 80
        self.Protocol = 'HTTP'
        self.VpcId = get_expvalue('VpcId')


class ELBV2TargetGroupECS(ELBV2TargetGroup):
    def setup(self):
        super(ELBV2TargetGroupECS, self).setup()
        self.Port = get_endvalue('ContainerDefinitions1ContainerPort')
        self.Protocol = get_endvalue('ContainerDefinitions1Protocol')
        self.TargetType = If(
            'NetworkModeAwsVpc',
            'ip',
            Ref('AWS::NoValue')
        )


class ELBV2ListernerRuleECS(elbv2.ListenerRule):
    def setup(self, key, index, mapname, scheme):
        auto_get_props(self, key, mapname='ListenerRules%s' % index, recurse=True)
        if 'Conditions' not in key:
            self.Conditions = []
            if 'HostHeader' in key:
                self.Conditions.append(elbv2.Condition(
                    Field='host-header',
                    Values=[get_endvalue(mapname + 'HostHeader', issub=True)]
                ))
            if 'PathPattern' in key:
                self.Conditions.append(elbv2.Condition(
                    Field='path-pattern',
                    Values=[Sub('${Value}', **{'Value': get_endvalue(mapname + 'PathPattern')})]
                ))
        if 'Actions' not in key:
            self.Actions = [elbv2.Action(
                Type='forward',
                TargetGroupArn=Ref('TargetGroup' + scheme)
            )]
        self.Priority = get_endvalue(mapname + 'Priority')


class ELBV2LoadBalancer(elbv2.LoadBalancer):
    def setup(self):
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
                Ref('AWS::NoValue')
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
    def setup(self):
        super(ELBV2LoadBalancerExternal, self).setup()
        self.Scheme = 'internet-facing'
        self.Subnets = Split(',', get_expvalue('SubnetsPublic'))


class ELBV2LoadBalancerInternal(ELBV2LoadBalancer):
    def setup(self):
        super(ELBV2LoadBalancerInternal, self).setup()
        self.Scheme = 'internal'
        self.Subnets = Split(',', get_expvalue('SubnetsPrivate'))


class ELBV2LoadBalancerExternalALB(ELBV2LoadBalancerExternal):
    def setup(self):
        super(ELBV2LoadBalancerExternalALB, self).setup()
        self.Condition = 'LoadBalancerApplicationExternal'
        self.SecurityGroups = [
            get_expvalue('SecurityGroupLoadBalancerApplicationExternal')
        ]

class ELBV2LoadBalancerInternalALB(ELBV2LoadBalancerInternal):
    def setup(self):
        super(ELBV2LoadBalancerInternalALB, self).setup()
        self.Condition = 'LoadBalancerApplicationInternal'
        self.SecurityGroups = [
            get_expvalue('SecurityGroupLoadBalancerApplicationInternal')
        ]

# E - V2 LOAD BALANCING #

# #################################
# ### START STACK INFRA CLASSES ###
# #################################

class LB_Listeners(object):
    def __init__(self):
        # Conditions
        do_no_override(True)
        for i in cfg.AllowedIp:
            condname = 'AllowedIp%s' % i  # Ex. AllowedIp1
            cfg.Conditions.append({
                condname: Not(Equals(get_endvalue(condname + 'Enabled'), 'None'))
            })
        do_no_override(False)


class LB_ListenersEC2(LB_Listeners):
    def __init__(self):
        super(LB_ListenersEC2, self).__init__()
        # Resources
        Listeners = []
        Securitygroup_Rules = []
        SecuritygroupIngress_InstanceRules = []
        for n, v in cfg.Listeners.iteritems():
            mapname = 'Listeners%s' % n  # Ex Listeners1

            if cfg.LoadBalancerClassic:
                Listener = ELBListener(mapname)
                Listener.setup(key=v)
                Listeners.append(Listener)

            for i in cfg.AllowedIp:
                ipname = 'AllowedIp%s' % i   # Ex. AllowedIp1
                condnameprivate = 'SecurityGroupRulePrivate' + mapname + ipname  # Ex. SecurityGroupRulePrivateListeners1AllowedIp1
                condnamepublic = 'SecurityGroupRulePublic' + mapname # Ex. SecurityGroupRulePublicListeners1

                # conditions
                do_no_override(True)
                c_ListenerAllowedIpPrivate = {condnameprivate: And(
                    Condition(ipname),
                    Equals(get_endvalue(mapname + 'LoadBalancerAccess'), 'Private')
                )}

                cfg.Conditions.append(c_ListenerAllowedIpPrivate)
                do_no_override(False)

                SGRule = SecurityGroupRuleELBPorts(mapname)
                SGRule.setup()
                SGRule.CidrIp = get_endvalue(ipname + 'Ip')

                Securitygroup_Rules.append(
                    If(
                        condnameprivate,
                        SGRule,
                        Ref('AWS::NoValue'),
                    )
                )

            # conditions
            do_no_override(True)
            c_ListenerPublic = {condnamepublic: Equals(
                get_endvalue(mapname + 'LoadBalancerAccess'), 'Public'
            )}

            cfg.Conditions.append(c_ListenerPublic)
            do_no_override(False)

            SGRule = SecurityGroupRuleELBPorts(mapname)
            SGRule.setup()
            SGRule.CidrIp = '0.0.0.0/0'

            Securitygroup_Rules.append(
                If(
                    condnamepublic,
                    SGRule,
                    Ref('AWS::NoValue'),
                )
            )

            # resources
            r_SGIInstance = SecurityGroupIngressInstanceELBPorts('SecurityGroupIngress' + mapname)
            r_SGIInstance.setup(listener=mapname)

            cfg.Resources.append(r_SGIInstance)

            # outputs
            Listener_Output = Output(mapname)
            Listener_Output.Value = Sub(
                '${LoadBalancerPort}.${Protocol}.${LoadBalancerAccess}',
                **{
                    'LoadBalancerPort': get_endvalue(mapname + 'LoadBalancerPort'),
                    'Protocol': get_endvalue(mapname + 'Protocol'),
                    'LoadBalancerAccess': get_endvalue(mapname + 'LoadBalancerAccess')
                }
            )
            cfg.Outputs.append(Listener_Output)

        R_SG = SecurityGroupLoadBalancer('SecurityGroupLoadBalancer')
        R_SG.setup()
        R_SG.SecurityGroupIngress = Securitygroup_Rules

        cfg.Resources.extend([
            R_SG,
        ])

        # Outputs
        O_SG = Output('SecurityGroupLoadBalancer')
        O_SG.Value = Ref('SecurityGroupLoadBalancer')

        cfg.Outputs.extend([
            O_SG,
        ])

        self.Listeners = Listeners


class LB_ListenerRulesExternalInternal(object):
    def __init__(self, index, key, mapname, scheme):
        # resources
        R_RuleHttp = ELBV2ListernerRuleECS('ListenerHttp' + scheme + 'Rules' + index)  # Ex. ListenerHttpExternalRules1
        R_RuleHttp.setup(key=key, index=index, mapname=mapname, scheme=scheme)
        R_RuleHttp.ListenerArn=get_expvalue('ListenerHttpDefault' + scheme, 'LoadBalancerApplicationStack')
        R_RuleHttp.Condition = 'ListenerLoadBalancerHttpPort'

        R_RuleHttps = ELBV2ListernerRuleECS('ListenerHttps' + scheme + 'Rules' + index)
        R_RuleHttps.setup(key=key, index=index, mapname=mapname, scheme=scheme)
        R_RuleHttps.ListenerArn=get_expvalue('ListenerHttpsDefault' + scheme, 'LoadBalancerApplicationStack')
        R_RuleHttps.Condition = 'ListenerLoadBalancerHttpsPort'

        # Create ListenerRule only in stack's specific new Listener
        ListenerHttpPort = cfg.ListenerLoadBalancerHttpPort
        ListenerHttpsPort = cfg.ListenerLoadBalancerHttpsPort
        Protocol = key['Protocol'] if 'Protocol' in key else ''
        RuleHttpAdd = None
        RuleHttpsAdd = None

        if 'NoDefault' in key:
            R_RuleHttp.ListenerArn = Ref('ListenerHttp' + scheme)
            R_RuleHttps.ListenerArn = Ref('ListenerHttps' + scheme)
            if ListenerHttpPort != 80:
                RuleHttpAdd = True
            if ListenerHttpsPort != 443:
                RuleHttpsAdd = True
        else:
            RuleHttpAdd = True
            RuleHttpsAdd = True

        if Protocol == 'http':
            RuleHttpAdd = True
            RuleHttpsAdd = None
        if Protocol == 'https':
            RuleHttpAdd = None
            RuleHttpsAdd = True

        if RuleHttpAdd:
            cfg.Resources.append(R_RuleHttp)
        if RuleHttpsAdd and scheme == 'External':
            cfg.Resources.append(R_RuleHttps)


class LB_ListenerRules(object):
    def __init__(self):
        for n, v in cfg.ListenerRules.iteritems():
            mapname = 'ListenerRules%s' % n  # Ex. ListenerRules1

            # parameters
            p_Priority = Parameter(mapname + 'Priority')
            p_Priority.Description = 'Listener Rule Priority, lesser value = high priority - empty for default based on env/role'

            cfg.Parameters.append(p_Priority)

            ListenerRule_Out_String = ['Priority=${Priority}']
            ListenerRule_Out_Map = {'Priority': get_endvalue(mapname + 'Priority')}

            if 'HostHeader' in v:
                p_HostHeader = Parameter(mapname + 'HostHeader')
                p_HostHeader.Description = 'Listener Rule HostHeader Condition - empty for default based on env/role'

                cfg.Parameters.append(p_HostHeader)

                # outputs
                ListenerRule_Out_String.append('HostHeader=${HostHeader}')
                ListenerRule_Out_Map.update({
                    'HostHeader': get_endvalue(mapname + 'HostHeader', issub=True)
                })

            if 'PathPattern' in v:
                p_PathPattern = Parameter(mapname + 'PathPattern')
                p_PathPattern.Description = 'Listener Rule PathPattern Condition - empty for default based on env/role'

                cfg.Parameters.append(p_PathPattern)

                # outputs
                ListenerRule_Out_String.append('PathPattern=${PathPattern}')
                ListenerRule_Out_Map.update({
                    'PathPattern': get_endvalue(mapname + 'PathPattern', issub=True)
                })

            # resources
            if cfg.LoadBalancerApplicationExternal:
                LB_ListenerRulesExternalInternal(index=str(n), key=v, mapname=mapname, scheme='External')

            if cfg.LoadBalancerApplicationInternal:
                LB_ListenerRulesExternalInternal(index=str(n), key=v, mapname=mapname, scheme='Internal')

            # outputs
            o_ListenerRule = Output(mapname)
            o_ListenerRule.Value = Sub(','.join(ListenerRule_Out_String), **ListenerRule_Out_Map)

            cfg.Outputs.append(o_ListenerRule)


class LB_ListenersV2ExternalInternal(object):
    def __init__(self, scheme):
        # Conditions
        do_no_override(True)
        C_SGIHttpPublic = {'SecurityGroupIngressPublicLoadBalancerHttp' + scheme: And(
            Condition('ListenerLoadBalancerHttpPort'),
            Condition('LoadBalancerPublic')
        )}

        C_SGIHttpsPublic = {'SecurityGroupIngressPublicLoadBalancerHttps' + scheme: And(
            Condition('ListenerLoadBalancerHttpsPort'),
            Condition('LoadBalancerPublic')
        )}

        cfg.Conditions.extend([
            C_SGIHttpPublic,
            C_SGIHttpsPublic,
        ])
        do_no_override(False)

        # Resources
        R_SGIHttpPublic = SecurityGroupsIngressEcs('SecurityGroupIngressPublicLoadBalancerHttp' + scheme)
        R_SGIHttpPublic.setup(proto='Http', scheme=scheme)
        R_SGIHttpPublic.CidrIp = '0.0.0.0/0'

        R_SGIHttpsPublic = SecurityGroupsIngressEcs('SecurityGroupIngressPublicLoadBalancerHttps' + scheme)
        R_SGIHttpsPublic.setup(proto='Https', scheme=scheme)
        R_SGIHttpsPublic.CidrIp = '0.0.0.0/0'

        cfg.Resources.extend([
            R_SGIHttpPublic,
            R_SGIHttpsPublic,
        ])

        for i in cfg.AllowedIp:
            ipname = 'AllowedIp%s' % i  # Ex. AllowedIp1
            condnamehttpprivate = 'SecurityGroupIngressPrivateLoadBalancerHttp' + scheme + ipname
            condnamehttpsprivate = 'SecurityGroupIngressPrivateLoadBalancerHttps' + scheme + ipname
            
            # conditions
            cfg.Conditions.extend([
                {condnamehttpprivate: And(
                    Condition(ipname),
                    Not(Condition('LoadBalancerPublic')),
                    Condition('ListenerLoadBalancerHttpPort')
                )},
                {condnamehttpsprivate: And(
                    Condition(ipname),
                    Not(Condition('LoadBalancerPublic')),
                    Condition('ListenerLoadBalancerHttpsPort')
                )}
            ])

            # resources
            SGIHttpPrivate = SecurityGroupsIngressEcs(condnamehttpprivate)
            SGIHttpPrivate.setup(proto='Http', scheme=scheme)
            SGIHttpPrivate.CidrIp = get_endvalue(ipname + 'Ip')

            SGIHttpsPrivate = SecurityGroupsIngressEcs(condnamehttpsprivate)
            SGIHttpsPrivate.setup(proto='Https', scheme=scheme)
            SGIHttpsPrivate.CidrIp = get_endvalue(ipname + 'Ip')

            cfg.Resources.extend([
                SGIHttpPrivate,
                SGIHttpsPrivate,
            ])

        if cfg.ListenerLoadBalancerHttpPort != 80:
            R_ListenerHttp = ELBV2ListenerHttp('ListenerHttp' + scheme)  # Ex. ListenerHttpExternal
            R_ListenerHttp.setup(scheme=scheme)
            R_ListenerHttp.LoadBalancerArn = get_expvalue('LoadBalancerApplication' + scheme, 'LoadBalancerApplicationStack')

            cfg.Resources.append(R_ListenerHttp)

        if cfg.ListenerLoadBalancerHttpsPort != 443 and scheme == 'External':
            R_ListenerHttps = ELBV2ListenerHttps('ListenerHttps' + scheme)
            R_ListenerHttps.setup(scheme=scheme)
            R_ListenerHttps.Condition = 'ListenerLoadBalancerHttpsPort'
            R_ListenerHttps.LoadBalancerArn = get_expvalue('LoadBalancerApplication' + scheme, 'LoadBalancerApplicationStack')

            cfg.Resources.append(R_ListenerHttps)


class LB_ListenersV2EC2(LB_ListenersEC2):
    def __init__(self):
        super(LB_ListenersV2EC2, self).__init__()
        # Resources
        if cfg.LoadBalancerApplicationExternal:
            R_ListenerHttpExternal = ELBV2ListenerHttp('ListenerHttpExternal')
            R_ListenerHttpExternal.setup(scheme='External')
            R_ListenerHttpExternal.Condition = 'ListenerLoadBalancerHttpPort'

            R_ListenerHttpsExternal = ELBV2ListenerHttps('ListenerHttpsExternal')
            R_ListenerHttpsExternal.setup(scheme='External')
            R_ListenerHttpsExternal.Condition = 'ListenerLoadBalancerHttpsPort'
       
            cfg.Resources.extend([
                R_ListenerHttpExternal,
                R_ListenerHttpsExternal,
            ])

        if cfg.LoadBalancerApplicationInternal:
            R_ListenerHttpInternal = ELBV2ListenerHttp('ListenerHttpInternal')
            R_ListenerHttpInternal.setup(scheme='Internal')
            R_ListenerHttpInternal.Condition = 'ListenerLoadBalancerHttpPort'

            cfg.Resources.extend([
                R_ListenerHttpInternal,
            ])
        
        LB_TargetGroupsEC2()
 

class LB_ListenersV2ECS(LB_Listeners):
    def __init__(self):
        super(LB_ListenersV2ECS, self).__init__()
        # Conditions
        do_no_override(True)
        C_ELBPublic = {'LoadBalancerPublic': Equals(
            get_endvalue('LoadBalancerAccess'), 'Public'
        )}

        cfg.Conditions.extend([
            C_ELBPublic,
        ])
        do_no_override(False)

        # Resources
        if cfg.LoadBalancerApplicationExternal:
            LB_ListenersV2ExternalInternal(scheme='External')

        if cfg.LoadBalancerApplicationInternal:
            LB_ListenersV2ExternalInternal(scheme='Internal')

        LB_TargetGroupsECS()
        LB_ListenerRules()

        # Outputs
        O_Listener = Output('ListenerLoadBalancer')
        O_Listener.Value = Sub(
            'HttpPort=${HttpPort},HttpsPort=${HttpsPort}',
            **{ 
                'HttpPort': get_endvalue('ListenerLoadBalancerHttpPort'),
                'HttpsPort': get_endvalue('ListenerLoadBalancerHttpsPort'),
            }
        )

        cfg.Outputs.extend([
            O_Listener,
        ])


class LB_ListenersV2ALB(object):
    def __init__(self):
        # Parameters
        P_CertificateArn = Parameter('LoadBalancerSslCertificateArn')
        P_CertificateArn.Description = 'LoadBalancer CertificateArn - empty for default based on env/role'

        cfg.Parameters.extend([
            P_CertificateArn,
        ])

        # Resources
        if cfg.LoadBalancerApplicationExternal:
            # CREATE SPECIFIC CLASS - EXTERNAL INTERNAL AS PARAMETER
            R_ListenerHttp = ELBV2ListenerHttp('ListenerHttpDefaultExternal')
            R_ListenerHttp.setup(scheme='External')
            R_ListenerHttp.DefaultActions[0].TargetGroupArn=Ref('TargetGroupDefaultExternal')
            R_ListenerHttp.Condition = 'LoadBalancerApplicationExternal'

            R_ListenerHttps = ELBV2ListenerHttps('ListenerHttpsDefaultExternal')
            R_ListenerHttps.setup(scheme='External')
            R_ListenerHttps.DefaultActions[0].TargetGroupArn=Ref('TargetGroupDefaultExternal')
            R_ListenerHttps.Certificates[0].CertificateArn = get_endvalue('LoadBalancerSslCertificateArn')
            R_ListenerHttps.Condition = 'LoadBalancerApplicationExternal'

            cfg.Resources.extend([
                R_ListenerHttp,
                R_ListenerHttps,
            ])

            # Outputs
            O_ListenerHttp = Output('ListenerHttpDefaultExternal')
            O_ListenerHttp.Condition = 'LoadBalancerApplicationExternal'
            O_ListenerHttp.Value = Ref('ListenerHttpDefaultExternal')
            O_ListenerHttp.Export = Export(Sub('ListenerHttpDefaultExternal-${AWS::StackName}'))

            O_ListenerHttps = Output('ListenerHttpsDefaultExternal')
            O_ListenerHttps.Condition = 'LoadBalancerApplicationExternal'
            O_ListenerHttps.Value = Ref('ListenerHttpsDefaultExternal')
            O_ListenerHttps.Export = Export(Sub('ListenerHttpsDefaultExternal-${AWS::StackName}'))

            cfg.Outputs.extend([
                O_ListenerHttp,
                O_ListenerHttps,
            ])

        if cfg.LoadBalancerApplicationInternal:
            R_ListenerHttp = ELBV2ListenerHttp('ListenerHttpDefaultInternal')
            R_ListenerHttp.setup(scheme='Internal')
            R_ListenerHttp.DefaultActions[0].TargetGroupArn=Ref('TargetGroupDefaultInternal')
            R_ListenerHttp.Condition = 'LoadBalancerApplicationInternal'

            cfg.Resources.extend([
                R_ListenerHttp,
            ])            
            
            # Outputs
            O_ListenerHttp = Output('ListenerHttpDefaultInternal')
            O_ListenerHttp.Condition = 'LoadBalancerApplicationInternal'
            O_ListenerHttp.Value = Ref('ListenerHttpDefaultInternal')
            O_ListenerHttp.Export = Export(Sub('ListenerHttpDefaultInternal-${AWS::StackName}'))

            cfg.Outputs.extend([
                O_ListenerHttp,
            ])


class LB_TargetGroups(object):
    def __init__(self):
        # Conditions
        do_no_override(True)
        C_TargetGroupCookieSticky = {'TargetGroupCookieSticky': Not(
            Equals(get_endvalue('TargetGroupCookieSticky'), 'None')
        )}

        cfg.Conditions.extend([
            C_TargetGroupCookieSticky
        ])
        do_no_override(False)


class LB_TargetGroupsEC2(LB_TargetGroups):
    def __init__(self):
        super(LB_TargetGroupsEC2, self).__init__()
        # Resources
        if cfg.LoadBalancerApplicationExternal:
            R_TargetGroup = ELBV2TargetGroupEC2('TargetGroupExternal')
            R_TargetGroup.setup()

            cfg.Resources.append(R_TargetGroup)

            cfg.Alarm['TargetEC2External5XX']['Enabled'] = True

        if cfg.LoadBalancerApplicationInternal:
            R_TargetGroup = ELBV2TargetGroupEC2('TargetGroupInternal')
            R_TargetGroup.setup()

            cfg.Resources.append(R_TargetGroup)
            
            cfg.Alarm['TargetEC2Internal5XX']['Enabled'] = True


class LB_TargetGroupsECS(LB_TargetGroups):
    def __init__(self):
        super(LB_TargetGroupsECS, self).__init__()
        # Resources
        if cfg.LoadBalancerApplicationExternal:
            R_TargetGroup = ELBV2TargetGroupECS('TargetGroupExternal')
            R_TargetGroup.setup()

            cfg.Resources.append(R_TargetGroup)

            cfg.Alarm['TargetExternal5XX']['Enabled'] = True

        if cfg.LoadBalancerApplicationInternal:
            R_TargetGroup = ELBV2TargetGroupECS('TargetGroupInternal')
            R_TargetGroup.setup()

            cfg.Resources.append(R_TargetGroup)
            
            cfg.Alarm['TargetInternal5XX']['Enabled'] = True


class LB_TargetGroupsALB(object):
    def __init__(self):
        # Resources
        if cfg.LoadBalancerApplicationExternal:
            R_TargetGroup = ELBV2TargetGroupALB('TargetGroupDefaultExternal')
            R_TargetGroup.Condition = 'LoadBalancerApplicationExternal'
            R_TargetGroup.setup()

            cfg.Resources.append(R_TargetGroup)

        if cfg.LoadBalancerApplicationInternal:
            R_TargetGroup = ELBV2TargetGroupALB('TargetGroupDefaultInternal')
            R_TargetGroup.Condition = 'LoadBalancerApplicationInternal'
            R_TargetGroup.setup()

            cfg.Resources.append(R_TargetGroup)
            

class LB_ElasticLoadBalancing(object):
    def __init__(self):
        # Parameters
        P_Log = Parameter('LoadBalancerLog')
        P_Log.Description = 'Load Balancer EmitInterval - None to disable - empty for default based on env/role'

        cfg.Parameters.extend([
            P_Log,
        ])

        # Conditions
        do_no_override(True)
        C_Log = {'LoadBalancerLog': Or(
            And(
                Condition('LoadBalancerLogOverride'),
                Not(Equals(Ref('LoadBalancerLog'), 'None'))
            ),
            And(
                Not(Condition('LoadBalancerLogOverride')),
                Not(Equals(get_endvalue('LoadBalancerLog'), 'None'))
            )
        )}

        cfg.Conditions.extend([
            C_Log,
        ])
        do_no_override(False)

        # Outputs
        O_Log = Output('LoadBalancerLog')
        O_Log.Value = get_endvalue('LoadBalancerLog')

        cfg.Outputs.extend([
            O_Log,
        ])


class LB_ElasticLoadBalancingApplication(object):
    def __init__(self):
        # Parameters
        P_Http2 = Parameter('LoadBalancerHttp2')
        P_Http2.Description = 'Load Balancer Http2 - empty for default based on env/role'
        P_Http2.AllowedValues = ['', 'true', 'false']

        cfg.Parameters.extend([
            P_Http2,
        ])

        # Conditions
        do_no_override(True)
        C_Http2 = {'LoadBalancerHttp2': Or(
            And(
                Condition('LoadBalancerHttp2Override'),
                Not(Equals(Ref('LoadBalancerHttp2'), 'None'))
            ),
            And(
                Not(Condition('LoadBalancerHttp2Override')),
                Not(Equals(get_endvalue('LoadBalancerHttp2'), 'None'))
            )
        )}

        cfg.Conditions.extend([
            C_Http2,
        ])
        do_no_override(False)


class LB_ElasticLoadBalancingClassicEC2(LB_ListenersEC2):
    def __init__(self):
        super(LB_ElasticLoadBalancingClassicEC2, self).__init__()
        # Conditions
        C_CookieSticky = {'LoadBalancerCookieSticky': Not(
            Equals(get_endvalue('LoadBalancerCookieSticky'), 'None')
        )}

        cfg.Conditions.extend([
            C_CookieSticky,
        ])
        do_no_override(False)

        # Resources
        if cfg.LoadBalancerClassicExternal:
            R_ELBExternal = ELBLoadBalancerExternal('LoadBalancerClassicExternal')
            R_ELBExternal.setup()
            R_ELBExternal.Listeners = self.Listeners

            cfg.Resources.append(R_ELBExternal)
            
            cfg.Alarm['BackendExternal5XX']['Enabled'] = True

        if cfg.LoadBalancerClassicInternal:
            R_ELBInternal = ELBLoadBalancerInternal('LoadBalancerClassicInternal')
            R_ELBInternal.setup()
            R_ELBInternal.Listeners = self.Listeners

            cfg.Resources.append(R_ELBInternal)
            
            cfg.Alarm['BackendInternal5XX']['Enabled'] = True

        # Outputs
        O_HealthCheck = Output('HealthCheck')
        O_HealthCheck.Value = Sub(
            'Type=${Type},Target=${Target},Interval=${Interval},Timeout=${Timeout},Healthy=${Healthy},Unhealthy=${Unhealthy}',
            **{
                'Type': get_endvalue('HealthCheckType'),
                'Target': get_endvalue('HealthCheckTarget') if cfg.HealthCheckTarget != 'None' else '',
                'Interval': get_endvalue('HealthCheckIntervalSeconds'),
                'Timeout': get_endvalue('HealthCheckTimeoutSeconds'),
                'Healthy': get_endvalue('HealthyThresholdCount'),
                'Unhealthy': get_endvalue('UnhealthyThresholdCount'),
            }
        )

        cfg.Outputs.extend([
            O_HealthCheck,
        ])


class LB_ElasticLoadBalancingApplicationEC2(object):
    def __init__(self):
        LB_ElasticLoadBalancingApplication()
        # Resources
        if cfg.LoadBalancerApplicationExternal:
            R_ELBExternal = ELBV2LoadBalancerExternal('LoadBalancerApplicationExternal')
            R_ELBExternal.setup()

            cfg.Resources.extend([
                R_ELBExternal,
            ])
       
        if cfg.LoadBalancerApplicationInternal:
            R_ELBInternal = ELBV2LoadBalancerInternal('LoadBalancerApplicationInternal')
            R_ELBInternal.setup()

            cfg.Resources.extend([
                R_ELBInternal,
            ])
        
        LB_ListenersV2EC2()
            
        # outputs
        O_HealthCheck = Output('HealthCheck')
        O_HealthCheck.Value = Sub(
            'Type=${Type},Path=${Path},Interval=${Interval},Timeout=${Timeout},Healthy=${Healthy},Unhealthy=${Unhealthy}',
            **{
                'Type': get_endvalue('HealthCheckType'),
                'Path': get_endvalue('HealthCheckPath') if cfg.HealthCheckPath != 'None' else '',
                'Interval': get_endvalue('HealthCheckIntervalSeconds'),
                'Timeout': get_endvalue('HealthCheckTimeoutSeconds'),
                'Healthy': get_endvalue('HealthyThresholdCount'),
                'Unhealthy': get_endvalue('UnhealthyThresholdCount'),
            }
        )
            
        cfg.Outputs.extend([
            O_HealthCheck,
        ])



class LB_ElasticLoadBalancingEC2(LB_ElasticLoadBalancing):
    def __init__(self, key):
        super(LB_ElasticLoadBalancingEC2, self).__init__()
        # Resources
        R53_RecordSetEC2LoadBalancer()
        
        if cfg.LoadBalancerClassic:
            LB_ElasticLoadBalancingClassicEC2()

        if cfg.LoadBalancerApplication:
            LB_ElasticLoadBalancingApplicationEC2()


class LB_ElasticLoadBalancingALB(LB_ElasticLoadBalancing):
    def __init__(self, key):
        super(LB_ElasticLoadBalancingALB, self).__init__()
        LB_ElasticLoadBalancingApplication()
        # Parameters
        P_ELBAPP = Parameter('LoadBalancerApplication')
        P_ELBAPP.Description = 'Application Load Balancer to conditionally create - empty for default based on role - need to be already defined'
        P_ELBAPP.AllowedValues=['External', 'Internal', '']

        cfg.Parameters.extend([
            P_ELBAPP,
        ])

        # Conditions
        do_no_override(True)
        C_ELBExternal = {'LoadBalancerApplicationExternal': Or(
            Equals(Ref('LoadBalancerApplication'), 'External'),
            Equals(Ref('LoadBalancerApplication'), ''),
        )}

        C_ELBInternal = {'LoadBalancerApplicationInternal': Or(
            Equals(Ref('LoadBalancerApplication'), 'Internal'),
            Equals(Ref('LoadBalancerApplication'), ''),
        )}

        cfg.Conditions.extend([
            C_ELBExternal,
            C_ELBInternal,
        ])
        do_no_override(False)

        if cfg.LoadBalancerApplicationExternal:
            # Resources
            R_ELB = ELBV2LoadBalancerExternalALB('LoadBalancerApplicationExternal')
            R_ELB.setup()

            cfg.Resources.append(R_ELB)

            # Outputs
            O_ELB = Output('LoadBalancerApplicationExternal')
            O_ELB.Condition = 'LoadBalancerApplicationExternal'
            O_ELB.Value = Ref('LoadBalancerApplicationExternal')
            O_ELB.Export = Export(Sub('LoadBalancerApplicationExternal-${AWS::StackName}'))

            O_ELBDNS = Output('LoadBalancerApplicationExternalDNS')
            O_ELBDNS.Condition = 'LoadBalancerApplicationExternal'
            O_ELBDNS.Value = GetAtt('LoadBalancerApplicationExternal', 'DNSName')
            O_ELBDNS.Export = Export(Sub('LoadBalancerApplicationExternalDNS-${AWS::StackName}'))

            O_ELBFullName = Output('LoadBalancerApplicationExternalFullName')
            O_ELBFullName.Condition = 'LoadBalancerApplicationExternal'
            O_ELBFullName.Value = GetAtt('LoadBalancerApplicationExternal', 'LoadBalancerFullName')
            O_ELBFullName.Export = Export(Sub('LoadBalancerApplicationExternalFullName-${AWS::StackName}'))

            cfg.Outputs.extend([
                O_ELB,
                O_ELBDNS,
                O_ELBFullName,
            ])

        if cfg.LoadBalancerApplicationInternal:
            # Resources
            R_ELB = ELBV2LoadBalancerInternalALB('LoadBalancerApplicationInternal')
            R_ELB.setup()

            cfg.Resources.append(R_ELB)

            # Outputs
            O_ELB = Output('LoadBalancerApplicationInternal')
            O_ELB.Condition = 'LoadBalancerApplicationInternal'
            O_ELB.Value = Ref('LoadBalancerApplicationInternal')
            O_ELB.Export = Export(Sub('LoadBalancerApplicationInternal-${AWS::StackName}'))

            O_ELBDNS = Output('LoadBalancerApplicationInternalDNS')
            O_ELBDNS.Condition = 'LoadBalancerApplicationInternal'
            O_ELBDNS.Value = GetAtt('LoadBalancerApplicationInternal', 'DNSName')
            O_ELBDNS.Export = Export(Sub('LoadBalancerApplicationInternalDNS-${AWS::StackName}'))

            O_ELBFullName = Output('LoadBalancerApplicationInternalFullName')
            O_ELBFullName.Condition = 'LoadBalancerApplicationInternal'
            O_ELBFullName.Value = GetAtt('LoadBalancerApplicationInternal', 'LoadBalancerFullName')
            O_ELBFullName.Export = Export(Sub('LoadBalancerApplicationInternalFullName-${AWS::StackName}'))

            cfg.Outputs.extend([
                O_ELB,
                O_ELBDNS,
                O_ELBFullName,
            ])

        # Resources
        LB_ListenersV2ALB()
        LB_TargetGroupsALB()

        # Outputs
        O_ELB = Output('LoadBalancerApplication')
        O_ELB.Value = get_endvalue('LoadBalancerApplication', nolist=True)

        cfg.Outputs.extend([
            O_ELB,
        ])


class LB_ElasticLoadBalancingECS(object):
    def __init__(self, key):
        # Resources
        LB_ListenersV2ECS()
        R53_RecordSetECSLoadBalancer()

        # Outputs
        O_HealthCheck = Output('HealthCheck')
        O_HealthCheck.Value = Sub(
            'Path=${Path},Interval=${Interval},Timeout=${Timeout},Healthy=${Healthy},Unhealthy=${Unhealthy}',
            **{
                'Path': get_endvalue('HealthCheckPath'),
                'Interval': get_endvalue('HealthCheckIntervalSeconds'),
                'Timeout': get_endvalue('HealthCheckTimeoutSeconds'),
                'Healthy': get_endvalue('HealthyThresholdCount'),
                'Unhealthy': get_endvalue('UnhealthyThresholdCount'),
            }
        )

        O_Access = Output('LoadBalancerAccess')
        O_Access.Value = get_endvalue('LoadBalancerAccess')

        O_Scheme = Output('LoadBalancerApplication')
        O_Scheme.Value = get_endvalue('LoadBalancerApplication', nolist=True)

        cfg.Outputs.extend([
            O_HealthCheck,
            O_Access,
            O_Scheme,
        ])
