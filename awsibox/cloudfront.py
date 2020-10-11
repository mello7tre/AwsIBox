import troposphere.cloudfront as clf

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
                     get_subvalue, auto_get_props, get_condition, add_obj,
                     change_obj_data)
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
        auto_get_props(self, key, recurse=True)

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
            self.TargetOriginId = If(
                'CloudFrontOriginAdHoc',
                Ref('RecordSetExternal'),
                Sub(
                    '${EnvRole}${RecordSetCloudFrontSuffix}.origin.%s'
                    % cfg.HostedZoneNameEnv)
            )

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


class CFDistributionConfig(clf.DistributionConfig):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.Enabled = 'True'
        DefaultCacheBehavior = CFDefaultCacheBehavior(
            'CloudFrontCacheBehaviors0', key=cfg.CloudFrontCacheBehaviors[0])
        self.DefaultCacheBehavior = DefaultCacheBehavior
        self.HttpVersion = get_endvalue('CloudFrontHttpVersion')
        self.Logging = If(
            'CloudFrontLogging',
            clf.Logging(
                Bucket=Sub(f'{cfg.BucketLogs}.s3.amazonaws.com'),
                Prefix=Sub('${EnvRole}.${AWS::StackName}/'),
            ),
            Ref('AWS::NoValue')
        )
        self.PriceClass = 'PriceClass_100'
        self.ViewerCertificate = clf.ViewerCertificate()
        self.ViewerCertificate.AcmCertificateArn = If(
            'CloudFrontAcmCertificate',
            get_endvalue('GlobalCertificateArn'),
            Ref('AWS::NoValue')
        )
        self.ViewerCertificate.CloudFrontDefaultCertificate = If(
            'CloudFrontAcmCertificate',
            Ref('AWS::NoValue'),
            'True'
        )
        self.ViewerCertificate.SslSupportMethod = If(
            'CloudFrontAcmCertificate',
            'sni-only',
            Ref('AWS::NoValue')
        )
        self.ViewerCertificate.MinimumProtocolVersion = If(
            'CloudFrontAcmCertificate',
            get_endvalue('CloudFrontMinimumProtocolVersion'),
            Ref('AWS::NoValue')
        )
        self.WebACLId = get_endvalue('CloudFrontWebACLId', condition=True)


class CFCustomOrigin(clf.CustomOriginConfig):
    def __init__(self, title, key, **kwargs):
        super().__init__(title, **kwargs)

        name = self.title

        if 'HTTPSPort' in key:
            self.HTTPSPort = get_endvalue(f'{name}HTTPSPort')
        if 'HTTPSort' in key:
            self.HTTPPort = get_endvalue(f'{name}HTTPPort')

        self.OriginProtocolPolicy = get_endvalue(
                f'{name}ProtocolPolicy')

        if 'SSLProtocols' in key:
            self.OriginSSLProtocols = get_endvalue(
                f'{name}SSLProtocols')
        if 'ReadTimeout' in key:
            self.OriginReadTimeout = get_endvalue(
                f'{name}ReadTimeout')
        if 'KeepaliveTimeout' in key:
            self.OriginKeepaliveTimeout = get_endvalue(
                f'{name}KeepaliveTimeout')


class CFOriginCustomHeader(clf.OriginCustomHeader):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        name = self.title
        self.HeaderName = get_endvalue(f'{name}Name')
        self.HeaderValue = get_endvalue(f'{name}Value')


class CFOriginCLF(clf.Origin):
    def __init__(self, title, index, **kwargs):
        super().__init__(title, **kwargs)

        name = self.title
        key = cfg.CloudFrontOrigins[index]

        CustomHeaders = []
        if 'Headers' in key:
            for n in key['Headers']:
                headername = f'{name}Headers{n}'
                CustomHeader = CFOriginCustomHeader(headername)

                CustomHeaders.append(CustomHeader)

        if key['Type'] == 'custom':
            CustomOrigin = CFCustomOrigin(name, key=key)
            self.CustomOriginConfig = CustomOrigin
        else:
            self.S3OriginConfig = clf.S3OriginConfig()
            if 'OriginAccessIdentity' in key:
                self.S3OriginConfig.OriginAccessIdentity = get_subvalue(
                    'origin-access-identity/cloudfront/${1M}',
                    f'{name}OriginAccessIdentity')

        self.DomainName = get_endvalue(f'{name}DomainName')
        self.OriginPath = get_endvalue(f'{name}Path')
        self.Id = get_endvalue(f'{name}Id')
        self.OriginCustomHeaders = CustomHeaders


