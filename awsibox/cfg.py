import os
from collections import OrderedDict, Mapping

no_override = False

Parameters = []
Conditions = []
Mappings = []
Resources = []
Outputs = []

PATH_INT = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfg')
PATH_INT = os.path.normpath(PATH_INT)

PATH_EXT = os.path.join(os.getcwd(), 'cfg')
PATH_EXT = os.path.normpath(PATH_EXT)

MAX_SECURITY_GROUPS = 4
# SECURITY_GROUPS_DEFAULT equals list of empty values (Ex. for "MAX_SECURITY_GROUPS = 3" we have "SECURITY_GROUPS_DEFAULT = ',,'")
SECURITY_GROUPS_DEFAULT = reduce(lambda a, i: ',' + str(a), range(MAX_SECURITY_GROUPS - 1), '')

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
    'ImageIdLatest',
    'VPCCidrBlock',
    'VPCName',
)

EVAL_FUNCTIONS_IN_CFG = (
    'cfg.',
    'get_expvalue(',
    'Sub(',
    'Ref(',
    'get_subvalue(',
    'GetAtt(',
    'get_endvalue(',
    'Split(',
    'Export(',
    'Join(',
    'If(',
    'dict(',
    'eval(',
    'Tags(',
)

BASE_CFGS = {
    'Bucket': {
        'Enabled': 'None',
        'Create': 'None',
        'AccountsRO': OrderedDict([
            ('dev', 'None'),
            ('stg', 'None'),
            ('prd', 'None'),
        ]),
        'Cors': 'None',
        'CloudFrontOriginAccessIdentityExtra': OrderedDict([
            ('Dev', 'None'),
            ('Stg', 'None'),
            ('Prd', 'None'),
        ]),
        'ReplicaDstRegion': 'None',
        'ReplicaDstOwner': 'None',
        'ReplicaSrcAccount': 'None',
        'Versioning': 'None',
    }
}

INSTANCE_LIST = [
    'default',
    'i2.xlarge', 'i2.2xlarge', 'i2.4xlarge',
    'd2.xlarge', 'd2.2xlarge', 'd2.4xlarge',
    't2.nano', 't2.micro', 't2.small', 't2.medium', 't2.large', 't2.xlarge', 't2.2xlarge',
    't3.nano', 't3.micro', 't3.small', 't3.medium', 't3.large', 't3.xlarge', 't3.2xlarge',
    'm3.medium', 'm3.large', 'm3.xlarge', 'm3.2xlarge',
    'm4.large', 'm4.xlarge', 'm4.2xlarge', 'm4.4xlarge',
    'm5.large', 'm5.xlarge', 'm5.2xlarge', 'm5.4xlarge',
    'c3.large', 'c3.xlarge', 'c3.2xlarge', 'c3.4xlarge',
    'c4.large', 'c4.xlarge', 'c4.2xlarge', 'c4.4xlarge',
    'c5.large', 'c5.xlarge', 'c5.2xlarge', 'c5.4xlarge',
    'r3.large', 'r3.xlarge', 'r3.2xlarge', 'r3.4xlarge',
    'r4.large', 'r4.xlarge', 'r4.2xlarge', 'r4.4xlarge',
    'r5.large', 'r5.xlarge', 'r5.2xlarge', 'r5.4xlarge',
    'g2.2xlarge', 'g3s.xlarge',
]

