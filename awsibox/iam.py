import troposphere.iam as iam

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
    get_subvalue, auto_get_props, get_condition, add_obj, SSMParameter)


class IAMUser(iam.User):
    def setup(self, key, name):
        self.Condition = self.title
        self.UserName = key['UserName']
        self.LoginProfile = iam.LoginProfile(
            Password=GetAtt('SSMParameterPassword' + name, 'Value'),
            PasswordResetRequired=True
        )


class IAMGroup(iam.Group):
    def setup(self, key, name):
        self.Condition = self.title
        self.GroupName = name


class IAMUserToGroupAddition(iam.UserToGroupAddition):
    def setup(self, key, name):
        # self.Condition = name
        self.GroupName = name


class IAMPolicy(iam.PolicyType):
    def setup(self, key, name):
        self.PolicyName = name
        auto_get_props(self, key)
        self.PolicyDocument = {
            'Version': '2012-10-17',
        }


class IAMManagedPolicy(iam.ManagedPolicy):
    def setup(self, key, name):
        auto_get_props(self, key)
        self.PolicyDocument = {
            'Version': '2012-10-17',
        }
        self.Description = key['Description']


class IAMPolicyBucketReplica(iam.PolicyType):
    def setup(self, bucket, bucket_name, key):
        name = self.title  # Ex. IAMPolicyReplicaBucketElasticSearch
        self.Condition = bucket + 'Replica'
        self.PolicyName = self.title
        self.PolicyDocument = {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': [
                        's3:GetReplicationConfiguration',
                        's3:ListBucket'
                    ],
                    'Effect': 'Allow',
                    'Resource': [
                        Sub('arn:aws:s3:::%s' % bucket_name)
                    ]
                },
                {
                    'Action': [
                        's3:GetObjectVersion',
                        's3:GetObjectVersionAcl',
                        's3:GetObjectVersionTagging',
                    ],
                    'Effect': 'Allow',
                    'Resource': [
                        Sub('arn:aws:s3:::%s/*' % bucket_name) 
                    ]
                },
                {
                    'Action': [
                        's3:ReplicateObject',
                        's3:ReplicateDelete',
                        's3:ReplicateTags',
                        's3:ObjectOwnerOverrideToBucketOwner',
                    ],
                    'Effect': 'Allow',
                    'Resource': [
                        get_subvalue(
                            'arn:aws:s3:::${1M}/*',
                            bucket + 'ReplicaDstBucket'
                        ) if 'ReplicaDstBucket' in key else get_subvalue(
                            'arn:aws:s3:::${1M}-%s/*' % bucket_name.replace('${AWS::Region}-', '', 1),
                            bucket + 'ReplicaDstRegion',
                        )
                    ]
                }
            ]
        }
        self.Roles = [
            Ref('Role' + self.Condition)  # Ex. RoleBucketImagesReplica
        ]


class IAMInstanceProfile(iam.InstanceProfile):
    def setup(self):
        self.Path = '/'
        self.Roles=[
            Ref('RoleInstance')
        ]


class IAMRoleIBox(iam.Role):
    def setup(self):
        # Trick to add a policy from cfg/yml to a role created from code (Ex. LambdaRoles)
        try:
            cfg.IAMPolicyInRole
        except:
            pass
        else:
            for n, v in cfg.IAMPolicyInRole.items():
                if self.title.endswith(n):
                    self.Policies = [
                        IAMPolicyInRole(n, v)
                    ]
                    break


class IAMRole(iam.Role):
    def setup(self, key):
        auto_get_props(self, key)
        self.AssumeRolePolicyDocument = {
            'Statement': [{
                'Action': 'sts:AssumeRole',
                'Effect': 'Allow',
                'Principal': {
                    key['PrincipalType'] if 'PrincipalType' in key else 'Service': [get_endvalue(self.title + 'Principal')]
                },
            }]
        }
        self.Path = '/'


