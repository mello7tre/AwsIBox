import troposphere.sns as sns

from .common import *
from .shared import (Parameter, get_endvalue, get_expvalue, get_subvalue,
                     auto_get_props, get_condition, add_obj)
from .lambdas import LambdaPermissionSNS
from .sqs import SQSQueuePolicy


class SNSSubscription(sns.SubscriptionResource):
    def __init__(self, title, key, **kwargs):
        super().__init__(title, **kwargs)
        auto_get_props(self)


class SNSTopic(sns.Topic):
    def setup(self, name):
        self.DisplayName = Sub('${AWS::StackName}.${EnvRole}-SNS%s' % name)

##


def SNS_Topics(key):
    # Resources
    for n, v in getattr(cfg, key).items():
        resname = f'{key}{n}'
        r_Topic = SNSTopic(resname)
        r_Topic.setup(name=n)
        if 'Condition' in v:
            r_Topic.Condition = v['Condition']

        add_obj(r_Topic)

        # outputs
        if v.get('Export'):
            o_Topic = Output(resname)
            o_Topic.Value = Ref(resname)
            o_Topic.Export = Export(resname)
            if 'Condition' in v:
                o_Topic.Condition = v['Condition']

            add_obj(o_Topic)


def SNS_Subscriptions(key):
    # Resources
    for n, v in getattr(cfg, key).items():
        resname = f'{key}{n}'
        r_Subscription = SNSSubscription(resname, key=v)

        add_obj(r_Subscription)

        if v['Protocol'] == 'lambda':
            lambdaname = resname.split('Lambda')[1]
            topicname = resname.split('Lambda')[0].replace(key, 'SNS')
            permname = f'LambdaPermission{lambdaname}{topicname}'

            r_LambdaPermission = LambdaPermissionSNS(permname, key=v)
            # Propagate condition, if present, to permission
            if hasattr(r_Subscription, 'Condition'):
                r_LambdaPermission.Condition = r_Subscription.Condition

            add_obj(r_LambdaPermission)

        if v['Protocol'] == 'sqs':
            queuename = resname.split('SQS')[1]
            topicname = resname.split('SQS')[0].replace(key, 'SNS')
            queuepolicyname = f'SQSQueuePolicy{queuename}{topicname}'

            r_QueuePolicy = SQSQueuePolicy(queuepolicyname, key=v)

            add_obj(r_QueuePolicy)
