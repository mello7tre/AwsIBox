import troposphere.cloudfront as clf

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
    get_subvalue, auto_get_props, get_condition)
from .route53 import R53_RecordSetCloudFront


class CFOriginAccessIdentity(clf.CloudFrontOriginAccessIdentity):
    def setup(self, comment):
        self.CloudFrontOriginAccessIdentityConfig = clf.CloudFrontOriginAccessIdentityConfig(
            Comment=comment,
        )

# ############################################
# ### START STACK META CLASSES AND METHODS ###
# ############################################

# S - CLOUDFRONT #
class CFDefaultCacheBehavior(clf.DefaultCacheBehavior):
    def setup(self, key):
        name = self.title
        if 'AllowedMethods' in key:
            self.AllowedMethods = get_endvalue(name + 'AllowedMethods')

        if 'CachedMethods' in key:
            self.CachedMethods = get_endvalue(name + 'CachedMethods')

        # If not defined default to True
        if 'Compress' in key:
            self.Compress = get_endvalue(name + 'Compress')
        else:
            self.Compress = True

        if 'DefaultTTL' in key:
            self.DefaultTTL = get_endvalue(name + 'DefaultTTL')

        self.ForwardedValues = clf.ForwardedValues()
        # If not defined default to True
        if 'QueryString' in key:
            self.ForwardedValues.QueryString=get_endvalue(name + 'QueryString')
        else:
            self.ForwardedValues.QueryString=True

        if 'CookiesForward' in key:
            self.ForwardedValues.Cookies = clf.Cookies(
                Forward=get_endvalue(name + 'CookiesForward')
            )
            if 'CookiesWhitelistedNames' in key:
                self.ForwardedValues.Cookies.WhitelistedNames = get_endvalue(name + 'CookiesWhitelistedNames', condition=True)
                # conditions
                do_no_override(True)
                cfg.Conditions.append({
                    name + 'CookiesWhitelistedNames': Equals(get_endvalue(name + 'CookiesForward'), 'whitelist')
                })
                do_no_override(False)

        # If not defined default to 'Host'
        if 'Headers' in key:
            self.ForwardedValues.Headers = get_endvalue(name + 'Headers')
        else:
            self.ForwardedValues.Headers = ['Host']

        if 'QueryStringCacheKeys' in key:
            self.ForwardedValues.QueryStringCacheKeys = get_endvalue(name + 'QueryStringCacheKeys', condition=True)
            # conditions
            do_no_override(True)
            cfg.Conditions.append({
                name + 'QueryStringCacheKeys': Equals(get_endvalue(name + 'QueryString'), True)
            })
            do_no_override(False)

        if 'TargetOriginId' in key:
            self.TargetOriginId = get_endvalue(name + 'TargetOriginId')
        else:
            self.TargetOriginId = If(
                'CloudFrontOriginAdHoc',
                Ref('RecordSetExternal'),
                Sub('${EnvRole}${RecordSetCloudFrontSuffix}.origin.' + cfg.HostedZoneNameEnv)
            )

        if 'MaxTTL' in key:
            self.MaxTTL = get_endvalue(name + 'MaxTTL')

        if 'MinTTL' in key:
            self.MinTTL = get_endvalue(name + 'MinTTL')

        if 'LambdaFunctionARN' in key:
            condname = name + 'LambdaFunctionARN'
            eventType = 'origin-request'
            if 'LambdaEventType' in key:
                eventType = key['LambdaEventType']
            # conditions
            do_no_override(True)
            cfg.Conditions.append({
                condname: Not(Equals(get_endvalue(condname), 'None'))
            })
            do_no_override(False)
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

        if 'ViewerProtocolPolicy' in key:
            self.ViewerProtocolPolicy = get_endvalue(name + 'ViewerProtocolPolicy')


class CFCacheBehavior(clf.CacheBehavior, CFDefaultCacheBehavior):
    def setup(self, **kwargs):
        super(CFCacheBehavior, self).setup(**kwargs)
        name = self.title
        self.PathPattern = get_endvalue(name + 'PathPattern')


