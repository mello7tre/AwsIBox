import troposphere.ecr as ecr

from .common import *
from .shared import (Parameter, get_endvalue, get_expvalue, get_subvalue,
                     auto_get_props, get_condition, add_obj)
from .securitygroup import (SecurityGroupEcsService,
                            SecurityGroupRuleEcsService, SG_SecurityGroupsECS)


class ECRRepositories(ecr.Repository):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

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
        super().__init__(title, **kwargs)
        LifecyclePolicyText = {
            'rules': [
                {
                    'action': {
                        'type': 'expire'
                    },
                    'rulePriority': 1,
                    'selection': {
                        'countNumber': 9500,
                        'countType': 'imageCountMoreThan',
                        'tagStatus': 'any',
                    },
                    'description': 'Images are sorted on pushed_at_time '
                    '(desc), images greater than specified count are expired.'
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
            'ecr:BatchCheckLayerAvailability',
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

def ECR_Repositories(key):
    PolicyStatementAccounts = []
    for n, v in cfg.EcrAccount.items():
        mapname = f'EcrAccount{n}Id'  # Ex. EcrAccountPrdId
        # conditions
        add_obj(get_condition(mapname, 'not_equals', 'None'))

        if 'Pull' in v['Policy']:
            PolicyStatementAccount = (
                ECRRepositoryPolicyStatementAccountPull(name=mapname))
            PolicyStatementAccounts.append(
                If(
                    mapname,
                    PolicyStatementAccount,
                    Ref('AWS::NoValue')
                )
            )

        if 'Push' in v['Policy']:
            PolicyStatementAccount = (
                ECRRepositoryPolicyStatementAccountPush(name=mapname))
            PolicyStatementAccounts.append(
                If(
                    mapname,
                    PolicyStatementAccount,
                    Ref('AWS::NoValue')
                )
            )

    # Resources
    for n, v in getattr(cfg, key).items():
        resname = f'{key}{n}'
        Repo = ECRRepositories(resname)
        Repo.RepositoryPolicyText['Statement'].extend(
            PolicyStatementAccounts)
        Repo.LifecyclePolicy = ECRRepositoryLifecyclePolicy('')

        add_obj(Repo)
