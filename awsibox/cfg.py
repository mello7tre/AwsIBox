import os
import sys
from functools import reduce

from .mod import (
    autoscaling,
    cloudformation,
    cloudfront,
    ec2,
)

cwd = os.getcwd()
sys.path.append(os.path.join(cwd, "lib"))

no_override = False

Parameters = {}
Conditions = {}
Mappings = {}
Resources = {}
Outputs = {}
Metadata = {}

OBJS = {}

YAML_COMMON_NO_BRAND = []

APP_DIR = os.path.dirname(os.path.realpath(__file__))

PATH_INT = os.path.join(APP_DIR, "cfg")
PATH_INT = os.path.normpath(PATH_INT)

PATH_EXT = os.path.join(cwd, "cfg")
PATH_EXT = os.path.normpath(PATH_EXT)

IBOX_BASE_KEY_NAME = "IBOX_BASE"

IBOX_BRAND_DIR = "ibox"
STACKS_DIR = "stacks"

STACK_TYPES = [
    "agw",
    "cch",
    "clf",
    "ec2",
    "ecs",
    "rds",
    "res",
    "tsk",
    "lbd",
]

MAX_SECURITY_GROUPS = 4
# SECURITY_GROUPS_DEFAULT equals list of empty values
# (Ex. for "MAX_SECURITY_GROUPS = 3" we have "SECURITY_GROUPS_DEFAULT = ',,'")
SECURITY_GROUPS_DEFAULT = reduce(
    lambda a, i: f",{a}", list(range(MAX_SECURITY_GROUPS - 1)), ""
)

ENV_BASE = ["dev", "stg", "prd"]

DEFAULT_REGIONS = [
    "eu-west-1",
    "us-east-1",
]

AZones = {
    "MAX": 6,
    "default": 3,
    "us-east-1": 6,
    "us-west-1": 2,
    "us-west-2": 4,
    "ca-central-1": 2,
    "sa-east-1": 2,
    "cn-north-1": 2,
    "ap-northeast-3": 1,
}

AZoneNames = ["A", "B", "C", "D", "E", "F"]

VPC_DEFAULT_CIDR_BLOCK = "10.80.0.0/16"
VPC_DEFAULT_CIDR_BLOCK_PREFIX = ".".join(VPC_DEFAULT_CIDR_BLOCK.split(".")[0:2])
VPC_DEFAULT_SUBNETS_CIDR_BLOCK_PRIVATE = [
    f"{VPC_DEFAULT_CIDR_BLOCK_PREFIX}.{i * 16}.0/20" for i in range(AZones["MAX"])
]
VPC_DEFAULT_SUBNETS_CIDR_BLOCK_PUBLIC = [
    f"{VPC_DEFAULT_CIDR_BLOCK_PREFIX}.{i + 200}.0/24" for i in range(AZones["MAX"])
]

TROPO_CLASS_TO_CFM = {
    "AWS::WAFv2::WebACL": {
        "WebACLRule": "Rule",
    },
    "AWS::ECR::ReplicationConfiguration": {
        "ReplicationConfigurationProperty": "ReplicationConfiguration"
    },
}

EVAL_TROPO_FUNCTIONS_IN_CFG = (
    "Sub(",
    "Ref(",
    "GetAtt(",
    "Split(",
    "Select(",
    "Export(",
    "ImportValue(",
    "Join(",
    "Base64(",
    "If(",
    "Equals(",
    "Not(",
    "GetAZs(",
    "Tags(",
    "FindInMap(",
)

EVAL_PYTHON_FUNCTIONS_IN_CFG = (
    "cfg.",
    "get_expvalue(",
    "get_subvalue(",
    "get_endvalue(",
    "get_resvalue(",
    "get_condition(",
    "dict(",
    "eval(",
    "str(",
    "int(",
    "list(",
    "getattr(",
    "range(",
)

EVAL_FUNCTIONS_IN_CFG = EVAL_PYTHON_FUNCTIONS_IN_CFG + EVAL_TROPO_FUNCTIONS_IN_CFG

CLF_PATH_PATTERN_REPLACEMENT = {
    "/": "SLASH",
    "*": "STAR",
    "-": "HYPH",
    "?": "QUEST",
    ".": "DOT",
    "_": "USCORE",
}

MERGE_RP_KEEP_AS_LIST = ("IBOX_LINKED_OBJ",)

# override previous cfg with an External one
try:
    with open(os.path.join(cwd, "lib", "cfgExt.py")) as f:
        exec(f.read())
except FileNotFoundError:
    pass


class BuildEnvs(dict):
    def __init__(self, *arg, **kw):
        super().__init__(*arg, **kw)

    def clear(self):
        self.__dict__.clear()
        return super().clear()

    def __setattr__(self, key, item):
        super().__setattr__(key, item)
        super().__setitem__(key, item)


