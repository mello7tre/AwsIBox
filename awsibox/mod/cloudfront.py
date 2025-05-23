from troposphere import cloudfront

from .. import cfg
from ..shared import auto_get_props, add_obj, clf_compute_order


def process_cache_policy(v):
    # Use CachePolicyId/OriginRequestPolicyId or legacy mode
    if "CachePolicyId" in v:
        for k in ["DefaultTTL", "MaxTTL", "MinTTL", "ForwardedValues"]:
            try:
                del v[k]
            except Exception:
                pass


def CF_CloudFront(key):
    for n, v in getattr(cfg, key).items():
        if not v.get("IBOX_ENABLED", True):
            continue
        resname = f"{key}{n}"
        # Resources
        R_CloudFrontDistribution = cloudfront.Distribution(resname)
        distribution_config = v["DistributionConfig"]

        # process cache behaviors
        process_cache_policy(distribution_config["DefaultCacheBehavior"])
        for m, w in distribution_config["CacheBehaviors"].items():
            process_cache_policy(w)

        # process origins
        for m, w in distribution_config["Origins"].items():
            if "VpcOriginId" not in w["VpcOriginConfig"]:
                del w["VpcOriginConfig"]
            if any(n in w for n in ["S3OriginConfig", "VpcOriginConfig"]):
                del w["CustomOriginConfig"]

        # Automatically compute Behaviour Order based on PathPattern
        cfg.dbg_clf_compute_order = {}
        sortedcachebehaviors = sorted(
            distribution_config["CacheBehaviors"].items(),
            key=lambda x_y: clf_compute_order(x_y[1]["PathPattern"]),
        )
        distribution_config["CacheBehaviors"] = {
            x[0]: x[1] for x in sortedcachebehaviors
        }

        if cfg.debug:
            print("##########CLF_COMPUTE_ORDER#########START#######")
            for n, v in iter(
                sorted(cfg.dbg_clf_compute_order.items(), key=lambda x_y: x_y[1])
            ):
                print(f"{n} {v}\n")
            print("##########CLF_COMPUTE_ORDER#########END#######")

        auto_get_props(R_CloudFrontDistribution, mapname=resname)
        add_obj(R_CloudFrontDistribution)
