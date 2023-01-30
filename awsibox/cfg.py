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

OBJS = {}

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
    }
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
    "SG_SecurityGroups",
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
        "Name": "t4g",
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
    {
        "Name": "c7g",
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
        "module": "autoscaling",
        "func": "AS_ScalingPolicies",
    },
    "Apps": {"module": "joker", "func": ("codedeploy", "DeploymentGroup")},
    "AutoScalingLifecycleHook": {
        "module": "joker",
        "func": ("autoscaling", "LifecycleHook"),
    },
    "AutoScalingGroup": {
        "module": "autoscaling",
        "func": "AS_Autoscaling",
        "dep": ["SecurityGroups"],
    },
    "AutoScalingScalingPolicy": {"module": "autoscaling", "func": "AS_ScalingPolicies"},
    "AutoScalingScheduledAction": {
        "module": "joker",
        "func": ("autoscaling", "ScheduledAction"),
    },
    "Bucket": {"module": "s3", "func": "S3_Buckets"},
    "CertificateManagerCertificate": {
        "module": "joker",
        "func": ("certificatemanager", "Certificate"),
    },
    "ElastiCacheSubnetGroup": {
        "module": "joker",
        "func": ("elasticache", "SubnetGroup"),
    },
    "CloudFrontCachePolicy": {"module": "joker", "func": ("cloudfront", "CachePolicy")},
    "CloudFrontDistribution": {
        "module": "cloudfront",
        "func": "CF_CloudFront",
        "dep": [
            "ElasticLoadBalancingV2Listener",
            "LoadBalancer",
            "CloudFrontLambdaFunctionAssociation",
        ],
    },
    "CloudFrontLambdaFunctionAssociation": {
        "module": "joker",
        "func": ("cloudfront", "LambdaFunctionAssociation"),
    },
    "CloudFrontOriginAccessIdentity": {
        "module": "joker",
        "func": ("cloudfront", "CloudFrontOriginAccessIdentity"),
        "dep": ["Bucket"],
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
        "dep": ["LoadBalancer", "SQSQueue"],
    },
    "CodeDeployApplication": {"module": "joker", "func": ("codedeploy", "Application")},
    "DynamoDBTable": {"module": "joker", "func": ("dynamodb", "Table")},
    "EC2EIP": {"module": "joker", "func": ("ec2", "EIP")},
    "EC2InternetGateway": {"module": "joker", "func": ("ec2", "InternetGateway")},
    "EC2NatGateway": {"module": "joker", "func": ("ec2", "NatGateway")},
    "EC2Route": {"module": "joker", "func": ("ec2", "Route")},
    "EC2RouteTable": {"module": "joker", "func": ("ec2", "RouteTable")},
    "EC2SecurityGroup": {"module": "ec2", "func": "SG_SecurityGroup"},
    "EC2SecurityGroupIngress": {
        "module": "ec2",
        "func": "SG_SecurityGroupIngresses",
        "dep": ["ElasticLoadBalancingV2Listener"],
    },
    "EC2Subnet": {"module": "ec2", "func": "EC2_Subnet"},
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
    "ECRRepository": {"module": "ecr", "func": "ECR_Repositories"},
    "ECSCapacityProvider": {"module": "joker", "func": ("ecs", "CapacityProvider")},
    "ECSCluster": {"module": "joker", "func": ("ecs", "Cluster")},
    "ECSClusterCapacityProviderAssociations": {
        "module": "joker",
        "func": ("ecs", "ClusterCapacityProviderAssociations"),
    },
    "EFSAccessPoint": {"module": "joker", "func": ("efs", "AccessPoint")},
    "EFSFileSystem": {"module": "efs", "func": "EFS_FileStorage"},
    "ElastiCacheCacheCluster": {
        "module": "joker",
        "func": ("elasticache", "CacheCluster"),
    },
    "ElastiCacheReplicationGroup": {
        "module": "joker",
        "func": ("elasticache", "ReplicationGroup"),
    },
    "ElasticLoadBalancingV2LoadBalancer": {
        "module": "joker",
        "func": ("elasticloadbalancingv2", "LoadBalancer"),
    },
    "ElasticLoadBalancingV2Listener": {
        "module": "joker",
        "func": ("elasticloadbalancingv2", "Listener"),
        "dep": ["LoadBalancer"],
    },
    "ElasticLoadBalancingV2ListenerRule": {
        "module": "joker",
        "func": ("elasticloadbalancingv2", "ListenerRule"),
    },
    "ElasticLoadBalancingV2TargetGroup": {
        "module": "joker",
        "func": ("elasticloadbalancingv2", "TargetGroup"),
    },
    "EventsRule": {
        "module": "joker",
        "func": ("events", "Rule"),
        "dep": ["SecurityGroups"],
    },
    "IAMGroup": {"module": "iam", "func": "IAM_Groups"},
    "IAMInstanceProfile": {"module": "joker", "func": ("iam", "InstanceProfile")},
    "IAMManagedPolicy": {"module": "joker", "func": ("iam", "ManagedPolicy")},
    "IAMPolicy": {"module": "joker", "func": ("iam", "PolicyType"), "dep": ["Bucket"]},
    "IAMRole": {
        "module": "joker",
        "func": ("iam", "Role"),
        "dep": ["Lambda", "Bucket"],
    },
    "IAMUser": {"module": "iam", "func": "IAM_Users"},
    "IAMUserToGroupAddition": {"module": "iam", "func": "IAM_UserToGroupAdditions"},
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
    "LoadBalancer": {
        "module": "elasticloadbalancing",
        "func": "LB_ElasticLoadBalancing",
        # need this for override on ContainerDefinitions1ContainerPort
        "dep": ["TaskDefinition"],
    },
    "LogsLogGroup": {
        "module": "joker",
        "func": ("logs", "LogGroup"),
        "dep": ["Lambda"],
    },
    "RDSDBInstance": {"module": "rds", "func": "RDS_DB"},
    "RDSDBSubnetGroup": {"module": "joker", "func": ("rds", "DBSubnetGroup")},
    "Route53HostedZone": {"module": "joker", "func": ("route53", "HostedZone")},
    "Route53RecordSet": {
        "module": "joker",
        "func": ("route53", "RecordSetType"),
        "dep": [
            "ApiGatewayDomainName",
            "DBInstance",
            "EFSFileSystem",
            "LoadBalancer",
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
    "SecurityGroups": {
        "module": "ec2",
        "func": "SG_SecurityGroups",
        "dep": ["LoadBalancer"],
    },
    "Service": {
        "module": "ecs",
        "func": "ECS_Service",
        "dep": ["SecurityGroups"],
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
    "SQSQueue": {"module": "joker", "func": ("sqs", "Queue")},
    "SQSQueuePolicy": {
        "module": "joker",
        "func": ("sqs", "QueuePolicy"),
        "dep": ["SNSSubscription"],
    },
    "SNSSubscription": {"module": "joker", "func": ("sns", "SubscriptionResource")},
    "SNSTopic": {"module": "joker", "func": ("sns", "Topic")},
    "SSMParameter": {"module": "joker", "func": ("ssm", "Parameter")},
    "TaskDefinition": {"module": "ecs", "func": "ECS_TaskDefinition"},
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
    "WAFv2IPSet": {
        "module": "joker",
        "func": ("wafv2", "IPSet"),
    },
    "WAFv2WebACL": {
        "module": "joker",
        "func": ("wafv2", "WebACL"),
    },
    # CloudformationCustomResource begin here
    "CCRFargateSpot": {
        "module": "cloudformation",
        "func": "CFM_CustomResourceFargateSpot",
    },
    "CCRLightHouse": {
        "module": "cloudformation",
        "func": "CFM_CustomResourceLightHouse",
    },
    # ReplicateRegions need to be the last one
    "CCRReplicateRegions": {
        "module": "cloudformation",
        "func": "CFM_CustomResourceReplicator",
    },
    # Output need to be last line
    "Output": {"module": "cloudformation", "func": "CFM_Outputs"},
}
