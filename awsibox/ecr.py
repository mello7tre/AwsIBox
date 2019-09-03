import troposphere.ecr as ecr

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
    get_subvalue, auto_get_props, get_condition)
from .securitygroup import (SecurityGroupEcsService, SecurityGroupRuleEcsService,
    SG_SecurityGroupsECS)


class ECRRepositories(ecr.Repository):
    def setup(self):
        self.RepositoryName = get_endvalue(self.title)
        self.RepositoryPolicyText = {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': [
                        'ecr:GetDownloadUrlForLayer',
                        'ecr:BatchGetImage',
                        'ecr:BatchCheckLayerAvailability',
                        'ecr:PutImage',
                        'ecr:InitiateLayerUpload',
                        'ecr:UploadLayerPart',
                        'ecr:CompleteLayerUpload',
                        'ecr:ListImages',
                        'ecr:DescribeRepositories',
                        'ecr:DescribeImages'
                    ],
                    'Effect': 'Allow',
                    'Principal': {
                        'AWS': [
                            Sub('arn:aws:iam::${AWS::AccountId}:root')
                        ]
                    },
                    'Sid': 'AllowPushPull'
                },
            ]
        }

# ############################################
# ### START STACK META CLASSES AND METHODS ###
# ############################################

class ECRRepositoryLifecyclePolicy(ecr.LifecyclePolicy):
    def __init__(self, title, **kwargs):
        super(ECRRepositoryLifecyclePolicy, self).__init__(title, **kwargs)
        LifecyclePolicyText = {
            'rules': [
                {
                    'rulePriority': 1,
                    'description': 'Images are sorted on pushed_at_time (desc), images greater than specified count are expired.',
                    'selection': {
                        'tagStatus': 'any',
                        'countType': 'imageCountMoreThan',
                        'countNumber': 9500
                    },
                    'action': {
                        'type': 'expire'
                    }
                }
            ]
        }
        self.LifecyclePolicyText = json.dumps(LifecyclePolicyText)
        self.RegistryId = Ref('AWS::AccountId')


def ECRRepositoryPolicyStatementAccountPull(name):
    policy = {   
        'Action': [
            'ecr:GetDownloadUrlForLayer',
            'ecr:BatchGetImage',
            'ecr:BatchCheckLayerAvailability',
            'ecr:ListImages',
            'ecr:DescribeRepositories',
            'ecr:DescribeImages'
        ],
        'Effect': 'Allow',
        'Principal': {
            'AWS': [
                get_subvalue('arn:aws:iam::${1M}:root', name)
            ]
        },
        'Sid': 'AllowPull'
    }

    return policy


def ECRRepositoryPolicyStatementAccountPush(name):
    policy = {   
        'Action': [
            'ecr:PutImage',
            'ecr:InitiateLayerUpload',
            'ecr:UploadLayerPart',
            'ecr:CompleteLayerUpload',
        ],
        'Effect': 'Allow',
        'Principal': {
            'AWS': [
                get_subvalue('arn:aws:iam::${1M}:root', name)
            ]
        },
        'Sid': 'AllowPush'
    }

    return policy


# ##########################################
# ### END STACK META CLASSES AND METHODS ###
# ##########################################

class ECR_Repositories(object):
    def __init__(self, key):
        PolicyStatementAccounts = []
        for n, v in cfg.EcrAccount.iteritems():
            mapname = 'EcrAccount' + n  + 'Id'  # Ex. EcrAccountPrdId
            # conditions
            do_no_override(True)
            c_Account = {mapname: Not(
                Equals(get_endvalue(mapname), 'None')
            )}

            cfg.Conditions.extend([
                c_Account,
            ])
            do_no_override(False)

            if 'Pull' in v['Policy']:
                PolicyStatementAccount = ECRRepositoryPolicyStatementAccountPull(name=mapname)
                PolicyStatementAccounts.append(
                    If(
                        mapname,
                        PolicyStatementAccount,
                        Ref('AWS::NoValue')
                    )
                )

            if 'Push' in v['Policy']:
                PolicyStatementAccount = ECRRepositoryPolicyStatementAccountPush(name=mapname)
                PolicyStatementAccounts.append(
                    If(
                        mapname,
                        PolicyStatementAccount,
                        Ref('AWS::NoValue')
                    )
                )

        # Resources
        for n, v in getattr(cfg, key).iteritems():
            Repo = ECRRepositories(key + n)  # Ex. RepositoryApiLocationHierarchy
            Repo.setup()
            Repo.RepositoryPolicyText['Statement'].extend(PolicyStatementAccounts)
            Repo.LifecyclePolicy = ECRRepositoryLifecyclePolicy('')

            cfg.Resources.append(Repo)