class IAMRoleLambdaBase(IAMRoleIBox):
    def setup(self, key):
        super(IAMRoleLambdaBase, self).setup()
        self.Path = '/'
        self.ManagedPolicyArns = [
            'arn:aws:iam::aws:policy/AmazonEC2ReadOnlyAccess',
            'arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole'
        ]
        if 'RoleManagedPolicyArns' in key:
            self.ManagedPolicyArns.extend(get_endvalue('RoleManagedPolicyArns', fixedvalues=key))
        self.AssumeRolePolicyDocument = {
            'Statement': [{
                'Action': 'sts:AssumeRole',
                'Principal': {'Service': [
                    'lambda.amazonaws.com',
                    'edgelambda.amazonaws.com' if 'AtEdge' in key else Ref('AWS::NoValue')
                ]},
                'Effect': 'Allow'
            }]
        }


class IAMRoleBucketReplica(iam.Role):
    def setup(self):
        self.Condition = self.title.replace('Role','')  # Ex. BucketPortalStaticReplica
        self.Path = '/'
        self.AssumeRolePolicyDocument = {
            'Statement': [{
                'Action': 'sts:AssumeRole',
                'Effect': 'Allow',
                'Principal': {'Service': ['s3.amazonaws.com']},
            }],
            'Version': '2012-10-17'
        }


# ############################################
# ### START STACK META CLASSES AND METHODS ###
# ############################################


def IAMPolicyInRole(name, key):
    Policy = iam.Policy('')
    Policy.PolicyName = name
    Policy.PolicyDocument = {
            'Version': '2012-10-17',
            }
    Statement = []
    for n, v in key['Statement'].items():
        Statement.append(IAMPolicyStatement(v))
    Policy.PolicyDocument['Statement'] = Statement

    return Policy


def IAMPolicyStatement(key):
    Statement = {
        'Effect': key['Effect'] if 'Effect' in key else 'Allow',
    }

    for k in ['Action', 'NotAction', 'Resource', 'NotResource', 'Condition']:
        if k in key:
            Statement.update({k: get_endvalue(k, fixedvalues=key)})

    return Statement

# #################################
# ### START STACK INFRA CLASSES ###
# #################################

class IAM_Users(object):
    def __init__(self, key):
        for n, v in getattr(cfg, key).items():
            resname = key + n  # Ex. IAMUserPincoPalla

            # parameters
            p_Password = Parameter('PasswordBase' + n)
            p_Password.Description = 'Base Password, must be changed at first login'
            p_Password.Default = ''
            p_Password.NoEcho = True

            add_obj(p_Password)

            # conditions
            add_obj([
                get_condition(resname, 'not_equals', 'None', resname + 'Enabled'),
                get_condition(resname + 'RoleAccount', 'not_equals', 'None'),
            ])

            ManagedPolicyArns = []
            RoleGroups = []
            if 'RoleGroups' in v:
                for m, w in v['RoleGroups'].items():
                    condname = resname + 'RoleGroups' + m
                    # conditions
                    add_obj(get_condition(condname, 'not_equals', 'None'))
    
                    # resources
                    RoleGroups.append(
                        If(
                            condname,
                            m,
                            Ref('AWS::NoValue')
                        )
                    )
   
                    try: policy_arns = cfg.IAMGroup[m]['ManagedPolicyArns']
                    except:
                        pass
                    else:
                        for p in policy_arns:
                            ManagedPolicyArns.append(
                                If(
                                    condname,
                                    ImportValue('IAMPolicy' + p),
                                    Ref('AWS::NoValue')
                                )
                            )

            # resources
            r_Role = IAMRole('IAMRole' + n)
            r_Role.setup(key={'Principal': ''})
            r_Role.Condition = resname + 'RoleAccount'
            r_Role.RoleName = v['UserName']
            r_Role.MaxSessionDuration = 43200
            r_Role.ManagedPolicyArns = ManagedPolicyArns
            AssumeRoleStatement = r_Role.AssumeRolePolicyDocument['Statement'][0]
            AssumeRoleStatement['Condition'] = {
                'StringEquals': {'aws:username': v['UserName']}
            }
            AssumeRoleStatement['Principal'] = {
                'AWS': Sub('arn:aws:iam::${IdAccount}:root', **{'IdAccount': get_endvalue(resname + 'RoleAccount')})
            }

            r_User = IAMUser(resname)
            r_User.setup(key=v, name=n)
            r_User.Groups = RoleGroups

            r_SSMParameter = SSMParameter('SSMParameterPassword' + n)
            r_SSMParameter.Condition = resname
            r_SSMParameter.Name = Sub('/iam/PasswordBase/${UserName}', **{'UserName': get_endvalue(resname + 'UserName')})
            r_SSMParameter.Value = Ref('PasswordBase' + n)
            r_SSMParameter.AllowedPattern = '^[^ ]{16,}$'

            add_obj([
                r_User,
                r_Role,
                r_SSMParameter,
            ])


