import troposphere.elasticache as cch

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
                     get_subvalue, auto_get_props, get_condition, add_obj)
from .route53 import R53_RecordSetCCH


class CCHCacheCluster(cch.CacheCluster):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        auto_get_props(self, mapname='')


class CCHReplicationGroup(cch.ReplicationGroup):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        auto_get_props(self, mapname='')


class CCHReplicationGroupPublic(CCHReplicationGroup):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.CacheSubnetGroupName = get_expvalue('CacheSubnetGroupPublic')
        self.CacheSecurityGroupNames = [Ref('SecurityGroupCCH')]


class CCHReplicationGroupPrivate(CCHReplicationGroup):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.CacheSubnetGroupName = get_expvalue('CacheSubnetGroupPrivate')
        self.SecurityGroupIds = [Ref('SecurityGroupCCH')]


class CCHCacheClusterPublic(CCHCacheCluster):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.CacheSubnetGroupName = get_expvalue('CacheSubnetGroupPublic')
        self.CacheSecurityGroupNames = [Ref('SecurityGroupCCH')]


class CCHCacheClusterPrivate(CCHCacheCluster):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.CacheSubnetGroupName = get_expvalue('CacheSubnetGroupPrivate')
        self.VpcSecurityGroupIds = [Ref('SecurityGroupCCH')]


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

# #################################
# ### START STACK INFRA CLASSES ###
# #################################


class CCH_Cache(object):
    def __init__(self, key):
        # Resources
        if cfg.CCHScheme == 'External':
            R_Cache = CCHCacheClusterPublic('ElastiCacheCacheCluster')
            R_Group = CCHReplicationGroupPublic('ElastiCacheReplicationGroup')
        if cfg.CCHScheme == 'Internal':
            R_Cache = CCHCacheClusterPrivate('ElastiCacheCacheCluster')
            R_Group = CCHReplicationGroupPrivate('ElastiCacheReplicationGroup')

        R_Cache.Condition = 'CacheCluster'
        R_Group.Condition = 'ReplicationGroup'

        R53_RecordSetCCH()

        add_obj([
            R_Cache,
            R_Group,
        ])


class CCH_SubnetGroups(object):
    def __init__(self, key):
        # Resources
        R_Private = CCHCacheSubnetGroupPrivate('CacheSubnetGroupPrivate')

        R_Public = CCHCacheSubnetGroupPublic('CacheSubnetGroupPublic')

        add_obj([
            R_Private,
            R_Public,
        ])

        # Outputs
        O_Private = Output('CacheSubnetGroupPrivate')
        O_Private.Value = Ref('CacheSubnetGroupPrivate')
        O_Private.Export = Export('CacheSubnetGroupPrivate')

        O_Public = Output('CacheSubnetGroupPublic')
        O_Public.Value = Ref('CacheSubnetGroupPublic')
        O_Public.Export = Export('CacheSubnetGroupPublic')

        add_obj([
            O_Private,
            O_Public,
        ])
