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


def cache_behavior_process(key):
    # process default behavior
    process_cache_policy(
        key["DefaultCacheBehavior"]
    )
    # process other behaviors
    for n, v in key["CacheBehaviors"].items():
        process_cache_policy(v)


def origin_process(name, key):
    for n, v in key["Origins"].items():
        resname = f"{name}DistributionConfigOrigins{n}"

        if "OriginAccessIdentity" in v.get("S3OriginConfig", []):
            del v["CustomOriginConfig"]
        else:
            del v["S3OriginConfig"]


def CF_CloudFront(key):
    for n, v in getattr(cfg, key).items():
        if not v.get("IBOX_ENABLED", True):
            continue
        resname = f"{key}{n}"
        # Resources
        R_CloudFrontDistribution = clf.Distribution(resname)
        distribution_config = v["DistributionConfig"]

        # process cache_behavior and origin
        cache_behavior_process(distribution_config)
        origin_process(resname, distribution_config)

        # Automatically compute Behaviour Order based on PathPattern
        cfg.dbg_clf_compute_order = {}
        sortedcachebehaviors = sorted(
            distribution_config["CacheBehaviors"].items(),
            key=lambda x_y: clf_compute_order(x_y[1]["PathPattern"]),
        )
        distribution_config["CacheBehaviors"] = {x[0]: x[1] for x in sortedcachebehaviors}

        if cfg.debug:
            print("##########CLF_COMPUTE_ORDER#########START#######")
            for n, v in iter(
                sorted(cfg.dbg_clf_compute_order.items(), key=lambda x_y: x_y[1])
            ):
                print(f"{n} {v}\n")
            print("##########CLF_COMPUTE_ORDER#########END#######")

        auto_get_props(R_CloudFrontDistribution, mapname=resname)
        add_obj(R_CloudFrontDistribution)