CFG_TO_CLASS = OrderedDict([
    ('MappingClass', {'module': 'mappings', 'class': 'Mappings'}),
    ('Parameter', {'module': 'cloudformation', 'class': 'CFM_Parameters'}),
    ('Condition', {'module': 'cloudformation', 'class': 'CFM_Conditions'}),
    ('Mapping', {'module': 'cloudformation', 'class': 'CFM_Mappings'}),
    ('Output', {'module': 'cloudformation', 'class': 'CFM_Outputs'}),
    ('CapacityDesired', {'module': 'autoscaling', 'class': 'AS_Autoscaling'}),
    ('ScalingPolicyUpScalingAdjustment1', {'module': 'autoscaling', 'class': 'AS_ScalingPoliciesStep'}),
    ('ScalingPolicyTrackings', {'module': 'autoscaling', 'class': 'AS_ScalingPoliciesTracking'}),
    ('Bucket', {'module': 's3', 'class': 'S3_Buckets'}),
    ('BucketPolicy', {'module': 's3', 'class': 'S3_BucketPolicies'}),
    ('Certificate', {'module': 'crm', 'class': 'CRM_Certificate'}),
    ('CodeDeployApp', {'module': 'codedeploy', 'class': 'CD_Applications'}),
    ('Repository', {'module': 'ecr', 'class': 'ECR_Repositories'}),
    ('Cluster', {'module': 'ecs', 'class': 'ECS_Cluster'}),
    ('Service', {'module': 'ecs', 'class': 'ECS_Service'}),
    ('ApiGatewayResource', {'module': 'apigateway', 'class': 'AGW_RestApi'}),
    ('ApiGatewayStage', {'module': 'apigateway', 'class': 'AGW_Stages'}),
    ('LogGroupName', {'module': 'logs', 'class': 'LGS_LogGroup'}),
    ('ContainerDefinitions', {'module': 'ecs', 'class': 'ECS_TaskDefinition'}),
    ('EFSFileSystem', {'module': 'efs', 'class': 'EFS_FileStorage'}),
    ('CacheSubnetGroup', {'module': 'elasticache', 'class': 'CCH_SubnetGroups'}),
    ('CacheNodeType', {'module': 'elasticache', 'class': 'CCH_Cache'}),
    ('EventsRule', {'module': 'events', 'class': 'EVE_EventRules'}),
    ('Role', {'module': 'iam', 'class': 'IAM_Roles'}),
    ('IAMPolicy', {'module': 'iam', 'class': 'IAM_Policies'}),
    ('IAMUser', {'module': 'iam', 'class': 'IAM_Users'}),
    ('IAMGroup', {'module': 'iam', 'class': 'IAM_Groups'}),
    ('IAMUserToGroupAddition', {'module': 'iam', 'class': 'IAM_UserToGroupAdditions'}),
    ('KMSKey', {'module': 'kms', 'class': 'KMS_Keys'}),
    ('Lambda', {'module': 'lambdas', 'class': 'LBD_Lambdas'}),
    ('LoadBalancerApplication', {'module': 'loadbalancing', 'class': 'LB_ElasticLoadBalancing'}),
    ('LoadBalancerClassic', {'module': 'loadbalancing', 'class': 'LB_ElasticLoadBalancing'}),
    ('Alarm', {'module': 'cloudwatch', 'class': 'CW_Alarms'}),
    ('CloudFront', {'module': 'cloudfront', 'class': 'CF_CloudFront'}),
    ('SNSSubscription', {'module': 'sns', 'class': 'SNS_Subscriptions'}),
    ('SNSTopic', {'module': 'sns', 'class': 'SNS_Topics'}),
    ('SQSQueue', {'module': 'sqs', 'class': 'SQS_Queues'}),
    ('ASGLifecycleHook', {'module': 'autoscaling', 'class': 'AS_LifecycleHook'}),
    ('DBInstanceClass', {'module': 'rds', 'class': 'RDS_DB'}),
    ('DBParameterGroup', {'module': 'rds', 'class': 'RDS_ParameterGroups'}),
    ('DBSubnetGroup', {'module': 'rds', 'class': 'RDS_SubnetGroups'}),
    ('HostedZoneEnv', {'module': 'route53', 'class': 'R53_HostedZones'}),
    ('WafByteMatchSet', {'module': 'waf', 'class': ['WAF_GlobalByteMatchSets', 'WAF_RegionalByteMatchSets']}),
    ('WafIPSet', {'module': 'waf', 'class': ['WAF_GlobalIPSets', 'WAF_RegionalIPSets']}),
    ('WafRule', {'module': 'waf', 'class': ['WAF_GlobalRules', 'WAF_RegionalRules']}),
    ('WafWebAcl', {'module': 'waf', 'class': ['WAF_GlobalWebAcls', 'WAF_RegionalWebAcls']}),
    ('ServiceDiscovery', {'module': 'servicediscovery', 'class': 'SRVD_ServiceDiscovery'}),
    ('VPCEndpoint', {'module': 'vpc', 'class': 'VPC_Endpoint'}),
    ('SecurityGroupBase', {'module': 'securitygroup', 'class': 'SG_SecurityGroup'}),
    ('SecurityGroupIngress', {'module': 'securitygroup', 'class': 'SG_SecurityGroupIngressesExtra'}),
    ('VPC', {'module': 'vpc', 'class': 'VPC_VPC'}),
])
