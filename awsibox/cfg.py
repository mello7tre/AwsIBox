from collections import OrderedDict, Mapping

from troposphere import (
    Template,
    Parameter,
    GetAtt,
    Ref,
    Join,
    If,
    FindInMap,
    ImportValue,
    Sub,
    Split,
)

mappedvalue = {}
no_override = False
envrole = ''
stacktype = ''
classenvrole = ''
template = Template()
RP_cmm = {}
mappings = {}
brand = ''
debug = False
RP = {}


Parameters = []
Parameters_Override = []
Conditions = []
Resources = []
Outputs = []

MAX_SECURITY_GROUPS = 4
# SECURITY_GROUPS_DEFAULT equals list of empty values (Ex. for "MAX_SECURITY_GROUPS = 3" we have "SECURITY_GROUPS_DEFAULT = ',,'")
SECURITY_GROUPS_DEFAULT = reduce(lambda a, i: ',' + str(a), range(MAX_SECURITY_GROUPS - 1), '')

RP_base = OrderedDict([
    ('cmm', {
        'cmm': {},
    }),
    ('dev', {
        'eu-west-1': {},
        'us-east-1': {},
    }),
    ('stg', {
        'eu-west-1': {},
        'us-east-1': {},
    }),
    ('prd', {
        'eu-west-1': {},
        'us-east-1': {},
        'eu-central-1': {},
    }),
])

IMPORT_MODULES = [
    'lambdas',
    'securitygroup',
    'cloudwatch',
    'loadbalancing',
    'autoscaling',
    'iam',
    'codedeploy',
    'route53',
    'certificates',
    'events',
    'cloudfront',
    'queue',
    'notification',
    'containers',
    'buckets',
    'waf',
    'vpc',
    'dynamodb',
    'kms',
    'rds',
    'efs',
    'elasticache',
    'servicediscovery',
    'cloudformation',
    'logs',
    'apigateway',
]

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
    'get_exported_value(',
    'Sub(',
    'Ref(',
    'get_sub_mapex(',
    'GetAtt(',
    'get_final_value(',
    'Split(',
    'Export(',
    'Join(',
    'If(',
    'dict(',
    'eval(',
    'Tags(',
)

CFG_TO_CLASS = OrderedDict([
    ('Parameter', 'CFM_Parameters'),
    ('Condition', 'CFM_Conditions'),
    ('Output', 'CFM_Outputs'),
    ('CapacityDesired' , 'AS_Autoscaling'),
    ('ScalingPolicyUpScalingAdjustment1', 'AS_ScalingPoliciesStep'),
    ('ScalingPolicyTrackings', 'AS_ScalingPoliciesTracking'),
    ('Bucket', 'S3_Buckets'),
    ('BucketPolicy', 'S3_BucketPolicies'),
    ('Certificate', 'CRM_Certificate'),
    ('CodeDeployApp', 'CD_Applications'),
    ('Repository', 'ECR_Repositories'),
    ('Cluster', 'ECS_Cluster'),
    ('Service', 'ECS_Service'),
    ('ApiGatewayResource', 'AGW_RestApi'),
    ('ApiGatewayStage', 'AGW_Stages'),
    ('LogGroupName', 'LGS_LogGroup'),
    ('ContainerDefinitions', 'ECS_TaskDefinition'),
    ('EFSFileSystem', 'EFS_FileStorage'),
    ('CacheSubnetGroup', 'CCH_SubnetGroups'),
    ('CacheNodeType', 'CCH_Cache'),
    ('EventsRule', 'EVE_EventRules'),
    ('Role', 'IAM_Roles'),
    ('IAMPolicy', 'IAM_Policies'),
    ('IAMUser', 'IAM_Users'),
    ('IAMGroup', 'IAM_Groups'),
    ('KMSKey', 'KMS_Keys'),
    ('Lambda', 'LBD_Lambdas'),
    ('LoadBalancerApplication', 'LB_ElasticLoadBalancing'),
    ('LoadBalancerClassic', 'LB_ElasticLoadBalancing'),
    ('Alarm', 'CW_Alarms'),
    ('CloudFront', 'CF_CloudFront'),
    ('SNSSubscription', 'SNS_Subscriptions'),
    ('SNSTopic', 'SNS_Topics'),
    ('SQSQueue', 'SQS_Queues'),
    ('ASGLifecycleHook', 'AS_LifecycleHook'),
    ('DBInstanceClass', 'RDS_DB'),
    ('DBParameterGroup', 'RDS_ParameterGroups'),
    ('DBSubnetGroup', 'RDS_SubnetGroups'),
    ('HostedZoneEnv', 'R53_HostedZones'),
    ('WafByteMatchSet', ['WAF_GlobalByteMatchSets', 'WAF_RegionalByteMatchSets']),
    ('WafIPSet', ['WAF_GlobalIPSets', 'WAF_RegionalIPSets']),
    ('WafRule', ['WAF_GlobalRules', 'WAF_RegionalRules']),
    ('WafWebAcl', ['WAF_GlobalWebAcls', 'WAF_RegionalWebAcls']),
    ('ServiceDiscovery', 'SRVD_ServiceDiscovery'),
    ('VPCEndpoint', 'VPC_Endpoint'),
    ('SecurityGroupBase', 'SG_SecurityGroup'),
    ('SecurityGroupIngress', 'SG_SecurityGroupIngressesExtra'),
])
