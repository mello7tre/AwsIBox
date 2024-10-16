import os
import sys
from functools import reduce
from .cfg_instance_types import INSTANCE_LIST, INSTANCE_LIST_RDS, EPHEMERAL_MAP

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


# Order is VERY important do not CHANGE it!
CFG_TO_FUNC = {
    "Parameter": {"module": "joker", "func": (None, "Parameter")},
    "Condition": {"module": "joker", "func": (None, "Condition")},
    "Mapping": {"module": "cloudformation", "func": "CFM_Mappings"},
    "ApiGatewayAccount": {"module": "joker", "func": ("apigateway", "Account")},
    "ApiGatewayApiKey": {"module": "joker", "func": ("apigateway", "ApiKey")},
    "ApiGatewayBasePathMapping": {
        "module": "joker",
        "func": ("apigateway", "BasePathMapping"),
    },
    "ApiGatewayDeployment": {
        "module": "joker",
        "func": ("apigateway", "Deployment"),
        "dep": ["ApiGatewayStage"],
    },
    "ApiGatewayDomainName": {"module": "joker", "func": ("apigateway", "DomainName")},
    "ApiGatewayMethod": {"module": "joker", "func": ("apigateway", "Method")},
    "ApiGatewayRestApi": {"module": "joker", "func": ("apigateway", "RestApi")},
    "ApiGatewayResource": {"module": "joker", "func": ("apigateway", "Resource")},
    "ApiGatewayStage": {"module": "joker", "func": ("apigateway", "Stage")},
    "ApiGatewayUsagePlan": {"module": "joker", "func": ("apigateway", "UsagePlan")},
    "ApiGatewayUsagePlanKey": {
        "module": "joker",
        "func": ("apigateway", "UsagePlanKey"),
    },
    "ApplicationAutoScalingScalableTarget": {
        "module": "joker",
        "func": ("applicationautoscaling", "ScalableTarget"),
    },
    "ApplicationAutoScalingScalingPolicy": {
        "module": "joker",
        "func": ("applicationautoscaling", "ScalingPolicy"),
    },
    "AutoScalingLifecycleHook": {
        "module": "joker",
        "func": ("autoscaling", "LifecycleHook"),
    },
    "AutoScalingGroup": {
        "module": "autoscaling",
        "func": "AS_Autoscaling",
        "dep": ["SecurityGroups", "ECSCapacityProvider"],
    },
    "AutoScalingScalingPolicy": {
        "module": "joker",
        "func": ("autoscaling", "ScalingPolicy"),
    },
    "AutoScalingScheduledAction": {
        "module": "joker",
        "func": ("autoscaling", "ScheduledAction"),
    },
    "CertificateManagerCertificate": {
        "module": "joker",
        "func": ("certificatemanager", "Certificate"),
    },
    "CloudFormationCustomResource": {
        "module": "joker",
        "func": ("cloudformation", "CustomResource"),
        "dep": ["ECSService"],
    },
    "CloudFrontCachePolicy": {"module": "joker", "func": ("cloudfront", "CachePolicy")},
    "CloudFrontDistribution": {
        "module": "cloudfront",
        "func": "CF_CloudFront",
        "dep": [
            "ElasticLoadBalancingV2Listener",
            "ElasticLoadBalancingLoadBalancer",
            "CloudFrontLambdaFunctionAssociation",
        ],
    },
    "CloudFrontFunction": {
        "module": "joker",
        "func": ("cloudfront", "Function"),
    },
    "CloudFrontLambdaFunctionAssociation": {
        "module": "joker",
        "func": ("cloudfront", "LambdaFunctionAssociation"),
    },
    "CloudFrontOriginOriginAccessControl": {
        "module": "joker",
        "func": ("cloudfront", "OriginAccessControl"),
    },
    "CloudFrontOriginAccessIdentity": {
        "module": "joker",
        "func": ("cloudfront", "CloudFrontOriginAccessIdentity"),
        "dep": ["S3Bucket"],
    },
    "CloudFrontOriginRequestPolicy": {
        "module": "joker",
        "func": ("cloudfront", "OriginRequestPolicy"),
    },
    "CloudFrontResponseHeadersPolicy": {
        "module": "joker",
        "func": ("cloudfront", "ResponseHeadersPolicy"),
    },
    "CloudWatchAlarm": {
        "module": "joker",
        "func": ("cloudwatch", "Alarm"),
        "dep": ["ElasticLoadBalancingLoadBalancer", "SQSQueue"],
    },
    "CodeDeployApplication": {"module": "joker", "func": ("codedeploy", "Application")},
    "CodeDeployDeploymentGroup": {
        "module": "joker",
        "func": ("codedeploy", "DeploymentGroup"),
    },
    "DynamoDBTable": {"module": "joker", "func": ("dynamodb", "Table")},
    "EC2EIP": {"module": "joker", "func": ("ec2", "EIP")},
    "EC2InternetGateway": {"module": "joker", "func": ("ec2", "InternetGateway")},
    "EC2NatGateway": {"module": "joker", "func": ("ec2", "NatGateway")},
    "EC2Route": {"module": "joker", "func": ("ec2", "Route")},
    "EC2RouteTable": {"module": "joker", "func": ("ec2", "RouteTable")},
    "EC2SecurityGroup": {
        "module": "ec2",
        "func": "SG_SecurityGroup",
        "dep": ["ECSTaskDefinition", "EFSFileSystem"],
    },
    "EC2SecurityGroupIngress": {
        "module": "ec2",
        "func": "SG_SecurityGroupIngresses",
        "dep": [
            "ElasticLoadBalancingV2Listener",
            "ElasticLoadBalancingLoadBalancer",
            "EFSFileSystem",
        ],
    },
    "EC2Subnet": {"module": "joker", "func": ("ec2", "Subnet"), "dep": ["EC2VPC"]},
    "EC2SubnetRouteTableAssociation": {
        "module": "joker",
        "func": ("ec2", "SubnetRouteTableAssociation"),
        "dep": ["EC2VPC"],
    },
    "EC2VPC": {"module": "joker", "func": ("ec2", "VPC")},
    "EC2VPCEndpoint": {"module": "joker", "func": ("ec2", "VPCEndpoint")},
    "EC2VPCGatewayAttachment": {
        "module": "joker",
        "func": ("ec2", "VPCGatewayAttachment"),
    },
    "EC2VPCPeeringConnection": {
        "module": "joker",
        "func": ("ec2", "VPCPeeringConnection"),
    },
    "ECRRegistryPolicy": {"module": "joker", "func": ("ecr", "RegistryPolicy")},
    "ECRReplicationConfiguration": {
        "module": "joker",
        "func": ("ecr", "ReplicationConfiguration"),
    },
    "ECRRepository": {"module": "joker", "func": ("ecr", "Repository")},
    "ECSCapacityProvider": {"module": "joker", "func": ("ecs", "CapacityProvider")},
    "ECSCluster": {"module": "joker", "func": ("ecs", "Cluster")},
    "ECSClusterCapacityProviderAssociations": {
        "module": "joker",
        "func": ("ecs", "ClusterCapacityProviderAssociations"),
    },
    "ECSService": {
        "module": "joker",
        "func": ("ecs", "Service"),
        "dep": ["SecurityGroups", "ECSTaskDefinition"],
    },
    "ECSTaskDefinition": {"module": "joker", "func": ("ecs", "TaskDefinition")},
    "EFSAccessPoint": {"module": "joker", "func": ("efs", "AccessPoint")},
    "EFSFileSystem": {"module": "joker", "func": ("efs", "FileSystem")},
    "EFSMountTarget": {"module": "joker", "func": ("efs", "MountTarget")},
    "ElastiCacheCacheCluster": {
        "module": "joker",
        "func": ("elasticache", "CacheCluster"),
    },
    "ElastiCacheParameterGroup": {
        "module": "joker",
        "func": ("elasticache", "ParameterGroup"),
    },
    "ElastiCacheReplicationGroup": {
        "module": "joker",
        "func": ("elasticache", "ReplicationGroup"),
    },
    "ElastiCacheSubnetGroup": {
        "module": "joker",
        "func": ("elasticache", "SubnetGroup"),
    },
    "ElasticLoadBalancingLoadBalancer": {
        "module": "joker",
        "func": ("elasticloadbalancing", "LoadBalancer"),
    },
    "ElasticLoadBalancingV2LoadBalancer": {
        "module": "joker",
        "func": ("elasticloadbalancingv2", "LoadBalancer"),
    },
    "ElasticLoadBalancingV2Listener": {
        "module": "joker",
        "func": ("elasticloadbalancingv2", "Listener"),
        "dep": ["ElasticLoadBalancingLoadBalancer"],
    },
    "ElasticLoadBalancingV2ListenerRule": {
        "module": "joker",
        "func": ("elasticloadbalancingv2", "ListenerRule"),
    },
    "ElasticLoadBalancingV2TargetGroup": {
        "module": "joker",
        "func": ("elasticloadbalancingv2", "TargetGroup"),
        # need this for override on ContainerDefinitions1ContainerPort
        "dep": ["ECSTaskDefinition"],
    },
    "EventsRule": {
        "module": "joker",
        "func": ("events", "Rule"),
        "dep": ["SecurityGroups"],
    },
    "IAMGroup": {"module": "joker", "func": ("iam", "Group")},
    "IAMInstanceProfile": {"module": "joker", "func": ("iam", "InstanceProfile")},
    "IAMManagedPolicy": {"module": "joker", "func": ("iam", "ManagedPolicy")},
    "IAMPolicy": {
        "module": "joker",
        "func": ("iam", "PolicyType"),
        "dep": ["S3Bucket"],
    },
    "IAMRole": {
        "module": "joker",
        "func": ("iam", "Role"),
        "dep": ["Lambda", "S3Bucket"],
    },
    "IAMUser": {"module": "joker", "func": ("iam", "User")},
    "IAMUserToGroupAddition": {
        "module": "joker",
        "func": ("iam", "UserToGroupAddition"),
    },
    "KMSAlias": {"module": "joker", "func": ("kms", "Alias")},
    "KMSKey": {"module": "joker", "func": ("kms", "Key")},
    "Lambda": {"module": "joker", "func": ("awslambda", "Function")},
    "LambdaEventInvokeConfig": {
        "module": "joker",
        "func": ("awslambda", "EventInvokeConfig"),
    },
    "LambdaEventSourceMapping": {
        "module": "joker",
        "func": ("awslambda", "EventSourceMapping"),
    },
    "LambdaLayerVersion": {"module": "joker", "func": ("awslambda", "LayerVersion")},
    "LambdaLayerVersionPermission": {
        "module": "joker",
        "func": ("awslambda", "LayerVersionPermission"),
        "dep": ["LambdaLayerVersion"],
    },
    "LambdaPermission": {
        "module": "joker",
        "func": ("awslambda", "Permission"),
        "dep": ["SNSSubscription", "Lambda", "EventsRule", "SchedulerSchedule"],
    },
    "LambdaVersion": {
        "module": "joker",
        "func": ("awslambda", "Version"),
        "dep": ["Lambda"],
    },
    "LogsLogGroup": {
        "module": "joker",
        "func": ("logs", "LogGroup"),
        "dep": ["Lambda"],
    },
    "RDSDBInstance": {"module": "joker", "func": ("rds", "DBInstance")},
    "RDSDBParameterGroup": {
        "module": "joker",
        "func": ("rds", "DBParameterGroup"),
        "dep": ["RDSDBInstance"],
    },
    "RDSDBSubnetGroup": {"module": "joker", "func": ("rds", "DBSubnetGroup")},
    "Route53HostedZone": {"module": "joker", "func": ("route53", "HostedZone")},
    "Route53RecordSet": {
        "module": "joker",
        "func": ("route53", "RecordSetType"),
        "dep": [
            "ApiGatewayDomainName",
            "DBInstance",
            "EFSFileSystem",
            "ElasticLoadBalancingLoadBalancer",
            "CloudFrontDistribution",
        ],
    },
    "Route53ResolverEndpoint": {
        "module": "joker",
        "func": ("route53resolver", "ResolverEndpoint"),
    },
    "Route53ResolverRule": {
        "module": "joker",
        "func": ("route53resolver", "ResolverRule"),
    },
    "Route53ResolverRuleAssociation": {
        "module": "joker",
        "func": ("route53resolver", "ResolverRuleAssociation"),
    },
    "S3Bucket": {"module": "joker", "func": ("s3", "Bucket")},
    "S3BucketPolicy": {
        "module": "joker",
        "func": ("s3", "BucketPolicy"),
        "dep": ["S3Bucket"],
    },
    "SecurityGroups": {
        "module": "ec2",
        "func": "SG_SecurityGroups",
        "dep": ["ElasticLoadBalancingLoadBalancer"],
    },
    "ServiceDiscoveryPublicDnsNamespace": {
        "module": "joker",
        "func": ("servicediscovery", "PublicDnsNamespace"),
    },
    "ServiceDiscoveryService": {
        "module": "joker",
        "func": ("servicediscovery", "Service"),
    },
    "SchedulerSchedule": {
        "module": "joker",
        "func": ("scheduler", "Schedule"),
        "dep": ["SecurityGroups"],
    },
    "SSOPermissionSet": {"module": "joker", "func": ("sso", "PermissionSet")},
    "SSOAssignment": {"module": "joker", "func": ("sso", "Assignment")},
    "SQSQueue": {"module": "joker", "func": ("sqs", "Queue")},
    "SQSQueuePolicy": {
        "module": "joker",
        "func": ("sqs", "QueuePolicy"),
        "dep": ["SNSSubscription"],
    },
    "SNSSubscription": {"module": "joker", "func": ("sns", "SubscriptionResource")},
    "SNSTopic": {"module": "joker", "func": ("sns", "Topic")},
    "SNSTopicPolicy": {"module": "joker", "func": ("sns", "TopicPolicy")},
    "SSMParameter": {"module": "joker", "func": ("ssm", "Parameter")},
    "WAFv2IPSet": {
        "module": "joker",
        "func": ("wafv2", "IPSet"),
    },
    "WAFv2WebACL": {
        "module": "joker",
        "func": ("wafv2", "WebACL"),
    },
    # ReplicateRegions need to be the last one
    "CCRReplicateRegions": {
        "module": "cloudformation",
        "func": "CFM_CustomResourceReplicator",
    },
    # Output need to be last line
    "Output": {"module": "joker", "func": (None, "Output")},
}
