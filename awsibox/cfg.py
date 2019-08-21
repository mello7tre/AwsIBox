import os
from collections import OrderedDict, Mapping

no_override = False

Parameters = []
Parameters_Override = []
Conditions = []
Mappings = []
Resources = []
Outputs = []

PATH_INT = '%s/cfg' % os.path.dirname(os.path.realpath(__file__))
PATH_INT = os.path.normpath(PATH_INT)

PATH_EXT = '%s/cfg' % os.getcwd()
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

PARAMETERS_SKIP_OVERRIDE_CONDITION = (
    'Env',
    'UpdateMode',
    'RecordSetExternal',
    'DoNotSignal',
    'EfsMounts',
    'SecurityGroups',
    'ImageIdLatest',
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

CFG_TO_CLASS = OrderedDict([
    ('Parameter', {'module': 'cloudformation', 'class': 'CFM_Parameters'}),
    ('Condition', {'module': 'cloudformation', 'class': 'CFM_Conditions'}),
    ('Mapping', {'module': 'cloudformation', 'class': 'CFM_Mappings'}),
    ('Output', {'module': 'cloudformation', 'class': 'CFM_Outputs'}),
    ('CapacityDesired', {'module': 'autoscaling', 'class': 'AS_Autoscaling'}),
    ('ScalingPolicyUpScalingAdjustment1', {'module': 'autoscaling', 'class': 'AS_ScalingPoliciesStep'}),
    ('ScalingPolicyTrackings', {'module': 'autoscaling', 'class': 'AS_ScalingPoliciesTracking'}),
    ('Bucket', {'module': 'buckets', 'class': 'S3_Buckets'}),
    ('BucketPolicy', {'module': 'buckets', 'class': 'S3_BucketPolicies'}),
    ('Certificate', {'module': 'certificates', 'class': 'CRM_Certificate'}),
    ('CodeDeployApp', {'module': 'codedeploy', 'class': 'CD_Applications'}),
    ('Repository', {'module': 'containers', 'class': 'ECR_Repositories'}),
    ('Cluster', {'module': 'containers', 'class': 'ECS_Cluster'}),
    ('Service', {'module': 'containers', 'class': 'ECS_Service'}),
    ('ApiGatewayResource', {'module': 'apigateway', 'class': 'AGW_RestApi'}),
    ('ApiGatewayStage', {'module': 'apigateway', 'class': 'AGW_Stages'}),
    ('LogGroupName', {'module': 'logs', 'class': 'LGS_LogGroup'}),
    ('ContainerDefinitions', {'module': 'containers', 'class': 'ECS_TaskDefinition'}),
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
])
