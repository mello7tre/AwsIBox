import troposphere.cloudfront as clf

from .common import *
from .shared import (Parameter, get_endvalue, get_expvalue, get_subvalue,
                     auto_get_props, get_condition, add_obj, change_obj_data,
                     clf_compute_order)


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


def CFCustomErrors():
    CustomErrorResponses = []
    mapname = 'CloudFrontCustomErrorResponses'

    try:
        ErrorResponses = getattr(cfg, mapname)
    except Exception:
        pass
    else:
        for n, v in ErrorResponses.items():
            resname = f'{mapname}{n}'
            CustomErrorResponse = clf.CustomErrorResponse(resname)
            CustomErrorResponses.append(
                auto_get_props(CustomErrorResponse))

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


def CF_CloudFront(key):
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
        name = f'CloudFrontCacheBehaviors{n}'

        cachebehavior = CFCacheBehavior(name, key=v)

        # Create and Use Condition
        # only if PathPattern Value differ between envs
        if f'{name}PathPattern' not in cfg.fixedvalues:
            # conditions
            add_obj(
                get_condition(
                    name, 'not_equals', 'None', f'{name}PathPattern'))

            cachebehaviors.append(
                If(
                    name,
                    cachebehavior,
                    Ref("AWS::NoValue")))
        else:
            cachebehaviors.append(cachebehavior)

    DistributionConfig.CacheBehaviors = cachebehaviors

    cloudfrontaliasextra = []
    for n, v in cfg.CloudFrontAliasExtra.items():
        name = f'CloudFrontAliasExtra{n}'

        # skip parameter and condition for Cdn, Env, Zone
        if v.startswith(cfg.EVAL_FUNCTIONS_IN_CFG):
            cloudfrontaliasextra.append(get_endvalue(name))
            continue

        # parameters
        p_Alias = Parameter(name)
        p_Alias.Description = (
            'Alias extra - ''empty for default based on env/role')

        add_obj(p_Alias)

        cloudfrontaliasextra.append(get_endvalue(name, condition=True))

        # conditions
        add_obj(get_condition(name, 'not_equals', 'None'))

    DistributionConfig.Aliases = cloudfrontaliasextra
    DistributionConfig.CustomErrorResponses = CFCustomErrors()
    CloudFrontDistribution.DistributionConfig = DistributionConfig

    CloudFrontDistribution.DistributionConfig.Origins = CFOrigins()
    CloudFrontDistribution.DistributionConfig.Comment = get_endvalue(
        'CloudFrontComment')

    try:
        cfg.CloudFrontDistributionCondition
    except Exception:
        pass
    else:
        CloudFrontDistribution.Condition = (
            cfg.CloudFrontDistributionCondition)

    R_CloudFrontDistribution = CloudFrontDistribution

    add_obj([
        R_CloudFrontDistribution])


def CF_CachePolicy(key):
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
            o_CachePolicy])


def CF_OriginRequestPolicy(key):
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
            o_OriginRequestPolicy])