class IAM_UserToGroupAdditions(object):
    def __init__(self, key):
        for n, v in getattr(cfg, key).items():
            resname = key + n  # Ex. IAMUserToGroupAdditionBase

            Users = []
            for m, w in v['User'].items():
                condname = '%sUser%s' % (resname, m)
                # conditions
                add_obj(get_condition(condname, 'not_equals', 'None'))

                Users.append(
                    If(
                        condname,
                        # for user defined in the same yaml file
                        # Ref('IAMUser' + m) if m in cfg.IAMUser else get_endvalue(condname),
                        get_endvalue(condname),
                        Ref('AWS::NoValue')
                    )
                )


            # resources
            r_GroupAdd = IAMUserToGroupAddition('IAMUserToGroupAddition' + n)
            r_GroupAdd.setup(key=v, name=n)
            r_GroupAdd.Users = Users

            add_obj([
                r_GroupAdd,
            ])



class IAM_Groups(object):
    def __init__(self, key):
        for n, v in getattr(cfg, key).items():
            resname = key + n  # Ex. IAMGroupBase

            # conditions
            add_obj(get_condition(resname, 'not_equals', 'None', resname + 'Enabled'))

            ManagedPolicyArns = []
            for m in v['ManagedPolicyArns']:
                if m.startswith('arn'):
                    ManagedPolicyArns.append(m)
                elif m.startswith('Ref('):
                    ManagedPolicyArns.append(eval(m))
                else:
                    ManagedPolicyArns.append(ImportValue('IAMPolicy' + m))


            # resources
            r_Group = IAMGroup(resname)
            r_Group.setup(key=v, name=n)
            r_Group.ManagedPolicyArns = ManagedPolicyArns

            add_obj([
                r_Group,
            ])


class IAM_Policies(object):
    def __init__(self, key):
        # Resources
        for n, v in getattr(cfg, key).items():
            resname = key + n  # Ex. IAMPolicyLambdaR53RecordInstanceId
            Statement = []
            for m, w  in v['Statement'].items():
                Statement.append(IAMPolicyStatement(w))

            if 'Type' in v and v['Type'] == 'Managed':
                r_Policy = IAMManagedPolicy(resname)
            else:
                r_Policy = IAMPolicy(resname)
            r_Policy.setup(key=v, name=n)
            r_Policy.PolicyDocument['Statement'] = Statement

            add_obj(r_Policy)

            # outputs
            if 'Export' in v:
                o_Policy = Output(resname)
                o_Policy.Value = Ref(resname)
                o_Policy.Export = Export(resname)

                add_obj(o_Policy)


class IAM_Roles(object):
    def __init__(self, key):
        # Resources
        for n, v in getattr(cfg, key).items():
            resname = key + n  # Ex. RoleECSService
            r_Role = IAMRole(resname)
            r_Role.setup(key=v)

            # Add embedded policies if present 
            if 'Policies' in v:
                Policies = []
                for p, w in v['Policies'].items():
                    Policies.append(IAMPolicyInRole(p,w))
                r_Role.Policies = Policies

            add_obj(r_Role)

            # outputs
            if 'Export' in v:
                o_Role = Output(resname)
                o_Role.Value = GetAtt(resname, 'Arn')
                o_Role.Export = Export(resname)
                if 'Condition' in v:
                    o_Role.Condition = v['Condition']

                add_obj(o_Role)
