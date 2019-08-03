import troposphere.dynamodb as ddb

from shared import *


class DDBTableCredStash(ddb.Table):
    def setup(self):
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

# Need to stay as last lines
import_modules(globals())
