import troposphere.elasticache as cch

from .common import *
from .shared import (
    Parameter,
    get_endvalue,
    get_expvalue,
    get_subvalue,
    auto_get_props,
    get_condition,
    add_obj,
)


def CCH_Cache(key):
    # Resources
    R_Cache = cch.CacheCluster("ElastiCacheCacheCluster")
    R_Group = cch.ReplicationGroup("ElastiCacheReplicationGroup")

    auto_get_props(R_Cache, f"{key}Base")

    auto_get_props(R_Group, f"{key}Base")
    auto_get_props(R_Group, "ReplicationGroupBase")

    add_obj([R_Cache, R_Group])
