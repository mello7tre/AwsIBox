import troposphere.rds as rds

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
                     get_subvalue, auto_get_props, get_condition, add_obj)
from .route53 import R53_RecordSetRDS


class RDSDBInstance(rds.DBInstance):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        self.AllocatedStorage = get_endvalue('AllocatedStorage')
        self.AllowMajorVersionUpgrade = 'True'
        self.DBInstanceClass = get_endvalue('DBInstanceClass')
        self.DBName = get_endvalue(
            'DBName', nocondition='DBInstanceSkipProperties')
        self.Engine = get_endvalue('Engine')
        self.EngineVersion = get_endvalue('EngineVersion')
        self.MasterUsername = get_endvalue(
            'MasterUsername', nocondition='DBInstanceSkipProperties')
        self.MasterUserPassword = get_endvalue(
            'MasterUserPassword', nocondition='DBInstanceSkipProperties')
        self.MultiAZ = get_endvalue('MultiAZ')
        self.DBParameterGroupName = Ref('DBParameterGroup1')
        self.SourceDBInstanceIdentifier = get_endvalue(
            'SourceDBInstanceIdentifier', condition=True)
        self.StorageType = get_endvalue('StorageType')
        self.VPCSecurityGroups = [Ref('SecurityGroupRDS')]

    def validate(self):
        if 'DBSnapshotIdentifier' not in self.properties:
            if 'Engine' not in self.properties:
                raise ValueError(
                    'Resource Engine is required in type %s'
                    % self.resource_type)

#       if 'SourceDBInstanceIdentifier' in self.properties:
#
#           invalid_replica_properties = (
#               'BackupRetentionPeriod', 'DBName', 'MasterUsername',
#               'MasterUserPassword', 'PreferredBackupWindow', 'MultiAZ',
#               'DBSnapshotIdentifier',
#           )
#
#           invalid_properties = [s for s in self.properties.keys() if
#                                 s in invalid_replica_properties]
#
#           if invalid_properties:
#                raise ValueError(
#                   ('{0} properties can\'t be provided when '
#                    'SourceDBInstanceIdentifier is present '
#                    'AWS::RDS::DBInstance.'
#                    ).format(', '.join(sorted(invalid_properties))))

        if ('DBSnapshotIdentifier' not in self.properties and
            'SourceDBInstanceIdentifier' not in self.properties) and \
            ('MasterUsername' not in self.properties or
                'MasterUserPassword' not in self.properties) and \
                ('DBClusterIdentifier' not in self.properties):
            raise ValueError(
                'Either (MasterUsername and MasterUserPassword) or'
                ' DBSnapshotIdentifier are required in type '
                'AWS::RDS::DBInstance.'
            )

        if 'KmsKeyId' in self.properties and \
           'StorageEncrypted' not in self.properties:
            raise ValueError(
                'If KmsKeyId is provided, StorageEncrypted is required '
                'AWS::RDS::DBInstance.'
            )

        nonetype = type(None)
        avail_zone = self.properties.get('AvailabilityZone', None)
        multi_az = self.properties.get('MultiAZ', None)
        if not (isinstance(avail_zone, (AWSHelperFn, nonetype)) and
                isinstance(multi_az, (AWSHelperFn, nonetype))):
            if avail_zone and multi_az in [True, 1, '1', 'true', 'True']:
                raise ValueError("AvailabiltyZone cannot be set on "
                                 "DBInstance if MultiAZ is set to true.")

        storage_type = self.properties.get('StorageType', None)
        if storage_type and storage_type == 'io1' and \
                'Iops' not in self.properties:
            raise ValueError("Must specify Iops if using StorageType io1")

        allocated_storage = self.properties.get('AllocatedStorage')
        iops = self.properties.get('Iops', None)
        if iops and not isinstance(iops, AWSHelperFn):
            if not isinstance(allocated_storage, AWSHelperFn) and \
                    allocated_storage < 100:
                raise ValueError("AllocatedStorage must be at least 100 when "
                                 "Iops is set.")
            if not isinstance(allocated_storage, AWSHelperFn) and not \
                    isinstance(iops, AWSHelperFn) and \
                    float(iops) / float(allocated_storage) > 10.0:
                raise ValueError("AllocatedStorage must be no less than "
                                 "1/10th the provisioned Iops")

        return True


class RDSDBInstancePublic(RDSDBInstance):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        self.DBSubnetGroupName = get_expvalue('DBSubnetGroupPublic')
        self.PubliclyAccessible = 'True'


class RDSDBInstancePrivate(RDSDBInstance):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        self.DBSubnetGroupName = get_expvalue('DBSubnetGroupPrivate')
        self.PubliclyAccessible = 'False'


class RDSDBParameterGroup(rds.DBParameterGroup):
    def setup(self):
        self.Description = Sub('MYSQL %s - ${AWS::StackName}' % self.title)
        self.Family = get_subvalue('mysql${1M}', 'EngineVersion')


class RDSDBSubnetGroupPrivate(rds.DBSubnetGroup):
    def setup(self):
        self.DBSubnetGroupDescription = Sub('${EnvShort}-Private')
        self.SubnetIds = Split(',', get_expvalue('SubnetsPrivate'))


class RDSDBSubnetGroupPublic(rds.DBSubnetGroup):
    def setup(self):
        self.DBSubnetGroupDescription = Sub('${EnvShort}-Public')
        self.SubnetIds = Split(',', get_expvalue('SubnetsPublic'))

# #################################
# ### START STACK INFRA CLASSES ###
# #################################


class RDS_ParameterGroups(object):
    def __init__(self, key):
        for n, v in getattr(cfg, key).items():
            resname = f'{key}{n}'
            # Resources
            r_PG = RDSDBParameterGroup(resname)
            r_PG.setup()
            r_PG.Parameters = v

            add_obj(r_PG)


class RDS_DB(object):
    def __init__(self, key):
        # Resources
        if cfg.RDSScheme == 'External':
            R_DB = RDSDBInstancePublic('DBInstance')
        if cfg.RDSScheme == 'Internal':
            R_DB = RDSDBInstancePrivate('DBInstance')

        R53_RecordSetRDS()

        add_obj([
            R_DB,
        ])


class RDS_SubnetGroups(object):
    def __init__(self, key):
        # Resources
        R_Private = RDSDBSubnetGroupPrivate('DBSubnetGroupPrivate')
        R_Private.setup()

        R_Public = RDSDBSubnetGroupPublic('DBSubnetGroupPublic')
        R_Public.setup()

        add_obj([
            R_Private,
            R_Public,
        ])

        # Outputs
        O_Private = Output('DBSubnetGroupPrivate')
        O_Private.Value = Ref('DBSubnetGroupPrivate')
        O_Private.Export = Export('DBSubnetGroupPrivate')

        O_Public = Output('DBSubnetGroupPublic')
        O_Public.Value = Ref('DBSubnetGroupPublic')
        O_Public.Export = Export('DBSubnetGroupPublic')

        add_obj([
            O_Private,
            O_Public,
        ])
