import troposphere.dynamodb as ddb

from .common import *
from .shared import (Parameter, get_endvalue, get_expvalue, get_subvalue,
                     auto_get_props, get_condition, add_obj)


class DDBTableCredStash(ddb.Table):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        self.AttributeDefinitions = [
            ddb.AttributeDefinition(
                AttributeName='name',
                AttributeType='S'
            ),
            ddb.AttributeDefinition(
                AttributeName='version',
                AttributeType='S'
            )
        ]
        self.KeySchema = [
            ddb.KeySchema(
                AttributeName='name',
                KeyType='HASH'
            ),
            ddb.KeySchema(
                AttributeName='version',
                KeyType='RANGE'
            )
        ]
        self.ProvisionedThroughput = ddb.ProvisionedThroughput(
            ReadCapacityUnits=1,
            WriteCapacityUnits=1
        )
        self.TableName = Sub('credential-store-${EnvShort}')
