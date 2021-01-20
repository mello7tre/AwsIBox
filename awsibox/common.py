import os
import sys
import random
import string
import copy
import json
import logging
from pprint import pprint, pformat
from troposphere.autoscaling import Tags as asgTags
import troposphere.ssm as ssm

from troposphere import (
    And,
    AWSHelperFn,
    AWSObject,
    AWSProperty,
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
    PARAMETERS_SKIP_OVERRIDE_CONDITION,
)


# Temporary fix for https://github.com/cloudtools/troposphere/issues/1474
def my_one_of(class_name, properties, property, conditionals):
    if (properties.get(property) not in conditionals and
            not isinstance(properties.get(property), If)):
        raise ValueError(
            # Ensure we handle None as a valid value
            '%s.%s must be one of: "%s"' % (
                class_name, property, ', '.join(
                    condition for condition in conditionals if condition
                )
            )
        )