CFG_TO_FUNC_RENAME = {
    "lambda": "awslambda",
    "AutoScalingAutoScalingGroup": "AutoScalingGroup",
    "EC2LaunchTemplate": "LaunchTemplate",
    "LambdaFunction": "Lambda",
    "CloudFrontOriginAccessControl": "CloudFrontOriginOriginAccessControl",
    "Subscription": "SubscriptionResource",
    "Route53ResolverResolverEndpoint": "Route53ResolverEndpoint",
    "Route53ResolverResolverRule": "Route53ResolverRule",
    "Route53ResolverResolverRuleAssociation": "Route53ResolverRuleAssociation",
}

# Order is VERY important do not CHANGE it!
CFG_TO_FUNC_OVERRIDE = {
    "Parameter": {
        "func": (None, "Parameter"),
    },
    "Condition": {
        "func": (None, "Condition"),
    },
    "Mapping": {
        "module": cloudformation,
        "func": "CFM_Mappings",
    },
    "ApiGatewayDeployment": {
        "dep": ["ApiGatewayStage"],
    },
    "AutoScalingGroup": {
        "dep": ["ECSCapacityProvider"],
    },
    "CloudFormationCustomResource": {
        "dep": ["ECSService", "ElasticLoadBalancingV2Listener"],
    },
    "CloudFrontDistribution": {
        "module": cloudfront,
        "func": "CF_CloudFront",
        "dep": [
            "ElasticLoadBalancingV2Listener",
            "ElasticLoadBalancingLoadBalancer",
            "CloudFrontLambdaFunctionAssociation",
        ],
    },
    "CloudFrontOriginAccessIdentity": {
        "dep": ["S3Bucket"],
    },
    # This is not a resource but a sub-resource
    "CloudFrontLambdaFunctionAssociation": {
        "func": ("cloudfront", "LambdaFunctionAssociation"),
    },
    "CloudFrontVpcOrigin": {
        "func": ("cloudfront", "VpcOrigin"),
        "dep": ["ElasticLoadBalancingV2Listener"],
    },
    "CloudWatchAlarm": {
        "dep": [
            "ElasticLoadBalancingLoadBalancer",
            "ElasticLoadBalancingV2LoadBalancer",
            "SQSQueue",
            "Lambda",
        ],
    },
    "EC2SecurityGroup": {
        "module": ec2,
        "func": "SG_SecurityGroup",
        "dep": [
            "ECSTaskDefinition",
            "EFSFileSystem",
            "ElasticLoadBalancingV2Listener",
        ],
    },
    "EC2SecurityGroupIngress": {
        "module": ec2,
        "func": "SG_SecurityGroupIngresses",
        "dep": [
            "ElasticLoadBalancingV2Listener",
            "ElasticLoadBalancingV2TargetGroup",
            "ElasticLoadBalancingLoadBalancer",
            "EFSFileSystem",
        ],
    },
    "EC2Subnet": {
        "dep": ["EC2VPC"],
    },
    "EC2SubnetRouteTableAssociation": {
        "dep": ["EC2VPC"],
    },
    "ECSService": {
        "dep": ["ECSTaskDefinition"],
    },
    "ElasticLoadBalancingV2Listener": {
        "dep": ["ElasticLoadBalancingLoadBalancer"],
    },
    "ElasticLoadBalancingV2TargetGroup": {
        # need this for override on ContainerDefinitions1ContainerPort
        "dep": ["ECSTaskDefinition"],
    },
    "IAMPolicy": {
        "func": ("iam", "PolicyType"),
        "dep": ["S3Bucket"],
    },
    "IAMRole": {
        "dep": ["Lambda", "S3Bucket"],
    },
    "LambdaLayerVersionPermission": {
        "dep": ["LambdaLayerVersion"],
    },
    "LambdaPermission": {
        "dep": ["SNSSubscription", "Lambda", "EventsRule", "SchedulerSchedule"],
    },
    "LambdaVersion": {
        "dep": ["Lambda"],
    },
    "LaunchTemplate": {
        "module": ec2,
        "func": "EC2_LaunchTemplate",
    },
    "LogsLogGroup": {
        "dep": ["Lambda"],
    },
    "RDSDBParameterGroup": {
        "dep": ["RDSDBInstance"],
    },
    "Route53RecordSet": {
        "func": ("route53", "RecordSetType"),
        "dep": [
            "ApiGatewayDomainName",
            "DBInstance",
            "EFSFileSystem",
            "ElasticLoadBalancingLoadBalancer",
            "CloudFrontDistribution",
        ],
    },
    "S3BucketPolicy": {
        "dep": ["S3Bucket"],
    },
    "SQSQueuePolicy": {
        "dep": ["SNSSubscription"],
    },
    # ReplicateRegions need to be the last one
    "CCRReplicateRegions": {
        "module": cloudformation,
        "func": "CFM_CustomResourceReplicator",
    },
    # Output need to be last line
    "Output": {
        "func": (None, "Output"),
    },
}
