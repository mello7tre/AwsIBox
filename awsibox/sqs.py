import troposphere.sqs as sqs

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
                     get_subvalue, auto_get_props, get_condition, add_obj)


class SQSQueuePolicy(sqs.QueuePolicy):
    def __init__(self, title, key, **kwargs):
        super().__init__(title, **kwargs)
        self.Queues = [
            Sub(
                'https://sqs.${AWS::Region}.amazonaws.com/'
                '${AWS::AccountId}/${QueueId}',
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


class SQS_Queues(object):
    def __init__(self, key):
        for n, v in getattr(cfg, key).items():
            resname = f'{key}{n}'
            # resources
            r_Queue = sqs.Queue(resname)
            auto_get_props(r_Queue, v, recurse=True)

            add_obj([
                r_Queue,
            ])
