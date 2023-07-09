import os
import sys
import random
import string
import copy
import json
import logging
from pprint import pprint, pformat
from pathlib import PurePath
from troposphere import validators
from troposphere.autoscaling import Tags as asgTags
import troposphere.ssm as ssm
import troposphere.sso as sso
import troposphere.rds as rds
import troposphere.ec2 as ec2
import troposphere.elasticloadbalancing as elb
import troposphere.elasticloadbalancingv2 as elbv2

from troposphere import (
    And,
    AWSHelperFn,
    AWSObject,
    AWSProperty,
    PropsDictType,
    Base64,
    BaseAWSObject,
    Condition,
    Equals,
    Export,
    FindInMap,
    GetAtt,
    GetAZs,
    If,
    ImportValue,
    Join,
    Not,
    Or,
    Output,
    Parameter,
    Ref,
    Select,
    Split,
    Sub,
    Tags,
    Template,
)

from . import cfg

from .cfg import (
    MAX_SECURITY_GROUPS,
    SECURITY_GROUPS_DEFAULT,
)


### BEGIN TROPOSPHERE OVERRIDE ###


# Temporary fix for https://github.com/cloudtools/troposphere/issues/2146
sso.PermissionSet.props["InlinePolicy"] = (str, False)

# Temporary fix for https://github.com/cloudtools/troposphere/issues/1474
def my_one_of(class_name, properties, property, conditionals):
    if properties.get(property) not in conditionals and not isinstance(
        properties.get(property), If
    ):
        raise ValueError(
            # Ensure we handle None as a valid value
            '%s.%s must be one of: "%s"'
            % (
                class_name,
                property,
                ", ".join(condition for condition in conditionals if condition),
            )
        )


elbv2.one_of = my_one_of

# Fix troposphere/elasticloadbalancing.py LBCookieStickinessPolicy is a List and do not use class LBCookieStickinessPolicy
elb.LoadBalancer.props["LBCookieStickinessPolicy"] = (
    [elb.LBCookieStickinessPolicy],
    False,
)
elb.LoadBalancer.props["Listeners"] = ([elb.Listener], False)


# Fix to avoid setting OS variable TROPO_REAL_BOOL
def boolean(x):
    if x in [True, 1, "1", "true", "True"]:
        return True
    if x in [False, 0, "0", "false", "False"]:
        return False
    raise ValueError


validators.boolean = boolean


# RDSDBInstance reax check when using SourceDBInstanceIdentifier, forbidden properties can use If Condition to remove them
def validate_dbinstance(self):
    if "DBSnapshotIdentifier" not in self.properties:
        if "Engine" not in self.properties:
            raise ValueError(
                "Resource Engine is required in type %s" % self.resource_type
            )

    #    if "SourceDBInstanceIdentifier" in self.properties:
    #
    #        invalid_replica_properties = (
    #            "DBName",
    #            "MasterUsername",
    #            "MasterUserPassword",
    #            "PreferredBackupWindow",
    #            "MultiAZ",
    #            "DBSnapshotIdentifier",
    #        )
    #
    #        invalid_properties = [
    #            s for s in self.properties.keys() if s in invalid_replica_properties
    #        ]
    #
    #        if invalid_properties:
    #            raise ValueError(
    #                (
    #                    "{0} properties can't be provided when "
    #                    "SourceDBInstanceIdentifier is present "
    #                    "AWS::RDS::DBInstance."
    #                ).format(", ".join(sorted(invalid_properties)))
    #            )

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
            r"Either (MasterUsername and MasterUserPassword) or"
            r" DBSnapshotIdentifier are required in type "
            r"AWS::RDS::DBInstance."
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
        min_storage_size = 100
        engine = self.properties.get("Engine")
        if not isinstance(engine, AWSHelperFn) and engine.startswith("sqlserver"):
            min_storage_size = 20

        if (
            not isinstance(allocated_storage, AWSHelperFn)
            and int(allocated_storage) < min_storage_size
        ):
            raise ValueError(
                f"AllocatedStorage must be at least {min_storage_size} when "
                "Iops is set."
            )
        if (
            not isinstance(allocated_storage, AWSHelperFn)
            and not isinstance(iops, AWSHelperFn)
            and float(iops) / float(allocated_storage) > 50.0
        ):
            raise ValueError(
                "AllocatedStorage must be no less than " "1/50th the provisioned Iops"
            )


rds.DBInstance.validate = validate_dbinstance

# troposphere ec2 is quite old and SecurityGroupIngress is only a list
# without the obj type, this break auto_get_props, fix it overriding
ec2.SecurityGroup.props = {
    "GroupName": (str, False),
    "GroupDescription": (str, True),
    "SecurityGroupEgress": (list, False),
    "SecurityGroupIngress": ([ec2.SecurityGroupRule], False),
    "VpcId": (str, False),
    "Tags": ((Tags, list), False),
}