class CFDistributionConfig(clf.DistributionConfig):
    def setup(self):
        self.Enabled = 'True'
        DefaultCacheBehavior = CFDefaultCacheBehavior('CloudFrontCacheBehaviors0')
        DefaultCacheBehavior.setup(key=cfg.CloudFrontCacheBehaviors[0])
        self.DefaultCacheBehavior = DefaultCacheBehavior
        self.HttpVersion = get_endvalue('CloudFrontHttpVersion')
        self.Logging = If(
            'CloudFrontLogging',
            clf.Logging(
                Bucket=Sub(cfg.BucketLogs + '.s3.amazonaws.com'),
                Prefix=Sub('${EnvRole}.${AWS::StackName}/'),
            ),
            Ref('AWS::NoValue')
        )
        self.PriceClass = 'PriceClass_100'
        self.ViewerCertificate = clf.ViewerCertificate(
            AcmCertificateArn=If(
                'CloudFrontAcmCertificate',
                get_endvalue('CloudFrontAcmCertificateArn'),
                Ref('AWS::NoValue')
            ),
            CloudFrontDefaultCertificate=If(
                'CloudFrontAcmCertificate',
                Ref('AWS::NoValue'),
                'True'
            ),
            SslSupportMethod=If(
                'CloudFrontAcmCertificate',
                'sni-only',
                Ref('AWS::NoValue')
            )
        )
        self.WebACLId = get_endvalue('CloudFrontWebACLId', condition=True)


class CFCustomOrigin(clf.CustomOriginConfig):
    def setup(self, key):
        name = self.title
        if 'HTTPSPort' in key:
            self.HTTPSPort = get_endvalue(name + 'HTTPSPort')
        if 'HTTPSort' in key:
            self.HTTPPort = get_endvalue(name + 'HTTPPort')
        self.OriginProtocolPolicy = get_endvalue(name + 'ProtocolPolicy')
        if 'SSLProtocols' in key:
            self.OriginSSLProtocols = get_endvalue(name + 'SSLProtocols')
        if 'ReadTimeout' in key:
            self.OriginReadTimeout = get_endvalue(name + 'ReadTimeout')
        if 'KeepaliveTimeout' in key:
            self.OriginKeepaliveTimeout = get_endvalue(name + 'KeepaliveTimeout')


class CFOriginCustomHeader(clf.OriginCustomHeader):
    def setup(self):
        name = self.title
        self.HeaderName = get_endvalue(name + 'Name')
        self.HeaderValue = get_endvalue(name + 'Value')


class CFOriginCLF(clf.Origin):
    def setup(self, index):
        name = self.title
        key = cfg.CloudFrontOrigins[index]

        CustomHeaders = []
        if 'Headers' in key:
            for n in key['Headers']:
                headername = '%sHeaders%s' % (name, n)
                CustomHeader = CFOriginCustomHeader(headername)
                CustomHeader.setup()

                CustomHeaders.append(CustomHeader)

        if key['Type'] == 'custom':
            CustomOrigin = CFCustomOrigin(name)
            CustomOrigin.setup(key=key)
            self.CustomOriginConfig = CustomOrigin
        else:
            self.S3OriginConfig = clf.S3OriginConfig()
            if 'OriginAccessIdentity' in key:
                self.S3OriginConfig.OriginAccessIdentity = get_subvalue('origin-access-identity/cloudfront/${1M}', name + 'OriginAccessIdentity')

        self.DomainName = get_endvalue(name + 'DomainName')
        self.OriginPath = get_endvalue(name + 'Path')
        self.Id = get_endvalue(name + 'Id')
        self.OriginCustomHeaders = CustomHeaders


class CFOriginFixed(clf.Origin):
    def setup(self):
        cloudfrontorigincustomheaders = []

        self.DomainName = If(
            'CloudFrontOriginAdHoc',
            Ref('RecordSetExternal'),
            Sub('${EnvRole}${RecordSetCloudFrontSuffix}.origin.' + cfg.HostedZoneNameEnv)
        )
        self.Id = self.DomainName
        self.OriginPath = get_endvalue('CloudFrontOriginPath')

        try: custom_headers = cfg.CloudFrontOriginCustomHeaders
        except:
            pass
        else:
            for n in custom_headers:
                name = 'CloudFrontOriginCustomHeaders%s' % n
                cloudfrontorigincustomheaders.append(
                    If(
                        name,
                        clf.OriginCustomHeader(
                            HeaderName=get_endvalue(name + 'HeaderName'),
                            HeaderValue=get_endvalue(name + 'HeaderValue')
                        ),
                        Ref("AWS::NoValue")
                    )
                )
                # conditions
                do_no_override(True)
                cfg.Conditions.append({
                    name: Not(Equals(get_endvalue(name + 'HeaderName'), ''))
                })
                do_no_override(False)

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


