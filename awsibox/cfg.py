import os
import sys
from functools import reduce

cwd = os.getcwd()
sys.path.append(os.path.join(cwd, 'lib'))

no_override = False

Parameters = {}
Conditions = {}
Mappings = {}
Resources = {}
Outputs = {}

PATH_INT = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfg')
PATH_INT = os.path.normpath(PATH_INT)

PATH_EXT = os.path.join(cwd, 'cfg')
PATH_EXT = os.path.normpath(PATH_EXT)

STACK_TYPES = [
    'agw',
    'alb',
    'cch',
    'clf',
    'ec2',
    'ecr',
    'ecs',
    'rds',
    'res',
    'tsk',
]

MAX_SECURITY_GROUPS = 4
# SECURITY_GROUPS_DEFAULT equals list of empty values
# (Ex. for "MAX_SECURITY_GROUPS = 3" we have "SECURITY_GROUPS_DEFAULT = ',,'")
SECURITY_GROUPS_DEFAULT = reduce(
    lambda a, i: f',{a}', list(range(MAX_SECURITY_GROUPS - 1)), '')

ENV_BASE = ['dev', 'stg', 'prd']

DEFAULT_REGIONS = [
    'eu-west-1',
    'us-east-1',
    'eu-central-1',
]

AZones = {
    'MAX': 6,
    'default': 3,
    'us-east-1': 6,
    'us-west-1': 2,
    'us-west-2': 4,
    'ca-central-1': 2,
    'sa-east-1': 2,
    'cn-north-1': 2,
    'ap-northeast-3': 1,
}

AZoneNames = ['A', 'B', 'C', 'D', 'E', 'F']

PARAMETERS_SKIP_OVERRIDE_CONDITION = (
    'Env',
    'UpdateMode',
    'RecordSetExternal',
    'DoNotSignal',
    'EfsMounts',
    'LaunchTemplateDataImageIdLatest',
    'VPCCidrBlock',
    'VPCName',
)

EVAL_FUNCTIONS_IN_CFG = (
    'cfg.',
    'get_expvalue(',
    'Sub(',
    'Ref(',
    'get_subvalue(',
    'get_endvalue(',
    'get_resvalue(',
    'get_condition(',
    'GetAtt(',
    'Split(',
    'Export(',
    'ImportValue(',
    'Join(',
    'Base64(',
    'If(',
    'Equals(',
    'Not(',
    'GetAZs(',
    'dict(',
    'eval(',
    'Tags(',
    'str(',
    'list(',
    'SG_SecurityGroups',
)

CLF_PATH_PATTERN_REPLACEMENT = {
    '/': 'SLASH',
    '*': 'STAR',
    '-': 'HYPH',
    '?': 'QUEST',
    '.': 'DOT',
    '_': 'USCORE',
}

BASE_CFGS = {
    'Bucket': {
        'Create': 'no',
        'AccountsRead': {
            'dev': 'none',
            'stg': 'none',
            'prd': 'none',
        },
        'AccountsWrite': {
            'dev': 'none',
            'stg': 'none',
            'prd': 'none',
        },
        'Cors': 'no',
        'CloudFrontOriginAccessIdentityExtra': {
            'Dev': 'none',
            'Stg': 'none',
            'Prd': 'none',
        },
        'PolicyStatementReplica': {
            'Resource': {},
            'Principal': 'none',
        },
        'Replication': {
            'Enabled': 'no',
            'ConfigurationRules': {},
        },
        'Versioning': 'Disabled',
    },
    'CloudFrontCacheBehaviors': {
        'Compress': True,
        'ForwardedValues': {
            'QueryString': True,
            'Headers': []
        },
        'ViewerProtocolPolicy': 'redirect-to-https'
    },
    'CloudFrontOrigins': 'IBOX_BASE',
    'DBInstance': 'IBOX_BASE',
    'ScheduledAction': 'IBOX_BASE',
    'ContainerDefinitions': 'IBOX_BASE',
    'AllowedIp': 'IBOX_BASE',
    'ElasticLoadBalancingV2TargetGroupECS': 'IBOX_BASE',
    'Certificate': 'IBOX_BASE',
    'CloudFrontCachePolicy': 'IBOX_BASE',
    'CloudFrontOriginRequestPolicy': 'IBOX_BASE',
}

