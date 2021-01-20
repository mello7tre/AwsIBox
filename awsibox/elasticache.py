import troposphere.elasticache as cch

from .common import *
from .shared import (Parameter, get_endvalue, get_expvalue, get_subvalue,
                     auto_get_props, get_condition, add_obj)
from .route53 import R53_RecordSetCCH


class CCHCacheSubnetGroupPrivate(cch.SubnetGroup):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.Description = Sub('${EnvShort}-Private')
        self.SubnetIds = Split(',', get_expvalue('SubnetsPrivate'))


class CCHCacheSubnetGroupPublic(cch.SubnetGroup):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.Description = Sub('${EnvShort}-Public')
        self.SubnetIds = Split(',', get_expvalue('SubnetsPublic'))


def CCH_Cache(key):
    # Resources
    R_Cache = cch.CacheCluster('ElastiCacheCacheCluster')
    R_Group = cch.ReplicationGroup('ElastiCacheReplicationGroup')

    auto_get_props(R_Cache, f'{key}Base')

    auto_get_props(R_Group, f'{key}Base')
    auto_get_props(R_Group, 'ReplicationGroupBase')

    R53_RecordSetCCH()

    add_obj([
        R_Cache,
        R_Group])


def CCH_SubnetGroups(key):
    # Resources
    R_Private = CCHCacheSubnetGroupPrivate('CacheSubnetGroupPrivate')

    R_Public = CCHCacheSubnetGroupPublic('CacheSubnetGroupPublic')

    # Outputs
    O_Private = Output('CacheSubnetGroupPrivate')
    O_Private.Value = Ref('CacheSubnetGroupPrivate')
    O_Private.Export = Export('CacheSubnetGroupPrivate')

    O_Public = Output('CacheSubnetGroupPublic')
    O_Public.Value = Ref('CacheSubnetGroupPublic')
    O_Public.Export = Export('CacheSubnetGroupPublic')

    add_obj([
        R_Private,
        R_Public,
        O_Private,
        O_Public])
