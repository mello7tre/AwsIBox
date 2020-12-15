import troposphere.cloudfront as clf

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
                     get_subvalue, auto_get_props, get_condition, add_obj,
                     change_obj_data, clf_compute_order)
from .route53 import R53_RecordSetCloudFront


class CFOriginAccessIdentity(clf.CloudFrontOriginAccessIdentity):
    def __init__(self, title, comment, **kwargs):
        super().__init__(title, **kwargs)
        self.CloudFrontOriginAccessIdentityConfig = (
            clf.CloudFrontOriginAccessIdentityConfig(Comment=comment))

# ############################################
# ### START STACK META CLASSES AND METHODS ###
# ############################################


class CFDefaultCacheBehavior(clf.DefaultCacheBehavior):
    def __init__(self, title, key, **kwargs):
        super().__init__(title, **kwargs)

        name = self.title
        # Look for default values in awsibox/cfg.py [BASE_CFGS]
        auto_get_props(self)

        # Use CachePolicyId/OriginRequestPolicyId or legacy mode
        if 'CachePolicyId' in key:
            for k in ['DefaultTTL', 'MaxTTL', 'MinTTL', 'ForwardedValues']:
                try:
                    del self.properties[k]
                except Exception:
                    pass

        if 'TargetOriginId' in key:
            self.TargetOriginId = get_endvalue(f'{name}TargetOriginId')
        else:
            self.TargetOriginId = get_endvalue(
                f'CloudFrontCacheBehaviors0TargetOriginId')

        if 'LambdaFunctionARN' in key:
            condname = f'{name}LambdaFunctionARN'
            eventType = 'origin-request'
            if 'LambdaEventType' in key:
                eventType = key['LambdaEventType']
            # conditions
            add_obj(
                get_condition(condname, 'not_equals', 'None')
            )

            self.LambdaFunctionAssociations = [
                If(
                    condname,
                    clf.LambdaFunctionAssociation(
                        EventType=eventType,
                        LambdaFunctionARN=get_endvalue(condname)
                    ),
                    Ref('AWS::NoValue')
                )
            ]


class CFCacheBehavior(clf.CacheBehavior, CFDefaultCacheBehavior):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        name = self.title
        self.PathPattern = get_endvalue(f'{name}PathPattern')


class CFCustomErrorResponse(clf.CustomErrorResponse):
    def __init__(self, title, key, **kwargs):
        super().__init__(title, **kwargs)

        name = self.title  # Ex. CustomErrorResponses1

        self.ErrorCode = get_endvalue(f'{name}ErrorCode')
        self.ErrorCachingMinTTL = get_endvalue(f'{name}ErrorCachingMinTTL')

        if 'ResponsePagePath' in key:
            self.ResponsePagePath = get_endvalue(f'{name}ResponsePagePath')

        if 'ResponseCode' in key:
            self.ResponseCode = get_endvalue(f'{name}ResponseCode')


def CFCustomErrors():
    CustomErrorResponses = []
    mapname = 'CloudFrontCustomErrorResponses'

    try:
        ErrorResponses = getattr(cfg, mapname)
    except Exception:
        pass
    else:
        for n, v in ErrorResponses.items():
            name = f'{mapname}{n}'
            CustomErrorResponse = CFCustomErrorResponse(name, key=v)
            CustomErrorResponses.append(CustomErrorResponse)

    return CustomErrorResponses


def CFOrigins():
    Origins = []
    for n, v in cfg.CloudFrontOrigins.items():
        resname = f'CloudFrontOrigins{n}'

        try:
            S3OriginConfig = v['S3OriginConfig']
        except Exception:
            pass
        else:
            if 'OriginAccessIdentity' in S3OriginConfig:
                try:
                    del getattr(cfg, resname)['CustomOriginConfig']
                except Exception:
                    pass
            else:
                del getattr(cfg, resname)['S3OriginConfig']

        Origins.append(
            auto_get_props(clf.Origin(resname)))

    return Origins


# ##########################################
# ### END STACK META CLASSES AND METHODS ###
# ##########################################


# #################################
# ### START STACK INFRA CLASSES ###
# #################################


