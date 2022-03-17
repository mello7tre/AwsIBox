import os
import sys
from functools import reduce

cwd = os.getcwd()
sys.path.append(os.path.join(cwd, "lib"))

no_override = False

Parameters = {}
Conditions = {}
Mappings = {}
Resources = {}
Outputs = {}

PATH_INT = os.path.join(os.path.dirname(os.path.realpath(__file__)), "cfg")
PATH_INT = os.path.normpath(PATH_INT)

PATH_EXT = os.path.join(cwd, "cfg")
PATH_EXT = os.path.normpath(PATH_EXT)

STACK_TYPES = [
    "agw",
    "alb",
    "cch",
    "clf",
    "ec2",
    "ecr",
    "ecs",
    "rds",
    "res",
    "tsk",
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
    "eu-central-1",
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

PARAMETERS_SKIP_OVERRIDE_CONDITION = (
    "Env",
    "UpdateMode",
    "RecordSetExternal",
    "DoNotSignal",
    "EfsMounts",
    "LaunchTemplateDataImageIdLatest",
    "VPCCidrBlock",
    "VPCName",
)

EVAL_FUNCTIONS_IN_CFG = (
    "cfg.",
    "get_expvalue(",
    "Sub(",
    "Ref(",
    "get_subvalue(",
    "get_endvalue(",
    "get_resvalue(",
    "get_condition(",
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
    "dict(",
    "eval(",
    "Tags(",
    "str(",
    "list(",
    "SG_SecurityGroups",
)

CLF_PATH_PATTERN_REPLACEMENT = {
    "/": "SLASH",
    "*": "STAR",
    "-": "HYPH",
    "?": "QUEST",
    ".": "DOT",
    "_": "USCORE",
}

INSTANCE_SIZES = [
    "nano",
    "micro",
    "small",
    "medium",
    "large",
    "xlarge",
    "2xlarge",
    "4xlarge",
    "8xlarge",
    "12xlarge",
    "16xlarge",
    "24xlarge",
    "32xlarge",
    "48xlarge",
]

INSTANCE_FAMILY = [
    {
        "Name": "t2",
        "Min": "nano",
        "Max": "2xlarge",
    },
    {
        "Name": "m4",
        "Min": "large",
        "Max": "4xlarge",
    },
    {
        "Name": "c4",
        "Min": "large",
        "Max": "4xlarge",
    },
    {
        "Name": "r4",
        "Min": "large",
        "Max": "4xlarge",
    },
    {
        "Name": "t3",
        "Min": "nano",
        "Max": "2xlarge",
    },
    {
        "Name": "m5",
        "Min": "large",
        "Max": "4xlarge",
    },
    {
        "Name": "c5",
        "Min": "large",
        "Max": "4xlarge",
    },
    {
        "Name": "r5",
        "Min": "large",
        "Max": "4xlarge",
    },
    {
        "Name": "t3a",
        "Min": "nano",
        "Max": "2xlarge",
    },
    {
        "Name": "m5a",
        "Min": "large",
        "Max": "4xlarge",
    },
    {
        "Name": "c5a",
        "Min": "large",
        "Max": "4xlarge",
    },
    {
        "Name": "r5a",
        "Min": "large",
        "Max": "4xlarge",
    },
    {
        "Name": "m6i",
        "Min": "large",
        "Max": "4xlarge",
    },
    {
        "Name": "c6i",
        "Min": "large",
        "Max": "4xlarge",
    },
    {
        "Name": "r6i",
        "Min": "large",
        "Max": "4xlarge",
    },
    {
        "Name": "m6a",
        "Min": "large",
        "Max": "4xlarge",
    },
    {
        "Name": "c6a",
        "Min": "large",
        "Max": "4xlarge",
    },
]

# override previous cfg with an External one
try:
    with open(os.path.join(cwd, "lib", "cfgExt.py")) as f:
        exec(f.read())
except FileNotFoundError:
    pass

# build instances list
def build_instance_list():
    family_instances_list = []
    for family in INSTANCE_FAMILY:
        name = family["Name"]
        min_size = INSTANCE_SIZES.index(family["Min"])
        max_size = INSTANCE_SIZES.index(family["Max"])

        for s in INSTANCE_SIZES[min_size : max_size + 1]:
            family_instances_list.append(f"{name}.{s}")

    return family_instances_list


INSTANCE_LIST = ["default"] + build_instance_list()

# Order is VERY important do not CHANGE it!
CFG_TO_FUNC = {
    "MappingClass": {"module": "mappings", "func": "Mappings"},
    "Parameter": {"module": "cloudformation", "func": "CFM_Parameters"},
    "Condition": {"module": "cloudformation", "func": "CFM_Conditions"},
    "Mapping": {"module": "cloudformation", "func": "CFM_Mappings"},
    # SecurityGroups need to stay here because it populate a cfg value
    # [cfg.SecurityGroupsImport] used later by other keys/modules
    "SecurityGroups": {"module": "securitygroup", "func": "SG_SecurityGroups"},
    "AutoScalingGroup": {"module": "autoscaling", "func": "AS_Autoscaling"},
    "ScheduledAction": {"module": "joker", "func": ("autoscaling", "ScheduledAction")},
    "ScalableTarget": {"module": "autoscaling", "func": "AS_ScalableTarget"},
    "AutoScalingScalingPolicy": {"module": "autoscaling", "func": "AS_ScalingPolicies"},
    "ApplicationAutoScalingScalingPolicy": {
        "module": "autoscaling",
        "func": "AS_ScalingPolicies",
    },
    "Bucket": {"module": "s3", "func": "S3_Buckets"},
    "Certificate": {"module": "joker", "func": ("certificatemanager", "Certificate")},
    "CodeDeployApp": {"module": "codedeploy", "func": "CD_Applications"},
    "Repository": {"module": "ecr", "func": "ECR_Repositories"},
    "ECSCluster": {"module": "joker", "func": ("ecs", "Cluster")},
    "ECSCapacityProvider": {"module": "joker", "func": ("ecs", "CapacityProvider")},
    "ECSClusterCapacityProviderAssociations": {
        "module": "joker",
        "func": ("ecs", "ClusterCapacityProviderAssociations"),
    },
    "Service": {"module": "ecs", "func": "ECS_Service"},
    "ApiGatewayAccount": {"module": "apigateway", "func": "AGW_Account"},
    "ApiGatewayDomainName": {"module": "apigateway", "func": "AGW_DomainName"},
    "ApiGatewayRestApi": {"module": "apigateway", "func": "AGW_RestApi"},
    "ApiGatewayBasePathMapping": {
        "module": "joker",
        "func": ("apigateway", "BasePathMapping"),
    },
    "ApiGatewayStage": {"module": "apigateway", "func": "AGW_Stages"},
    "ApiGatewayUsagePlan": {"module": "apigateway", "func": "AGW_UsagePlans"},
    "ApiGatewayApiKey": {"module": "apigateway", "func": "AGW_ApiKeys"},
    "LogGroupName": {"module": "logs", "func": "LGS_LogGroup"},
    "TaskDefinition": {"module": "ecs", "func": "ECS_TaskDefinition"},
    "EFSFileSystem": {"module": "efs", "func": "EFS_FileStorage"},
    "EFSAccessPoint": {"module": "joker", "func": ("efs", "AccessPoint")},
    "CacheSubnetGroup": {"module": "elasticache", "func": "CCH_SubnetGroups"},
    "CacheCluster": {"module": "elasticache", "func": "CCH_Cache"},
    "EventsRule": {"module": "events", "func": "EVE_EventRules"},
    "Role": {"module": "iam", "func": "IAM_Roles"},
    "IAMPolicy": {"module": "iam", "func": "IAM_Policies"},
    "IAMUser": {"module": "iam", "func": "IAM_Users"},
    "IAMGroup": {"module": "iam", "func": "IAM_Groups"},
    "IAMUserToGroupAddition": {"module": "iam", "func": "IAM_UserToGroupAdditions"},
    "KMSKey": {"module": "kms", "func": "KMS_Keys"},
    "Lambda": {"module": "lambdas", "func": "LBD_Lambdas"},
    "LambdaLayerVersion": {"module": "lambdas", "func": "LBD_LayerVersions"},
    "LambdaPermission": {"module": "joker", "func": ("awslambda", "Permission")},
    "LambdaEventSourceMapping": {
        "module": "joker",
        "func": ("awslambda", "EventSourceMapping"),
    },
    "LambdaEventInvokeConfig": {
        "module": "joker",
        "func": ("awslambda", "EventInvokeConfig"),
    },
    "LoadBalancer": {
        "module": "loadbalancing",
        "func": "LB_ElasticLoadBalancing",
    },
    "Alarm": {"module": "joker", "func": ("cloudwatch", "Alarm")},
    "CloudFrontDistribution": {"module": "cloudfront", "func": "CF_CloudFront"},
    "CloudFrontCachePolicy": {"module": "joker", "func": ("cloudfront", "CachePolicy")},
    "CloudFrontOriginRequestPolicy": {
        "module": "joker",
        "func": ("cloudfront", "OriginRequestPolicy"),
    },
    "CloudFrontOriginAccessIdentity": {
        "module": "joker",
        "func": ("cloudfront", "CloudFrontOriginAccessIdentity"),
    },
    "SNSSubscription": {"module": "sns", "func": "SNS_Subscriptions"},
    "SNSTopic": {"module": "sns", "func": "SNS_Topics"},
    "SQSQueue": {"module": "joker", "func": ("sqs", "Queue")},
    "ASGLifecycleHook": {"module": "joker", "func": ("autoscaling", "LifecycleHook")},
    "DBInstance": {"module": "rds", "func": "RDS_DB"},
    "DBSubnetGroup": {"module": "rds", "func": "RDS_SubnetGroups"},
    "HostedZone": {"module": "route53", "func": "R53_HostedZones"},
    "R53RecordSet": {"module": "route53", "func": "R53_RecordSets"},
    "WafByteMatchSet": {
        "module": "waf",
        "func": ["WAF_GlobalByteMatchSets", "WAF_RegionalByteMatchSets"],
    },
    "WafIPSet": {"module": "waf", "func": ["WAF_GlobalIPSets", "WAF_RegionalIPSets"]},
    "WafRule": {"module": "waf", "func": ["WAF_GlobalRules", "WAF_RegionalRules"]},
    "WafWebAcl": {
        "module": "waf",
        "func": ["WAF_GlobalWebAcls", "WAF_RegionalWebAcls"],
    },
    "ServiceDiscoveryPublicDnsNamespace": {
        "module": "joker",
        "func": ("servicediscovery", "PublicDnsNamespace"),
    },
    "ServiceDiscoveryService": {
        "module": "joker",
        "func": ("servicediscovery", "Service"),
    },
    "VPCEndpoint": {"module": "vpc", "func": "VPC_Endpoint"},
    "SecurityGroup": {"module": "securitygroup", "func": "SG_SecurityGroup"},
    "SecurityGroupIngress": {
        "module": "securitygroup",
        "func": "SG_SecurityGroupIngresses",
    },
    "VPC": {"module": "vpc", "func": "VPC_VPC"},
    "CCRLightHouse": {
        "module": "cloudformation",
        "func": "CFM_CustomResourceLightHouse",
    },
    "CCRFargateSpot": {
        "module": "cloudformation",
        "func": "CFM_CustomResourceFargateSpot",
    },
    # ReplicateRegions need to stay here
    "CCRReplicateRegions": {
        "module": "cloudformation",
        "func": "CFM_CustomResourceReplicator",
    },
    # Output need to be last line
    "Output": {"module": "cloudformation", "func": "CFM_Outputs"},
}
