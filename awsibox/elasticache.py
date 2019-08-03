import troposphere.elasticache as cch

from shared import *


class CCHCacheCluster(cch.CacheCluster):
    def setup(self):
        auto_get_props(self, RP_cmm, mapname='')


class CCHCacheClusterPublic(CCHCacheCluster):
    def setup(self):
        super(CCHCacheClusterPublic, self).setup()
        self.CacheSubnetGroupName = get_exported_value('CacheSubnetGroupPublic')
        self.CacheSecurityGroupNames = [Ref('SecurityGroupCCH')]


class CCHCacheClusterPrivate(CCHCacheCluster):
    def setup(self):
        super(CCHCacheClusterPrivate, self).setup()
        self.CacheSubnetGroupName = get_exported_value('CacheSubnetGroupPrivate')
        self.VpcSecurityGroupIds = [Ref('SecurityGroupCCH')]


class CCHCacheSubnetGroupPrivate(cch.SubnetGroup):
    def setup(self):
        self.Description = Sub('${EnvShort}-Private')
        self.SubnetIds=Split(',', get_exported_value('SubnetsPrivate'))


class CCHCacheSubnetGroupPublic(cch.SubnetGroup):
    def setup(self):
        self.Description = Sub('${EnvShort}-Public')
        self.SubnetIds=Split(',', get_exported_value('SubnetsPublic'))

# #################################
# ### START STACK INFRA CLASSES ###
# #################################

class CCH_Cache(object):
    def __init__(self, key):
        # Resources
        if RP_cmm['CCHScheme'] == 'External':
            R_Cache = CCHCacheClusterPublic('CacheCluster')
        if RP_cmm['CCHScheme'] == 'Internal':
            R_Cache = CCHCacheClusterPrivate('CacheCluster')

        R_Cache.setup()
        R_Cache.Condition = 'CacheEnabled'

        R53_RecordSetCCH()

        cfg.Resources.extend([
            R_Cache,
        ])


class CCH_SubnetGroups(object):
    def __init__(self, key):
        # Resources
        R_Private = CCHCacheSubnetGroupPrivate('CacheSubnetGroupPrivate')
        R_Private.setup()

        R_Public = CCHCacheSubnetGroupPublic('CacheSubnetGroupPublic')
        R_Public.setup()

        cfg.Resources.extend([
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

        cfg.Outputs.extend([
            O_Private,
            O_Public,
        ])

# Need to stay as last lines
import_modules(globals())
