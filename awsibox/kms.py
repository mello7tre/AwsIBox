import troposphere.kms as kms

from shared import *


class KMSKey(kms.Key):
    def setup(self):
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
    def setup(self):
        self.AliasName = Sub('alias/parameter_store_key')
        self.TargetKeyId = Ref('KMSKeyParameterStore')

# #################################
# ### START STACK INFRA CLASSES ###
# #################################

class KMS_Keys(object):
    def __init__(self, key):
        # Resources
        R_KeyParameterStore = KMSKey('KMSKeyParameterStore')
        R_KeyParameterStore.setup()
        
        R_AliasParameterStore = KMSAliasParameterStore('KMSAliasParameterStore')
        R_AliasParameterStore.setup()

        cfg.Resources.extend([
            R_KeyParameterStore,
            R_AliasParameterStore,
        ])

        # Outputs
        O_ParameterStore = Output('KeyParameterStore')
        O_ParameterStore.Value = Sub('${KMSKeyParameterStore.Arn}')
        O_ParameterStore.Export = Export('KeyParameterStore')

        cfg.Outputs.extend([
            O_ParameterStore,
        ])

# Need to stay as last lines
import_modules(globals())
