import troposphere.iam as iam

from .common import *
from .shared import (Parameter, get_endvalue, get_expvalue, get_subvalue,
                     auto_get_props, get_condition, add_obj, SSMParameter)


class IAMUser(iam.User):
    def __init__(self, title, key, name, **kwargs):
        super().__init__(title, **kwargs)

        self.Condition = self.title
        self.UserName = key['UserName']
        self.LoginProfile = iam.LoginProfile(
            Password=GetAtt(f'SSMParameterPassword{name}', 'Value'),
            PasswordResetRequired=True
        )


class IAMGroup(iam.Group):
    def __init__(self, title, key, name, **kwargs):
        super().__init__(title, **kwargs)

        self.Condition = self.title
        self.GroupName = name


class IAMUserToGroupAddition(iam.UserToGroupAddition):
    def __init__(self, title, key, name, **kwargs):
        super().__init__(title, **kwargs)

        # self.Condition = name
        self.GroupName = name


class IAMPolicy(iam.PolicyType):
    def __init__(self, title, key, name, **kwargs):
        super().__init__(title, **kwargs)

        self.PolicyName = name
        auto_get_props(self)
        self.PolicyDocument = {
            'Version': '2012-10-17',
        }


class IAMManagedPolicy(iam.ManagedPolicy):
    def __init__(self, title, key, name, **kwargs):
        super().__init__(title, **kwargs)

        auto_get_props(self)
        self.PolicyDocument = {
            'Version': '2012-10-17',
        }
        self.Description = key['Description']


class IAMPolicyBucketReplica(iam.PolicyType):
    def __init__(self, title, bucket, bucket_name, mapname, key, **kwargs):
        super().__init__(title, **kwargs)

        name = self.title  # Ex. IAMPolicyReplicaBucketElasticSearch
        self.Condition = f'{bucket}Replica'
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
                        Sub(f'arn:aws:s3:::{bucket_name}')
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
                        Sub(f'arn:aws:s3:::{bucket_name}/*')
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
                        If(
                            f'{mapname}{n}DestinationBucket',
                            get_subvalue(
                                '${1M}/*',
                                f'{mapname}{n}DestinationBucket'),
                            Ref('AWS::NoValue')
                        ) for n in key
                    ]
                }
            ]
        }
        self.Roles = [
            Ref(f'Role{self.Condition}')  # Ex. RoleBucketImagesReplica
        ]


class IAMInstanceProfile(iam.InstanceProfile):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.Path = '/'
        self.Roles = [
            Ref('RoleInstance')
        ]


class IAMRoleIBox(iam.Role):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        # Trick to add a policy from cfg/yml
        # to a role created from code (Ex. LambdaRoles)
        try:
            cfg.IAMPolicyInRole
        except Exception:
            pass
        else:
            for n, v in cfg.IAMPolicyInRole.items():
                if self.title.endswith(n):
                    self.Policies = [
                        IAMPolicyInRole(n, v)
                    ]
                    break


class IAMRole(iam.Role):
    def __init__(self, title, key, **kwargs):
        super().__init__(title, **kwargs)
        auto_get_props(self)
        self.AssumeRolePolicyDocument = {
            'Statement': [{
                'Action': 'sts:AssumeRole',
                'Effect': 'Allow',
                'Principal': {
                    key['PrincipalType'] if 'PrincipalType' in key else
                    'Service': [get_endvalue(f'{self.title}Principal')]
                },
            }]
        }
        self.Path = '/'


class IAMRoleUser(iam.Role):
    def __init__(self, title, key, resnameuser, **kwargs):
        super().__init__(title, **kwargs)
        self.Condition = f'{resnameuser}RoleAccount'
        self.RoleName = key['UserName']
        self.MaxSessionDuration = 43200
        self.AssumeRolePolicyDocument = {
            'Statement': [{
                'Action': 'sts:AssumeRole',
                'Condition': {
                    'StringEquals': {'aws:username': key['UserName']}
                },
                'Effect': 'Allow',
                'Principal': {
                    'AWS': Sub('arn:aws:iam::${IdAccount}:root',
                               **{'IdAccount': get_endvalue(
                                   f'{resnameuser}RoleAccount')})},
            }]
        }
        self.Path = '/'


class IAMRoleLambdaBase(IAMRoleIBox):
    def __init__(self, title, key, **kwargs):
        super().__init__(title, **kwargs)

        self.Path = '/'
        self.ManagedPolicyArns = [
            'arn:aws:iam::aws:policy/AmazonEC2ReadOnlyAccess',
            'arn:aws:iam::aws:policy/service-role/'
            'AWSLambdaVPCAccessExecutionRole'
        ]
        if 'RoleManagedPolicyArns' in key:
            self.ManagedPolicyArns.extend(
                get_endvalue('RoleManagedPolicyArns', fixedvalues=key))
        self.AssumeRolePolicyDocument = {
            'Statement': [{
                'Action': 'sts:AssumeRole',
                'Principal': {'Service': [
                    'lambda.amazonaws.com',
                    'edgelambda.amazonaws.com' if 'AtEdge' in key else
                    Ref('AWS::NoValue')
                ]},
                'Effect': 'Allow'
            }]
        }


class IAMRoleBucketReplica(iam.Role):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        self.Condition = self.title.replace('Role', '')
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
    Policy.PolicyDocument = {'Version': '2012-10-17'}
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


