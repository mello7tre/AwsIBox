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


def boolean(x):
    if x in [True, 1, "1", "true", "True"]:
        return True
    if x in [False, 0, "0", "false", "False"]:
        return False
    raise ValueError


# Fix to avoid setting OS variable TROPO_REAL_BOOL
validators.boolean = boolean
