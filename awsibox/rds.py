import troposphere.rds as rds

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


class RDSDBInstance(rds.DBInstance):
    def validate(self):
        if "DBSnapshotIdentifier" not in self.properties:
            if "Engine" not in self.properties:
                raise ValueError(
                    "Resource Engine is required in type %s" % self.resource_type
                )

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

        if (
            (
                "DBSnapshotIdentifier" not in self.properties
                and "SourceDBInstanceIdentifier" not in self.properties
            )
            and (
                "MasterUsername" not in self.properties
                or "MasterUserPassword" not in self.properties
            )
            and ("DBClusterIdentifier" not in self.properties)
        ):
            raise ValueError(
                "Either (MasterUsername and MasterUserPassword) or"
                " DBSnapshotIdentifier are required in type "
                "AWS::RDS::DBInstance."
            )

        if "KmsKeyId" in self.properties and "StorageEncrypted" not in self.properties:
            raise ValueError(
                "If KmsKeyId is provided, StorageEncrypted is required "
                "AWS::RDS::DBInstance."
            )

        nonetype = type(None)
        avail_zone = self.properties.get("AvailabilityZone", None)
        multi_az = self.properties.get("MultiAZ", None)
        if not (
            isinstance(avail_zone, (AWSHelperFn, nonetype))
            and isinstance(multi_az, (AWSHelperFn, nonetype))
        ):
            if avail_zone and multi_az in [True, 1, "1", "true", "True"]:
                raise ValueError(
                    "AvailabiltyZone cannot be set on "
                    "DBInstance if MultiAZ is set to true."
                )

        storage_type = self.properties.get("StorageType", None)
        if storage_type and storage_type == "io1" and "Iops" not in self.properties:
            raise ValueError("Must specify Iops if using StorageType io1")

        allocated_storage = self.properties.get("AllocatedStorage")
        iops = self.properties.get("Iops", None)
        if iops and not isinstance(iops, AWSHelperFn):
            if (
                not isinstance(allocated_storage, AWSHelperFn)
                and allocated_storage < 100
            ):
                raise ValueError(
                    "AllocatedStorage must be at least 100 when " "Iops is set."
                )
            if (
                not isinstance(allocated_storage, AWSHelperFn)
                and not isinstance(iops, AWSHelperFn)
                and float(iops) / float(allocated_storage) > 10.0
            ):
                raise ValueError(
                    "AllocatedStorage must be no less than "
                    "1/10th the provisioned Iops"
                )

        return True


class RDSDBParameterGroup(rds.DBParameterGroup):
    def __init__(self, title, dbinstance, **kwargs):
        super().__init__(title, **kwargs)
        self.Description = Sub("MYSQL %s - ${AWS::StackName}" % self.title)
        self.Family = Sub(
            "${Engine}${EngineVersion}",
            **{
                "Engine": get_endvalue(f"{dbinstance}Engine"),
                "EngineVersion": Join(
                    ".",
                    [
                        Select(
                            0, Split(".", get_endvalue(f"{dbinstance}EngineVersion"))
                        ),
                        Select(
                            1, Split(".", get_endvalue(f"{dbinstance}EngineVersion"))
                        ),
                    ],
                ),
            },
        )


def RDS_DB(key):
    for n, v in getattr(cfg, key).items():
        mapname = f"{key}{n}"

        if not v["IBOX_ENABLED"]:
            continue

        # trick to keep current in use resname and obj.title
        resname = v.get("IBOX_RESNAME", mapname)

        # resources
        r_DB = RDSDBInstance(resname)
        auto_get_props(r_DB, mapname=mapname)
        # trick - when providing DBSnapshotIdentifier
        # or SourceDBInstanceIdentifier some props must not exists
        for m in ["DBName", "MasterUsername", "MasterUserPassword"]:
            setattr(
                r_DB,
                m,
                If(
                    f"{mapname}DBInstanceSkipProperties",
                    Ref("AWS::NoValue"),
                    getattr(r_DB, m),
                ),
            )
        for m in ["SourceDBInstanceIdentifier", "DBSnapshotIdentifier"]:
            setattr(r_DB, m, If(f"{mapname}{m}", getattr(r_DB, m), Ref("AWS::NoValue")))

        # trick fixed name to avoid reboot for now
        # best way should be to use a name like DBParameterGroup{Engine}
        r_PG = RDSDBParameterGroup("DBParameterGroup1", mapname)
        r_PG.Parameters = cfg.DBParameterGroup1

        add_obj([r_DB, r_PG])