def IAMPolicyApiGatewayPrivate():
    policy = {
        'Statement': [{
            'Action': 'execute-api:Invoke',
            'Effect': 'Allow',
            'Principal': '*',
            'Resource': 'execute-api:/*',
        }],
        'Version': '2012-10-17'
    }

    return policy


def IAM_Users(key):
    for n, v in getattr(cfg, key).items():
        resname = f'{key}{n}'  # Ex. IAMUserPincoPalla

        # parameters
        p_Password = Parameter(f'PasswordBase{n}')
        p_Password.Description = (
            'Base Password, must be changed at first login')
        p_Password.Default = ''
        p_Password.NoEcho = True

        add_obj(p_Password)

        # conditions
        c_Enabled = get_condition(
            resname, 'not_equals', 'None', f'{resname}Enabled')

        c_RoleAccount = get_condition(
            f'{resname}RoleAccount', 'not_equals', 'None')

        add_obj([
            c_Enabled,
            c_RoleAccount])

        ManagedPolicyArns = []
        RoleGroups = []
        if 'RoleGroups' in v:
            for m, w in v['RoleGroups'].items():
                condname = f'{resname}RoleGroups{m}'
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

                try:
                    policy_arns = cfg.IAMGroup[m]['ManagedPolicyArns']
                except Exception:
                    pass
                else:
                    for p in policy_arns:
                        ManagedPolicyArns.append(
                            If(
                                condname,
                                ImportValue(f'IAMPolicy{p}'),
                                Ref('AWS::NoValue')
                            )
                        )

        # resources
        r_Role = IAMRoleUser(f'IAMRole{n}', key=v, resnameuser=resname)
        r_Role.ManagedPolicyArns = ManagedPolicyArns

        r_User = IAMUser(resname, key=v, name=n)
        r_User.Groups = RoleGroups

        r_SSMParameter = SSMParameter(f'SSMParameterPassword{n}')
        r_SSMParameter.Condition = resname
        r_SSMParameter.Name = Sub(
            '/iam/PasswordBase/${UserName}',
            **{'UserName': get_endvalue(f'{resname}UserName')})
        r_SSMParameter.Value = Ref(f'PasswordBase{n}')
        r_SSMParameter.AllowedPattern = '^[^ ]{16,}$'

        add_obj([
            r_User,
            r_Role,
            r_SSMParameter])


def IAM_UserToGroupAdditions(key):
    for n, v in getattr(cfg, key).items():
        resname = f'{key}{n}'  # Ex. IAMUserToGroupAdditionBase

        Users = []
        for m, w in v['User'].items():
            condname = f'{resname}User{m}'
            # conditions
            add_obj(get_condition(condname, 'not_equals', 'None'))

            Users.append(
                If(
                    condname,
                    # for user defined in the same yaml file
                    # Ref(f'IAMUser{m}') if m in cfg.IAMUser
                    # else get_endvalue(condname),
                    get_endvalue(condname),
                    Ref('AWS::NoValue')
                )
            )

        # resources
        r_GroupAdd = IAMUserToGroupAddition(
            f'IAMUserToGroupAddition{n}', key=v, name=n)
        r_GroupAdd.Users = Users

        add_obj([
            r_GroupAdd])


def IAM_Groups(key):
    for n, v in getattr(cfg, key).items():
        resname = f'{key}{n}'  # Ex. IAMGroupBase

        # conditions
        c_Enabled = get_condition(
            resname, 'not_equals', 'None', f'{resname}Enabled')
        add_obj(c_Enabled)

        ManagedPolicyArns = []
        for m in v['ManagedPolicyArns']:
            if m.startswith('arn'):
                ManagedPolicyArns.append(m)
            elif m.startswith('Ref('):
                ManagedPolicyArns.append(eval(m))
            else:
                ManagedPolicyArns.append(ImportValue(f'IAMPolicy{m}'))

        # resources
        r_Group = IAMGroup(resname, key=v, name=n)
        r_Group.ManagedPolicyArns = ManagedPolicyArns

        add_obj([
            r_Group])


def IAM_Policies(key):
    # Resources
    for n, v in getattr(cfg, key).items():
        resname = f'{key}{n}'  # Ex. IAMPolicyLambdaR53RecordInstanceId
        Statement = []
        for m, w in v['Statement'].items():
            Statement.append(IAMPolicyStatement(w))

        if 'Type' in v and v['Type'] == 'Managed':
            r_Policy = IAMManagedPolicy(resname, key=v, name=n)
        else:
            r_Policy = IAMPolicy(resname, key=v, name=n)
        r_Policy.PolicyDocument['Statement'] = Statement

        add_obj(r_Policy)

        # outputs
        if v.get('Export'):
            o_Policy = Output(resname)
            o_Policy.Value = Ref(resname)
            o_Policy.Export = Export(resname)

            add_obj(o_Policy)


def IAM_Roles(key):
    # Resources
    for n, v in getattr(cfg, key).items():
        resname = f'{key}{n}'  # Ex. RoleECSService
        r_Role = IAMRole(resname, key=v)

        # Add embedded policies if present
        if 'Policies' in v:
            Policies = []
            for p, w in v['Policies'].items():
                Policies.append(IAMPolicyInRole(p, w))
            r_Role.Policies = Policies

        add_obj(r_Role)

        # outputs
        if v.get('Export'):
            o_Role = Output(resname)
            o_Role.Value = GetAtt(resname, 'Arn')
            o_Role.Export = Export(resname)
            if 'Condition' in v:
                o_Role.Condition = v['Condition']

            add_obj(o_Role)
