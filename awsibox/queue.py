import troposphere.sqs as sqs

from shared import *


class SQSQueue(sqs.Queue):
    def setup(self):
        self.MessageRetentionPeriod = 360


class SQSQueuePolicy(sqs.QueuePolicy):
    def setup(self, key):
        self.Queues = [
            Sub(
                'https://sqs.${AWS::Region}.amazonaws.com/${AWS::AccountId}/${QueueId}',
                **{'QueueId': Select('5', Split(':', eval(key['Endpoint'])))}
            )
        ]
        self.PolicyDocument = {
            'Version': '2012-10-17',
            'Statement': [
                {   
                    'Action': [
                        'SQS:SendMessage'
                    ],
                    'Condition': {
                        'ArnEquals': {
                            'aws:SourceArn': eval(key['TopicArn'])
                        }
                    },
                    'Effect': 'Allow',
                    'Principal': {
                        'AWS': '*'
                    },
                    'Resource': '*'
                }
            ]
        }

##
##

class SQS_Queues(object):
    def __init__(self, key):
        for n, v in RP_cmm[key].iteritems():
            resname = key + n
            # resources
            r_Queue = SQSQueue(resname)
            r_Queue.setup()

            cfg.Resources.extend([
                r_Queue,
            ])

# Need to stay as last lines
import_modules(globals())