INSTANCE_LIST = [
    'default',
    't2.nano', 't2.micro', 't2.small', 't2.medium', 't2.large',
    't2.xlarge', 't2.2xlarge',
    'm4.large', 'm4.xlarge', 'm4.2xlarge', 'm4.4xlarge',
    'c4.large', 'c4.xlarge', 'c4.2xlarge', 'c4.4xlarge',
    'r4.large', 'r4.xlarge', 'r4.2xlarge', 'r4.4xlarge',
    'g2.2xlarge', 'g3s.xlarge',
    't3.nano', 't3.micro', 't3.small', 't3.medium', 't3.large',
    't3.xlarge', 't3.2xlarge',
    'm5.large', 'm5.xlarge', 'm5.2xlarge', 'm5.4xlarge', 'm5.8xlarge',
    'm5.12xlarge', 'm5.16xlarge', 'm5.24xlarge',
    'c5.large', 'c5.xlarge', 'c5.2xlarge', 'c5.4xlarge', 'c5.9xlarge',
    'c5.12xlarge', 'c5.18xlarge', 'c5.24xlarge',
    'r5.large', 'r5.xlarge', 'r5.2xlarge', 'r5.4xlarge', 'r5.8xlarge',
    'r5.12xlarge', 'r5.16xlarge', 'r5.24xlarge',
    'a1.medium', 'a1.large', 'a1.xlarge', 'a1.2xlarge', 'a1.4xlarge',
    'm5a.large', 'm5a.xlarge', 'm5a.2xlarge', 'm5a.4xlarge', 'm5a.8xlarge',
    'm5a.12xlarge', 'm5a.16xlarge', 'm5a.24xlarge',
    'r5a.large', 'r5a.xlarge', 'r5a.2xlarge', 'r5a.4xlarge', 'r5a.8xlarge',
    'r5a.12xlarge', 'r5a.16xlarge', 'r5a.24xlarge',
    'c5a.large', 'c5a.xlarge', 'c5a.2xlarge', 'c5a.4xlarge', 'c5a.8xlarge',
    'c5a.12xlarge', 'c5a.16xlarge', 'c5a.24xlarge',
    't3a.nano', 't3a.micro', 't3a.small', 't3a.medium', 't3a.large',
    't3a.xlarge', 't3a.2xlarge',
    't4g.nano', 't4g.micro', 't4g.small', 't4g.medium', 't4g.large',
    't4g.xlarge', 't4g.2xlarge',
    'c6g.medium', 'c6g.large', 'c6g.xlarge', 'c6g.2xlarge', 'c6g.4xlarge',
    'c6g.8xlarge', 'c6g.12xlarge', 'c6g.16xlarge',
    'm6g.medium', 'm6g.large', 'm6g.xlarge', 'm6g.2xlarge', 'm6g.4xlarge',
    'm6g.8xlarge', 'm6g.12xlarge', 'm6g.16xlarge',
]

# override previous cfg with an External one
try:
    with open(os.path.join(cwd, 'lib', 'cfgExt.py')) as f:
        exec(f.read())
except FileNotFoundError:
    pass

