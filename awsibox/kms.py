import troposphere.kms as kms

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
                     get_subvalue, auto_get_props, get_condition, add_obj)


class KMSKey(kms.Key):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.KeyPolicy = {
            'Version': '2012-10-17',
            'Id': 'key-default-1',
            'Statement': [
                {
                    'Action': 'kms:*',
                    'Effect': 'Allow',
                    'Principal': {
                        'AWS': Sub('arn:aws:iam::${AWS::AccountId}:root')
                    },
                    'Resource': '*',
                    'Sid': 'Enable IAM User Permissions'
                },
            ]
        }


class KMSAliasParameterStore(kms.Alias):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.AliasName = Sub('alias/parameter_store_key')
        self.TargetKeyId = Ref('KMSKeyParameterStore')

# #################################
# ### START STACK INFRA CLASSES ###
# #################################


class KMS_Keys(object):
    def __init__(self, key):
        # Resources
        R_KeyParameterStore = KMSKey('KMSKeyParameterStore')

        R_AliasParameterStore = KMSAliasParameterStore(
            'KMSAliasParameterStore')

        add_obj([
            R_KeyParameterStore,
            R_AliasParameterStore,
        ])

        # Outputs
        O_ParameterStore = Output('KeyParameterStore')
        O_ParameterStore.Value = Sub('${KMSKeyParameterStore.Arn}')
        O_ParameterStore.Export = Export('KeyParameterStore')

        add_obj([
            O_ParameterStore,
        ])
