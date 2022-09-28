import troposphere.cloudfront as clf

from .common import *
from .shared import (
    Parameter,
    get_endvalue,
    get_expvalue,
    get_subvalue,
    auto_get_props,
    get_condition,
    add_obj,
    change_obj_data,
    clf_compute_order,
)


def process_cache_policy(v):
    # Use CachePolicyId/OriginRequestPolicyId or legacy mode
    if "CachePolicyId" in v:
        for k in ["DefaultTTL", "MaxTTL", "MinTTL", "ForwardedValues"]:
            try:
                del v[k]
            except Exception:
                pass


def cache_behavior_process():
    # process default behavior
    process_cache_policy(
        cfg.CloudFrontDistributionBase["DistributionConfig"]["DefaultCacheBehavior"]
    )
    # process other behaviors
    for n in cfg.CloudFrontCacheBehaviors:
        process_cache_policy(getattr(cfg, f"CloudFrontCacheBehaviors{n}"))


def origin_process():
    for n, v in cfg.CloudFrontOrigins.items():
        resname = f"CloudFrontOrigins{n}"

        if "OriginAccessIdentity" in v.get("S3OriginConfig", []):
            del getattr(cfg, resname)["CustomOriginConfig"]
        else:
            del getattr(cfg, resname)["S3OriginConfig"]


def CF_CloudFront(key):
    for n, v in getattr(cfg, key).items():
        resname = f"{key}{n}"
        # Resources
        R_CloudFrontDistribution = clf.Distribution(resname)

        # process cache_behavior and origin
        cache_behavior_process()
        origin_process()

        # Automatically compute Behaviour Order based on PathPattern
        cfg.dbg_clf_compute_order = {}
        sortedcachebehaviors = sorted(
            cfg.CloudFrontCacheBehaviors.items(),
            key=lambda x_y: clf_compute_order(x_y[1]["PathPattern"]),
        )
        cfg.CloudFrontCacheBehaviors = {x[0]: x[1] for x in sortedcachebehaviors}

        if cfg.debug:
            print("##########CLF_COMPUTE_ORDER#########START#######")
            for n, v in iter(
                sorted(cfg.dbg_clf_compute_order.items(), key=lambda x_y: x_y[1])
            ):
                print(f"{n} {v}\n")
            print("##########CLF_COMPUTE_ORDER#########END#######")

        auto_get_props(R_CloudFrontDistribution)
        add_obj(R_CloudFrontDistribution)