class CFCustomErrorResponse(clf.CustomErrorResponse):
    def setup(self, key):
        name = self.title  # Ex. CustomErrorResponses1

        self.ErrorCode = get_endvalue(name + 'ErrorCode')
        self.ErrorCachingMinTTL = get_endvalue(name + 'ErrorCachingMinTTL')

        if 'ResponsePagePath' in key:
            self.ResponsePagePath = get_endvalue(name + 'ResponsePagePath')

        if 'ResponseCode' in key:
            self.ResponseCode = get_endvalue(name + 'ResponseCode')
# E - CLOUDFRONT #


# ##########################################
# ### END STACK META CLASSES AND METHODS ###
# ##########################################


# #################################
# ### START STACK INFRA CLASSES ###
# #################################

# S - CLOUDFRONT #
class CF_CloudFront(object):
    def __init__(self):
        # Parameters
        P_Logging = Parameter('CloudFrontLogging')
        P_Logging.Description = 'CloudFront Logging - None to disable - empty for default based on env/role'

        cfg.Parameters.extend([
            P_Logging,
        ])

        # Conditions
        do_no_override(True)
        C_Logging = get_condition('CloudFrontLogging', 'not_equals', 'None')

        C_AcmCertificate = {'CloudFrontAcmCertificate': Not(
            Equals(get_endvalue('CloudFrontAcmCertificate'), 'None')
        )}

        cfg.Conditions.extend([
            C_Logging,
            C_AcmCertificate,
        ])
        do_no_override(False)

        # Resources
        CloudFrontDistribution = clf.Distribution('CloudFrontDistribution')

        DistributionConfig = CFDistributionConfig()
        DistributionConfig.setup()

        cachebehaviors = []
        sortedcachebehaviors = sorted(
            cfg.CloudFrontCacheBehaviors.iteritems(),
            key=lambda (x, y): (
                (y['Order']*1000) - len(y['PathPattern']) if 'PathPattern' in y else 0
            ) if 'Order' in y else x
        )
        itercachebehaviors = iter(sortedcachebehaviors)
        itercachebehaviors.next()
        for n, v in itercachebehaviors:
            if not v['PathPattern']:
                continue
            name = 'CloudFrontCacheBehaviors%s' % n

            cachebehavior = CFCacheBehavior(name)
            cachebehavior.setup(key=v)

            # Create and Use Condition only if PathPattern Value differ between envs
            if name + 'PathPattern' not in cfg.fixedvalues:
                # conditions
                do_no_override(True)
                c_CacheBehavior = {name: Not(
                    Equals(get_endvalue(name + 'PathPattern'), 'None')
                )}

                cfg.Conditions.append(c_CacheBehavior)
                do_no_override(False)

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
            name = 'CloudFrontAliasExtra%s' % n

            # parameters
            p_Alias = Parameter(name)
            p_Alias.Description = 'Alias extra - empty for default based on env/role'

            cfg.Parameters.append(p_Alias)
            
            cloudfrontaliasextra.append(get_endvalue(name, condition=True))

            # conditions
            do_no_override(True)
            c_Alias = {name: Or(
                And(
                    Condition(name + 'Override'),
                    Not(Equals(Ref(name), 'None'))
                ),
                And(
                    Not(Condition(name + 'Override')),
                    Not(Equals(get_endvalue(name), 'None'))
                )
            )}

            cfg.Conditions.append(c_Alias)
            do_no_override(False)

        CloudFrontDistribution.DistributionConfig = DistributionConfig
        CloudFrontDistribution.DistributionConfig.Aliases = cloudfrontaliasextra

        self.CloudFrontDistribution = CloudFrontDistribution