# Order is VERY important do not CHANGE it!
CFG_TO_FUNC = {
    'MappingClass': {
        'module': 'mappings',
        'func': 'Mappings'},
    'Parameter': {
        'module': 'cloudformation',
        'func': 'CFM_Parameters'},
    'Condition': {
        'module': 'cloudformation',
        'func': 'CFM_Conditions'},
    'Mapping': {
        'module': 'cloudformation',
        'func': 'CFM_Mappings'},
    # SecurityGroups need to stay here because it populate a cfg value
    # [cfg.SecurityGroupsImport] used later by other keys/modules
    'SecurityGroups': {
        'module': 'securitygroup',
        'func': 'SG_SecurityGroups'},
    'AutoScalingGroup': {
        'module': 'autoscaling',
        'func': 'AS_Autoscaling'},
    'ScheduledAction': {
        'module': 'joker',
        'func': ('autoscaling', 'ScheduledAction')},
    'ScalableTarget': {
        'module': 'autoscaling',
        'func': 'AS_ScalableTarget'},
    'AutoScalingScalingPolicy': {
        'module': 'autoscaling',
        'func': 'AS_ScalingPolicies'},
    'ApplicationAutoScalingScalingPolicy': {
        'module': 'autoscaling',
        'func': 'AS_ScalingPolicies'},
    'Bucket': {
        'module': 's3',
        'func': 'S3_Buckets'},
    'Certificate': {
        'module': 'joker',
        'func': ('certificatemanager', 'Certificate')},
    'CodeDeployApp': {
        'module': 'codedeploy',
        'func': 'CD_Applications'},
    'Repository': {
        'module': 'ecr',
        'func': 'ECR_Repositories'},
    'ECSCluster': {
        'module': 'joker',
        'func': ('ecs', 'Cluster')},
    'ECSCapacityProvider': {
        'module': 'joker',
        'func': ('ecs', 'CapacityProvider')},
    'ECSClusterCapacityProviderAssociations': {
        'module': 'joker',
        'func': ('ecs', 'ClusterCapacityProviderAssociations')},
    'Service': {
        'module': 'ecs',
        'func': 'ECS_Service'},
    'ApiGatewayAccount': {
        'module': 'apigateway',
        'func': 'AGW_Account'},
    'ApiGatewayDomainName': {
        'module': 'apigateway',
        'func': 'AGW_DomainName'},
    'ApiGatewayRestApi': {
        'module': 'apigateway',
        'func': 'AGW_RestApi'},
    'ApiGatewayBasePathMapping': {
        'module': 'joker',
        'func': ('apigateway', 'BasePathMapping')},
    'ApiGatewayStage': {
        'module': 'apigateway',
        'func': 'AGW_Stages'},
    'ApiGatewayUsagePlan': {
        'module': 'apigateway',
        'func': 'AGW_UsagePlans'},
    'ApiGatewayApiKey': {
        'module': 'apigateway',
        'func': 'AGW_ApiKeys'},
    'LogGroupName': {
        'module': 'logs',
        'func': 'LGS_LogGroup'},
    'TaskDefinition': {
        'module': 'ecs',
        'func': 'ECS_TaskDefinition'},
    'EFSFileSystem': {
        'module': 'efs',
        'func': 'EFS_FileStorage'},
    'EFSAccessPoint': {
        'module': 'joker',
        'func': ('efs', 'AccessPoint')},
    'CacheSubnetGroup': {
        'module': 'elasticache',
        'func': 'CCH_SubnetGroups'},
    'CacheCluster': {
        'module': 'elasticache',
        'func': 'CCH_Cache'},
    'EventsRule': {
        'module': 'events',
        'func': 'EVE_EventRules'},
    'Role': {
        'module': 'iam',
        'func': 'IAM_Roles'},
    'IAMPolicy': {
        'module': 'iam',
        'func': 'IAM_Policies'},
    'IAMUser': {
        'module': 'iam',
        'func': 'IAM_Users'},
    'IAMGroup': {
        'module': 'iam',
        'func': 'IAM_Groups'},
    'IAMUserToGroupAddition': {
        'module': 'iam',
        'func': 'IAM_UserToGroupAdditions'},
    'KMSKey': {
        'module': 'kms',
        'func': 'KMS_Keys'},
    'Lambda': {
        'module': 'lambdas',
        'func': 'LBD_Lambdas'},
    'LambdaLayerVersion': {
        'module': 'lambdas',
        'func': 'LBD_LayerVersions'},
    'LambdaPermission': {
        'module': 'joker',
        'func': ('awslambda', 'Permission')},
    'LambdaEventSourceMapping': {
        'module': 'joker',
        'func': ('awslambda', 'EventSourceMapping')},
    'LambdaEventInvokeConfig': {
        'module': 'joker',
        'func': ('awslambda', 'EventInvokeConfig')},
    'LoadBalancerApplication': {
        'module': 'loadbalancing',
        'func': 'LB_ElasticLoadBalancing'},
    'LoadBalancerClassic': {
        'module': 'loadbalancing',
        'func': 'LB_ElasticLoadBalancing'},
    'Alarm': {
        'module': 'joker',
        'func': ('cloudwatch', 'Alarm')},
    'CloudFrontDistribution': {
        'module': 'cloudfront',
        'func': 'CF_CloudFront'},
    'CloudFrontCachePolicy': {
        'module': 'joker',
        'func': ('cloudfront', 'CachePolicy')},
    'CloudFrontOriginRequestPolicy': {
        'module': 'joker',
        'func': ('cloudfront', 'OriginRequestPolicy')},
    'SNSSubscription': {
        'module': 'sns',
        'func': 'SNS_Subscriptions'},
    'SNSTopic': {
        'module': 'sns',
        'func': 'SNS_Topics'},
    'SQSQueue': {
        'module': 'joker',
        'func': ('sqs', 'Queue')},
    'ASGLifecycleHook': {
        'module': 'joker',
        'func': ('autoscaling', 'LifecycleHook')},
    'DBInstance': {
        'module': 'rds',
        'func': 'RDS_DB'},
    'DBSubnetGroup': {
        'module': 'rds',
        'func': 'RDS_SubnetGroups'},
    'HostedZone': {
        'module': 'route53',
        'func': 'R53_HostedZones'},
    'R53RecordSet': {
        'module': 'route53',
        'func': 'R53_RecordSets'},
    'WafByteMatchSet': {
        'module': 'waf',
        'func': ['WAF_GlobalByteMatchSets', 'WAF_RegionalByteMatchSets']},
    'WafIPSet': {
        'module': 'waf',
        'func': ['WAF_GlobalIPSets', 'WAF_RegionalIPSets']},
    'WafRule': {
        'module': 'waf',
        'func': ['WAF_GlobalRules', 'WAF_RegionalRules']},
    'WafWebAcl': {
        'module': 'waf',
        'func': ['WAF_GlobalWebAcls', 'WAF_RegionalWebAcls']},
    'ServiceDiscoveryPublicDnsNamespace': {
        'module': 'joker',
        'func': ('servicediscovery', 'PublicDnsNamespace')},
    'ServiceDiscoveryService': {
        'module': 'joker',
        'func': ('servicediscovery', 'Service')},
    'VPCEndpoint': {
        'module': 'vpc',
        'func': 'VPC_Endpoint'},
    'SecurityGroup': {
        'module': 'securitygroup',
        'func': 'SG_SecurityGroup'},
    'SecurityGroupIngress': {
        'module': 'securitygroup',
        'func': 'SG_SecurityGroupIngresses'},
    'VPC': {
        'module': 'vpc',
        'func': 'VPC_VPC'},
    'CCRLightHouse': {
        'module': 'cloudformation',
        'func': 'CFM_CustomResourceLightHouse'},
    'CCRFargateSpot': {
        'module': 'cloudformation',
        'func': 'CFM_CustomResourceFargateSpot'},
    # ReplicateRegions need to stay here
    'CCRReplicateRegions': {
        'module': 'cloudformation',
        'func': 'CFM_CustomResourceReplicator'},
    # Output need to be last line
    'Output': {
        'module': 'cloudformation',
        'func': 'CFM_Outputs'},
}