class CFOriginEC2ECS(clf.Origin):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        cloudfrontorigincustomheaders = []

        self.DomainName = If(
            'CloudFrontOriginAdHoc',
            Ref('RecordSetExternal'),
            Sub('${EnvRole}${RecordSetCloudFrontSuffix}.origin.%s'
                % cfg.HostedZoneNameEnv)
        )
        self.Id = self.DomainName
        self.OriginPath = get_endvalue('CloudFrontOriginPath')

        try:
            custom_headers = cfg.CloudFrontOriginCustomHeaders
        except Exception:
            pass
        else:
            for n in custom_headers:
                name = f'CloudFrontOriginCustomHeaders{n}'
                cloudfrontorigincustomheaders.append(
                    If(
                        name,
                        clf.OriginCustomHeader(
                            HeaderName=get_endvalue(f'{name}HeaderName'),
                            HeaderValue=get_endvalue(f'{name}HeaderValue')
                        ),
                        Ref('AWS::NoValue')
                    )
                )
                # conditions
                add_obj(
                    get_condition(name, 'not_equals', '', f'{name}HeaderName')
                )

        self.OriginCustomHeaders = cloudfrontorigincustomheaders
        self.CustomOriginConfig = clf.CustomOriginConfig(
            HTTPSPort=If(
                'CloudFrontOriginProtocolHTTPS',
                get_endvalue('ListenerLoadBalancerHttpsPort'),
                Ref('AWS::NoValue')
            ),
            HTTPPort=If(
                'CloudFrontOriginProtocolHTTP',
                get_endvalue('ListenerLoadBalancerHttpPort'),
                Ref('AWS::NoValue')
            ),
            OriginProtocolPolicy=get_endvalue('CloudFrontOriginProtocolPolicy')
        )


class CFOriginAGW(CFOriginEC2ECS):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.DomainName = Sub(
            '${ApiGatewayRestApi}.execute-api.${AWS::Region}.amazonaws.com')
        self.Id = self.DomainName
        self.CustomOriginConfig = clf.CustomOriginConfig(
            HTTPSPort='443',
            OriginProtocolPolicy='https-only',
        )


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

        DistributionConfig = CFDistributionConfig()

        cachebehaviors = []
        sortedcachebehaviors = sorted(
            iter(cfg.CloudFrontCacheBehaviors.items()),
            key=lambda x_y: (
                (x_y[1]['Order']*1000) - len(x_y[1]['PathPattern'])
                if 'PathPattern' in x_y[1] else 0
            ) if 'Order' in x_y[1] else x_y[0]
        )
        itercachebehaviors = iter(sortedcachebehaviors)
        next(itercachebehaviors)
        for n, v in itercachebehaviors:
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

        Origins = []
        try:
            cfg.CloudFrontOrigins
        except Exception:
            pass
        else:
            for n, v in cfg.CloudFrontOrigins.items():
                name = f'CloudFrontOrigins{n}'

                # parameters
                p_Origin = Parameter(f'CloudFrontOrigins{n}DomainName')
                p_Origin.Description = (
                    'Origin - empty for default based on env/role')

                p_OriginHTTPSPort = Parameter(f'CloudFrontOrigins{n}HTTPSPort')
                p_OriginHTTPSPort.Description = (
                    'Origin - empty for default based on env/role')

                if 'OriginAccessIdentity' in v:
                    p_OriginAccessIdentity = Parameter(
                        f'CloudFrontOrigins{n}OriginAccessIdentity')
                    p_OriginAccessIdentity.Description = (
                        'OriginAccessIdentity - '
                        'empty for default based on env/role')

                    add_obj(p_OriginAccessIdentity)

                add_obj([
                    p_Origin,
                    p_OriginHTTPSPort,
                ])

                Origin = CFOriginCLF(name, index=n)
                Origins.append(Origin)

        CloudFrontDistribution.DistributionConfig.Origins = Origins
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

        Origin = CFOriginEC2ECS()
        self.CloudFrontDistribution.DistributionConfig.Origins.append(Origin)
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

        Origin = CFOriginAGW()
        self.CloudFrontDistribution.DistributionConfig.Origins = [Origin]

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
            auto_get_props(r_CachePolicy, v, recurse=True)
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
            auto_get_props(r_OriginRequestPolicy, v, recurse=True)
            r_OriginRequestPolicy.OriginRequestPolicyConfig.Name = n

            # outputs
            o_OriginRequestPolicy = Output(resname)
            o_OriginRequestPolicy.Value = Ref(resname)
            o_OriginRequestPolicy.Export = Export(resname)

            add_obj([
                r_OriginRequestPolicy,
                o_OriginRequestPolicy,
            ])