# S - CLOUDFRONT #
class CF_CloudFront(object):
    def __init__(self):
        # Resources
        CloudFrontDistribution = clf.Distribution('CloudFrontDistribution')

        DistributionConfig = clf.DistributionConfig(
            'CloudFrontDistributionConfig')
        auto_get_props(DistributionConfig, 'CloudFrontDistributionIBOXBASE')
        DistributionConfig.DefaultCacheBehavior = CFDefaultCacheBehavior(
            'CloudFrontCacheBehaviors0', key=cfg.CloudFrontCacheBehaviors[0])

        cachebehaviors = []
        # Skip DefaultBehaviour
        itercachebehaviors = iter(cfg.CloudFrontCacheBehaviors.items())
        next(itercachebehaviors)

        # Automatically compute Behaviour Order based on PathPattern
        cfg.dbg_clf_compute_order = {}
        sortedcachebehaviors = sorted(
            itercachebehaviors,
            key=lambda x_y: clf_compute_order(x_y[1]['PathPattern']))

        if cfg.debug:
            print('##########CLF_COMPUTE_ORDER#########START#######')
            for n, v in iter(sorted(cfg.dbg_clf_compute_order.items(),
                                    key=lambda x_y: x_y[1])):
                print(f'{n} {v}\n')
            print('##########CLF_COMPUTE_ORDER#########END#######')

        for n, v in sortedcachebehaviors:
            if not v['PathPattern']:
                continue
            name = f'CloudFrontCacheBehaviors{n}'

            cachebehavior = CFCacheBehavior(name, key=v)

            # Create and Use Condition
            # only if PathPattern Value differ between envs
            if f'{name}PathPattern' not in cfg.fixedvalues:
                # conditions
                add_obj(
                    get_condition(
                        name, 'not_equals', 'None', f'{name}PathPattern')
                )

                cachebehaviors.append(
                    If(
                        name,
                        cachebehavior,
                        Ref("AWS::NoValue")
                    )
                )
            else:
                cachebehaviors.append(cachebehavior)

        DistributionConfig.CacheBehaviors = cachebehaviors

        cloudfrontaliasextra = []
        for n in cfg.CloudFrontAliasExtra:
            name = f'CloudFrontAliasExtra{n}'

            # parameters
            p_Alias = Parameter(name)
            p_Alias.Description = (
                'Alias extra - ''empty for default based on env/role')

            add_obj(p_Alias)

            cloudfrontaliasextra.append(get_endvalue(name, condition=True))

            # conditions
            add_obj(get_condition(name, 'not_equals', 'None'))

        DistributionConfig.Aliases = cloudfrontaliasextra
        CloudFrontDistribution.DistributionConfig = DistributionConfig

        CloudFrontDistribution.DistributionConfig.Origins = CFOrigins()
        CloudFrontDistribution.DistributionConfig.Comment = get_endvalue(
            'CloudFrontComment')

        R_CloudFrontDistribution = CloudFrontDistribution

        add_obj([
            R_CloudFrontDistribution,
        ])

        self.CloudFrontDistribution = CloudFrontDistribution


class CF_CloudFrontInOtherService(CF_CloudFront):
    def __init__(self, key):
        super().__init__()

        # Resources
        # Prepend to Aliases list
        self.CloudFrontDistribution.DistributionConfig.Aliases[0:0] = [
            If(
                'RecordSetCloudFront',
                Sub('${EnvRole}${RecordSetCloudFrontSuffix}.cdn.%s'
                    % cfg.HostedZoneNameEnv),
                Ref('RecordSetExternal')
            ),
            Sub('${EnvRole}${RecordSetCloudFrontSuffix}.%s'
                % cfg.HostedZoneNameEnv),
            If(
                'CloudFrontAliasZone',
                Sub('%s.%s' % (
                    get_endvalue('CloudFrontAliasZone'),
                    cfg.HostedZoneNameEnv)),
                Ref('AWS::NoValue')
            ),
        ]

        self.CloudFrontDistribution.Condition = 'CloudFrontDistribution'

        self.CloudFrontDistribution.DistributionConfig.Comment = Sub(
            '${AWS::StackName}-${EnvRole}')

        try:
            cfg.CloudFrontCustomErrorResponses
        except Exception:
            pass
        else:
            (self.CloudFrontDistribution.
                DistributionConfig.CustomErrorResponses) = CFCustomErrors()

        R53_RecordSetCloudFront()


class CF_CloudFrontEC2(CF_CloudFrontInOtherService):
    def __init__(self, key):
        super().__init__(key)


class CF_CloudFrontECS(CF_CloudFrontEC2):
    def __init__(self, key):
        super().__init__(key)


class CF_CloudFrontAGW(CF_CloudFrontInOtherService):
    def __init__(self, key):
        super().__init__(key)

        # To use the same code of ecs ec2 need to add "fake" condition,
        # api-gateway use https only

        # Conditions
        add_obj([
            {'ListenerLoadBalancerHttpPort': Equals('True', 'False')},
            {'ListenerLoadBalancerHttpsPort': Equals('True', 'True')},
        ])

        # RecordSetExternal do not exist replace it with Ref('AWS::NoValue')
        change_obj_data(
            self.CloudFrontDistribution.DistributionConfig.Aliases,
            'RecordSetExternal',
            Ref('AWS::NoValue')
        )


class CF_CloudFrontCLF(CF_CloudFront):
    def __init__(self, key):
        super(CF_CloudFrontCLF, self).__init__()

        (self.CloudFrontDistribution.
            DistributionConfig.CustomErrorResponses) = CFCustomErrors()


class CF_CachePolicy(object):
    def __init__(self, key):
        # Resources
        for n, v in getattr(cfg, key).items():
            resname = f'{key}{n}'

            # resources
            r_CachePolicy = clf.CachePolicy(resname)
            auto_get_props(r_CachePolicy)
            r_CachePolicy.CachePolicyConfig.Name = n

            # outputs
            o_CachePolicy = Output(resname)
            o_CachePolicy.Value = Ref(resname)
            o_CachePolicy.Export = Export(resname)

            add_obj([
                r_CachePolicy,
                o_CachePolicy,
            ])


class CF_OriginRequestPolicy(object):
    def __init__(self, key):
        # Resources
        for n, v in getattr(cfg, key).items():
            resname = f'{key}{n}'

            # resources
            r_OriginRequestPolicy = clf.OriginRequestPolicy(resname)
            auto_get_props(r_OriginRequestPolicy)
            r_OriginRequestPolicy.OriginRequestPolicyConfig.Name = n

            # outputs
            o_OriginRequestPolicy = Output(resname)
            o_OriginRequestPolicy.Value = Ref(resname)
            o_OriginRequestPolicy.Export = Export(resname)

            add_obj([
                r_OriginRequestPolicy,
                o_OriginRequestPolicy,
            ])
