import troposphere.iam as iam

from shared import *


# S - IAM #
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
        self.Condition = name
        self.GroupName = Ref(name)


class IAMPolicy(iam.PolicyType):
    def setup(self, key, name):
        auto_get_props(self, key)
        self.PolicyDocument = {
            'Version': '2012-10-17',
        }
        self.PolicyName = name


class IAMManagedPolicy(iam.ManagedPolicy):
    def setup(self, key, name):
        auto_get_props(self, key)
        self.PolicyDocument = {
            'Version': '2012-10-17',
        }
        self.Description = key['Description']


class IAMPolicyBucketReplica(iam.PolicyType):
    def setup(self, bucket, key):
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
                        Sub('arn:aws:s3:::%s' % RP_cmm[bucket])
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
                        Sub('arn:aws:s3:::%s/*' % RP_cmm[bucket]) 
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
                        get_sub_mapex(
                            'arn:aws:s3:::${1M} + /*', '%sReplicaDstBucket' % bucket
                        ) if 'ReplicaDstBucket' in key else get_sub_mapex(
                            'arn:aws:s3:::${1M}-%s/*' % RP_cmm[bucket].replace('${AWS::Region}-', '', 1),
                            '%sReplicaDstRegion' % bucket,
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


class IAMRole(iam.Role):
    def setup(self, key):
        auto_get_props(self, key)
        self.AssumeRolePolicyDocument = {
            'Statement': [{
                'Action': 'sts:AssumeRole',
                'Effect': 'Allow',
                'Principal': { 'Service': [key['Principal']] },
            }]
        }
        self.Path = '/'


class IAMRoleLambdaBase(iam.Role):
    def setup(self, key):
        self.Path = '/'
        self.ManagedPolicyArns = [
            'arn:aws:iam::aws:policy/AmazonEC2ReadOnlyAccess',
            'arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole'
        ]
        if 'RoleManagedPolicyArns' in key:
            self.ManagedPolicyArns.extend(get_final_value('RoleManagedPolicyArns', mappedvalue=key))
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


# E - IAM #

# ############################################
# ### START STACK META CLASSES AND METHODS ###
# ############################################

def IAMPolicyStatement(key):
    Statement = {
        'Effect': key['Effect'] if 'Effect' in key else 'Allow',
    }

    for k in ['Action', 'NotAction', 'Resource', 'NotResource', 'Condition']:
        if k in key:
            Statement.update({k: get_final_value(k, mappedvalue=key)})

    return Statement

# #################################
# ### START STACK INFRA CLASSES ###
# #################################

class IAM_Users(object):
    def __init__(self, key):
        for n, v in RP_cmm[key].iteritems():
            resname = key + n  # Ex. IAMUserPincoPalla

            # parameters
            p_Password = Parameter('PasswordBase' + n)
            p_Password.Description = 'Base Password, must be changed at first login'
            p_Password.Default = ''
            p_Password.NoEcho = True

            cfg.Parameters.append(p_Password)

            # conditions
            do_no_override(True)
            c_User = {resname: Not(
                Equals(get_final_value(resname + 'Enabled'), 'None')
            )}
            c_Role = {resname + 'RoleAccount': Not(
                Equals(get_final_value(resname + 'RoleAccount'), 'None')
            )}

            cfg.Conditions.extend([
                c_User,
                c_Role,
            ])
            do_no_override(False)

            ManagedPolicyArns = []
            RoleGroups = []
            if 'RoleGroups' in v:
                for m, w in v['RoleGroups'].iteritems():
                    condname = resname + 'RoleGroups' + m
                    # conditions
                    do_no_override(True)
                    c_RoleGroup = {condname: Not(
                        Equals(get_final_value(condname), 'None')
                    )}
    
                    cfg.Conditions.append(c_RoleGroup)
                    do_no_override(False)
    
                    # resources
                    RoleGroups.append(
                        If(
                            condname,
                            m,
                            Ref('AWS::NoValue')
                        )
                    )
    
                    if m in RP_cmm['IAMGroup']:
                        for p in RP_cmm['IAMGroup'][m]['ManagedPolicyArns']:
                            ManagedPolicyArns.append(
                                If(
                                    condname,
                                    Ref('IAMPolicy' + p),
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
                'AWS': Sub('arn:aws:iam::${IdAccount}:root', **{'IdAccount': get_final_value(resname + 'RoleAccount')})
            }

            r_User = IAMUser(resname)
            r_User.setup(key=v, name=n)
            r_User.Groups = RoleGroups

            r_SSMParameter = SSMParameter('SSMParameterPassword' + n)
            r_SSMParameter.Condition = resname
            r_SSMParameter.Name = Sub('/iam/PasswordBase/${UserName}', **{'UserName': get_final_value(resname + 'UserName')})
            r_SSMParameter.Value = Ref('PasswordBase' + n)
            r_SSMParameter.AllowedPattern = '^[^ ]{16,}$'

            cfg.Resources.extend([
                r_User,
                r_Role,
                r_SSMParameter,
            ])


class IAM_Groups(object):
    def __init__(self, key):
        for n, v in RP_cmm[key].iteritems():
            resname = key + n  # Ex. IAMGroupBase

            # conditions
            do_no_override(True)
            c_Group = {resname: Not(
                Equals(get_final_value(resname + 'Enabled'), 'None')
            )}
            cfg.Conditions.append(c_Group)
            do_no_override(False)

            ManagedPolicyArns = []
            for m in v['ManagedPolicyArns']:
                if m.startswith('arn'):
                    ManagedPolicyArns.append(m)
                else:
                    ManagedPolicyArns.append(Ref('IAMPolicy' + m))

            Users = []
            for m, w in v['User'].iteritems():
                condname = resname + 'User' + str(m)
                # conditions
                do_no_override(True)
                c_User = {condname: Not(
                    Equals(get_final_value(condname), 'None') 
                )}
                cfg.Conditions.append(c_User)
                do_no_override(False)

                Users.append(
                    If(
                        condname,
                        Ref('IAMUser' + m) if m in RP_cmm['IAMUser'] else get_final_value(condname),
                        Ref('AWS::NoValue')
                    )
                )

            # resources
            r_Group = IAMGroup(resname)
            r_Group.setup(key=v, name=n)
            r_Group.ManagedPolicyArns = ManagedPolicyArns

            r_GroupAdd = IAMUserToGroupAddition('IAMUserToGroupAddition' + n)
            r_GroupAdd.setup(key=v, name=resname)
            r_GroupAdd.Users = Users

            cfg.Resources.extend([
                r_Group,
                r_GroupAdd,
            ])


class IAM_Policies(object):
    def __init__(self, key):
        # Resources
        for n, v in RP_cmm[key].iteritems():
            resname = key + n  # Ex. IAMPolicyLambdaR53RecordInstanceId
            Statement = []
            for m, w  in v['Statement'].iteritems():
                Statement.append(IAMPolicyStatement(w))

            if 'Type' in v and v['Type'] == 'Managed':
                r_Policy = IAMManagedPolicy(resname)
            else:
                r_Policy = IAMPolicy(resname)
            r_Policy.setup(key=v, name=n)
            r_Policy.PolicyDocument['Statement'] = Statement

            cfg.Resources.append(r_Policy)

            # outputs
            if 'Export' in v:
                o_Policy = Output(resname)
                o_Policy.Value = Ref(resname)
                o_Policy.Export = Export(resname)

                cfg.Outputs.append(o_Policy)


class IAM_Roles(object):
    def __init__(self, key):
        # Resources
        for n, v in RP_cmm[key].iteritems():
            resname = key + n  # Ex. RoleECSService
            r_Role = IAMRole(resname)
            r_Role.setup(key=v)

            cfg.Resources.append(r_Role)

            # outputs
            if 'Export' in v:
                o_Role = Output(resname)
                o_Role.Value = GetAtt(resname, 'Arn')
                o_Role.Export = Export(resname)

                cfg.Outputs.append(o_Role)

# Need to stay as last lines
import_modules(globals())
