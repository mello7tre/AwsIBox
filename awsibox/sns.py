import troposphere.sns as sns

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
    get_subvalue, auto_get_props, get_condition, add_obj)
from .lambdas import LambdaPermissionSNS
from .sqs import SQSQueuePolicy

class SNSSubscription(sns.SubscriptionResource):
    def setup(self, key):
        auto_get_props(self, key)


class SNSTopic(sns.Topic):
    def setup(self, name):
        self.DisplayName = Sub('${AWS::StackName}.${EnvRole}-SNS%s' % name)

##
##

class SNS_Topics(object):
    def __init__(self, key):
        # Resources
        for n, v in getattr(cfg, key).items():
            resname = key + n  # Ex. SNSTopicASGNotification
            r_Topic = SNSTopic(resname)
            r_Topic.setup(name=n)
            if 'Condition' in v:
                r_Topic.Condition = v['Condition']

            add_obj(r_Topic)

            # outputs
            if 'Export' in v:
                o_Topic = Output(resname)
                o_Topic.Value = Ref(resname)
                o_Topic.Export = Export(resname)
                if 'Condition' in v:
                    o_Topic.Condition = v['Condition']

                add_obj(o_Topic)


class SNS_Subscriptions(object):
    def __init__(self, key):
        # Resources
        for n, v in getattr(cfg, key).items():
            if 'Enabled' in v and not v['Enabled']:
                continue
            resname = key + n  # Ex. SNSSubscriptionASGNotificationLambdaR53RecordInstanceId
            r_Subscription = SNSSubscription(resname)
            r_Subscription.setup(key=v)

            add_obj(r_Subscription)

            if v['Protocol'] == 'lambda':
                lambdaname = resname.split('Lambda')[1]
                topicname = resname.split('Lambda')[0].replace(key, 'SNS')
                permname = 'LambdaPermission' + lambdaname + topicname  # Ex. LambdaPermissionR53RecordInstanceIdSNSASGNotification 

                r_LambdaPermission = LambdaPermissionSNS(permname)
                r_LambdaPermission.setup(key=v)
                # Propagate condition, if present, to permission
                if hasattr(r_Subscription, 'Condition'):
                    r_LambdaPermission.Condition = r_Subscription.Condition

                add_obj(r_LambdaPermission)

            if v['Protocol'] == 'sqs':
                queuename = resname.split('SQS')[1]  # Ex. RabbitMQCluster
                topicname = resname.split('SQS')[0].replace(key, 'SNS')  # Ex. SNSASGNotification
                queuepolicyname = 'SQSQueuePolicy' + queuename + topicname  # Ex. SQSQueuePolicyRabbitMQClusterSNSASGNotification

                r_QueuePolicy = SQSQueuePolicy(queuepolicyname)
                r_QueuePolicy.setup(key=v)

                #add_obj(r_QueuePolicy)
                add_obj([r_QueuePolicy])