class CF_CloudFrontEC2(CF_CloudFront):
    def __init__(self, key):
        super(CF_CloudFrontEC2, self).__init__()

        # Parameters
        P_CloudFront = Parameter('CloudFront')
        P_CloudFront.Description = 'Create CloudFront Distribution - empty for default based on env/role'
        P_CloudFront.AllowedValues = ['', 'None', 'True']

        P_RecordSetCloudFrontSuffix = Parameter('RecordSetCloudFrontSuffix')
        P_RecordSetCloudFrontSuffix.Description = 'RecordSetCloudFront DNS Name Suffix - empty to disable'

        cfg.Parameters.extend([
            P_CloudFront,
            P_RecordSetCloudFrontSuffix,
        ])

        # Conditions
        do_no_override(True)
        C_AliasZone = {'CloudFrontAliasZone': Not(
            Equals(get_endvalue('CloudFrontAliasZone'), 'None')
        )}

        C_Distribution = {'CloudFrontDistribution': Or(
            And(
                Condition('CloudFrontOverride'),
                Not(Equals(Ref('CloudFront'), 'None'))
            ),
            And(
                Not(Condition('CloudFrontOverride')),
                Not(Equals(get_endvalue('CloudFront'), 'None'))
            )
        )}

        C_OriginAdHoc = {'CloudFrontOriginAdHoc': Equals(
            get_endvalue('CloudFrontOriginAdHoc'), True
        )}

        C_OriginProtocolHTTP = {'CloudFrontOriginProtocolHTTP': And(
            Condition('ListenerLoadBalancerHttpPort'),
            Not(Equals(get_endvalue('CloudFrontOriginProtocolPolicy'), 'https-only'))
        )}

        C_OriginProtocolHTTPS = {'CloudFrontOriginProtocolHTTPS': And(
            Condition('ListenerLoadBalancerHttpsPort'),
            Not(Equals(get_endvalue('CloudFrontOriginProtocolPolicy'), 'http-only'))
        )}

        cfg.Conditions.extend([
            C_AliasZone,
            C_Distribution,
            C_OriginAdHoc,
            C_OriginProtocolHTTP,
            C_OriginProtocolHTTPS,
        ])
        do_no_override(False)

        # Resources
        self.CloudFrontDistribution.DistributionConfig.Aliases[0:0] = [
            If(
                'RecordSetCloudFront',
                Sub('${EnvRole}${RecordSetCloudFrontSuffix}.cdn.' + cfg.HostedZoneNameEnv),
                Ref('RecordSetExternal')
            ),
            Sub('${EnvRole}${RecordSetCloudFrontSuffix}.' + cfg.HostedZoneNameEnv),
            If(
                'CloudFrontAliasZone',
                Sub('%s.%s' % (get_endvalue('CloudFrontAliasZone'), cfg.HostedZoneNameEnv)),
                Ref('AWS::NoValue')
            )
        ]

        self.CloudFrontDistribution.Condition = 'CloudFrontDistribution'

        Origin = CFOriginFixed()
        Origin.setup()
        self.CloudFrontDistribution.DistributionConfig.Origins = [Origin]
        self.CloudFrontDistribution.DistributionConfig.Comment = Sub('${AWS::StackName}-${EnvRole}')

        R_CloudFrontDistribution = self.CloudFrontDistribution

        cfg.Resources.extend([
            R_CloudFrontDistribution,
        ])

        R53_RecordSetCloudFront()

        # Outputs
        O_CloudFront = Output('CloudFront')
        O_CloudFront.Value = get_endvalue('CloudFront')

        cfg.Outputs.extend([
            O_CloudFront,
        ])


class CF_CloudFrontECS(CF_CloudFrontEC2):
    def __init__(self, key):
        super(CF_CloudFrontECS, self).__init__(key)


class CF_CloudFrontCLF(CF_CloudFront):
    def __init__(self, key):
        super(CF_CloudFrontCLF, self).__init__()

        Origins = []
        for n, v in cfg.CloudFrontOrigins.iteritems():
            name = 'CloudFrontOrigins%s' % n
            
            # parameters
            p_Origin = Parameter('CloudFrontOrigins' + n + 'DomainName')
            p_Origin.Description = 'Origin - empty for default based on env/role'

            p_OriginHTTPSPort = Parameter('CloudFrontOrigins' + n + 'HTTPSPort')
            p_OriginHTTPSPort.Description = 'Origin - empty for default based on env/role'

            cfg.Parameters.extend([
                p_Origin,
                p_OriginHTTPSPort,
            ])

            Origin = CFOriginCLF(name)
            Origin.setup(index=n)
            Origins.append(Origin)

        CustomErrorResponses = []
        if hasattr(cfg.CustomErrorResponses, 'iteritems'):
            for n, v in cfg.CustomErrorResponses.iteritems():
                name = 'CustomErrorResponses%s' % n
                CustomErrorResponse = CFCustomErrorResponse(name)
                CustomErrorResponse.setup(key=v)
                CustomErrorResponses.append(CustomErrorResponse)

        self.CloudFrontDistribution.DistributionConfig.Origins = Origins
        self.CloudFrontDistribution.DistributionConfig.CustomErrorResponses = CustomErrorResponses
        self.CloudFrontDistribution.DistributionConfig.Comment = get_endvalue('CloudFrontComment')

        R_CloudFrontDistribution = self.CloudFrontDistribution

        cfg.Resources.extend([
            R_CloudFrontDistribution,
        ])
