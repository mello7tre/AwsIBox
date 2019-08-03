import troposphere.autoscaling as asg
import troposphere.cloudformation as cfm
import troposphere.policies as pol
import troposphere.applicationautoscaling as aas

import os
import sys

from cfn import *
from shared import *

try:
    from cfnExt import *
except ImportError:
    pass


# S - AUTOSCALING #
class ASAutoScalingGroup(asg.AutoScalingGroup):
    def setup(self, spot=None):
        if spot:
            CapacityDesiredASGMainIsSpot = get_final_value('CapacityDesired')
            CapacityDesiredASGMainIsNotSpot = 0
            CapacityMinASGMainIsSpot = get_final_value('CapacityMin')
            CapacityMinASGMainIsNotSpot = 0
            self.Condition = 'SpotASG'
            self.LaunchConfigurationName = Ref('LaunchConfigurationSpot')
            self.UpdatePolicy = ASUpdatePolicy(spot=True)
        else:
            CapacityDesiredASGMainIsSpot = 0
            CapacityDesiredASGMainIsNotSpot = get_final_value('CapacityDesired')
            CapacityMinASGMainIsSpot = 0
            CapacityMinASGMainIsNotSpot = get_final_value('CapacityMin')
            self.LaunchConfigurationName = Ref('LaunchConfiguration')
            self.UpdatePolicy = ASUpdatePolicy()

        self.AvailabilityZones = GetAZs()
        if 'SpotASG' in RP_cmm:
            self.DesiredCapacity = If('ASGMainIsSpot', CapacityDesiredASGMainIsSpot, CapacityDesiredASGMainIsNotSpot)
            self.MinSize = If('ASGMainIsSpot', CapacityMinASGMainIsSpot, CapacityMinASGMainIsNotSpot)
        else:
            self.DesiredCapacity = get_final_value('CapacityDesired')
            self.MinSize = get_final_value('CapacityMin')
        self.CreationPolicy = pol.CreationPolicy(
            ResourceSignal=pol.ResourceSignal(
                Count=self.DesiredCapacity,
                Timeout=get_final_value('AutoscalingCreationTimeout')
            )
        )
        self.HealthCheckGracePeriod = get_final_value('HealthCheckGracePeriod')
        self.HealthCheckType = get_final_value('HealthCheckType')
        self.MaxSize = get_final_value('CapacityMax')
        self.MetricsCollection = [asg.MetricsCollection(
            Granularity='1Minute'
        )]
        self.Tags = [
            asg.Tag(('Name'), Ref('EnvRole'), True),
            asg.Tag(('EnvStackName'), Ref('AWS::StackName'), True),
        ]
        self.TerminationPolicies = ['OldestInstance']
        self.VPCZoneIdentifier = Split(',', get_exported_value('SubnetsPrivate'))


class ASLaunchConfiguration(asg.LaunchConfiguration):
    def setup(self, UserDataApp, spot=None):
        if spot:
            AutoScalingGroupName='AutoScalingGroupSpot'
            self.Condition = 'SpotASG'
        else:
            AutoScalingGroupName = 'AutoScalingGroup'
        self.AssociatePublicIpAddress = False
        self.BlockDeviceMappings = [
            asg.BlockDeviceMapping(
                DeviceName='/dev/xvda',
                Ebs=asg.EBSBlockDevice(
                    VolumeSize=get_final_value('VolumeSize'),
                    VolumeType=get_final_value('VolumeType'),
                )
            ),
            If(
                'AdditionalStorage',
                asg.BlockDeviceMapping(
                    DeviceName=get_final_value('AdditionalStorageName'),
                    Ebs=asg.EBSBlockDevice(
                        VolumeSize=get_final_value('AdditionalStorageSize'),
                        VolumeType=get_final_value('AdditionalStorageType'),
                    )
                ),
                Ref('AWS::NoValue')
            ),
            If(
                'InstaceEphemeral0',
                asg.BlockDeviceMapping(
                    DeviceName='/dev/xvdb',
                    VirtualName='ephemeral0'
                ),
                Ref('AWS::NoValue')
            ),
            If(
                'InstaceEphemeral1',
                asg.BlockDeviceMapping(
                    DeviceName='/dev/xvdc',
                    VirtualName='ephemeral1'
                ),
                Ref('AWS::NoValue')
            ),
            If(
                'InstaceEphemeral2',
                asg.BlockDeviceMapping(
                    DeviceName='/dev/xvdd',
                    VirtualName='ephemeral2'
                ),
                Ref('AWS::NoValue')
            ),
        ]
        self.IamInstanceProfile = Ref('InstanceProfile')
        self.ImageId = If(
            'ImageIdLatest',
            Ref('ImageIdLatest'),
            get_final_value('ImageId'),
        ) if 'ImageIdLatest' in RP_cmm['Parameter'] else get_final_value('ImageId')
        self.InstanceMonitoring = get_final_value('InstanceMonitoring')
        self.InstanceType = get_final_value('InstanceType')
        self.KeyName = get_final_value('KeyName')
        self.SecurityGroups = [
            GetAtt('SecurityGroupInstancesRules', 'GroupId'),
        ]
        self.SpotPrice = If('SpotPrice', get_final_value('SpotPrice'), Ref('AWS::NoValue'))
        self.UserData = Base64(Join('', [
            '#!/bin/bash\n',
            'PATH=/opt/aws/bin:$PATH\n',
            'export BASH_ENV=/etc/profile.d/ibox_env.sh\n',
            'export ENV=$BASH_ENV\n',
            'yum -C list installed aws-cfn-bootstrap || yum install -y aws-cfn-bootstrap\n',
            #'#', Ref('EnvApp1Version') if 1 in RP_cmm['Apps'] else '', '\n',
            Sub(''.join(UserDataApp)),
            'cfn-init -v',
            ' --stack ', Ref('AWS::StackName'),
            ' --role ', Ref('RoleInstance'),
            ' --resource LaunchConfiguration',
            ' --region ', Ref('AWS::Region'), '\n',
            If(
                'DoNotSignal',
                Ref('AWS::NoValue'),
                Sub('cfn-signal -e $? --stack ${AWS::StackName} --role ${RoleInstance} --resource ' + AutoScalingGroupName + ' --region ${AWS::Region}\n')
            ),
            'rm /var/lib/cloud/instance/sem/config_scripts_user\n',
        ]))


class ASScalingPolicyStep(asg.ScalingPolicy):
    def setup(self):
        name = self.title  # Ex. ScalingPolicyDown
        self.AdjustmentType = 'ChangeInCapacity'
        self.AutoScalingGroupName = Ref('AutoScalingGroup')
        self.EstimatedInstanceWarmup = get_final_value(name + 'EstimatedInstanceWarmup')
        self.PolicyType = 'StepScaling'
        self.StepAdjustments = [
            asg.StepAdjustments(
                MetricIntervalLowerBound=get_final_value(name + 'MetricIntervalLowerBound1'),  # Ex. ScalingPolicyDownMetricIntervalLowerBound1
                MetricIntervalUpperBound=get_final_value(name + 'MetricIntervalUpperBound1'),
                ScalingAdjustment=get_final_value(name + 'ScalingAdjustment1')  # Ex. ScalingPolicyDownScalingAdjustment1
            ),
            asg.StepAdjustments(
                MetricIntervalLowerBound=get_final_value(name + 'MetricIntervalLowerBound2'),
                MetricIntervalUpperBound=get_final_value(name + 'MetricIntervalUpperBound2'),
                ScalingAdjustment=get_final_value(name + 'ScalingAdjustment2')
            ),
            asg.StepAdjustments(
                ScalingAdjustment=get_final_value(name + 'ScalingAdjustment3')
            )
        ]


class ASScheduledAction(asg.ScheduledAction):
    def setup(self):
        name = self.title
        self.Condition = name
        if 'SpotASG' in RP_cmm:
            self.AutoScalingGroupName = If('ASGMainIsSpot', Ref('AutoScalingGroupSpot'), Ref('AutoScalingGroup'))
        else:
            self.AutoScalingGroupName = Ref('AutoScalingGroup')
        self.DesiredCapacity = If(
            name + 'CapacityDesiredSize',
            get_final_value('CapacityDesired'),
            get_final_value(name + 'DesiredSize', nocondition=name + 'KeepDesiredSize')
        )
        self.MinSize = If(
            name + 'CapacityMinSize',
            get_final_value('CapacityMin'),
            get_final_value(name + 'MinSize', nocondition=name + 'KeepMinSize')
        )
        self.MaxSize = If(
            name + 'CapacityMaxSize',
            get_final_value('CapacityMax'),
            get_final_value(name + 'MaxSize', nocondition=name + 'KeepMaxSize')
        )
        self.Recurrence = get_final_value(name + 'Recurrence')
        self.StartTime = If(
            name + 'StartTimeOverride',
            Ref(name + 'StartTime'),
            Ref('AWS::NoValue')
        )


class ASLifecycleHook(asg.LifecycleHook):
    def __init__(self, title, name, key, **kwargs):
        super(asg.LifecycleHook, self).__init__(title, **kwargs)
        auto_get_props(self, key)
        self.HeartbeatTimeout = get_final_value(title + 'HeartbeatTimeout')

# E - AUTOSCALING #


class ASScalingPolicyStepDown(ASScalingPolicyStep):
    def setup(self):
        super(ASScalingPolicyStepDown, self).setup()
        name = self.title
        self.StepAdjustments[2].MetricIntervalUpperBound = get_final_value(name + 'MetricIntervalUpperBound3')


class ASScalingPolicyStepUp(ASScalingPolicyStep):
    def setup(self):
        super(ASScalingPolicyStepUp, self).setup()
        name = self.title
        self.StepAdjustments[2].MetricIntervalLowerBound = get_final_value(name + 'MetricIntervalLowerBound3')


# S - APPLICATION AUTOSCALING #
class APPASScalingPolicy(aas.ScalingPolicy):
    def setup(self):
        name = self.title
        self.PolicyName = self.title
        self.ScalingTargetId = Ref('ScalableTarget')


class APPASScalingPolicyStep(APPASScalingPolicy):
    def setup(self):
        super(APPASScalingPolicyStep, self).setup()
        name = self.title
        self.PolicyType = 'StepScaling'
        self.StepScalingPolicyConfiguration = aas.StepScalingPolicyConfiguration(
            AdjustmentType='ChangeInCapacity',
            MetricAggregationType='Average',
            StepAdjustments=[
                aas.StepAdjustment(
                    MetricIntervalLowerBound=get_final_value(name + 'MetricIntervalLowerBound1'),
                    MetricIntervalUpperBound=get_final_value(name + 'MetricIntervalUpperBound1'),
                    ScalingAdjustment=get_final_value(name + 'ScalingAdjustment1')
                    ),
                aas.StepAdjustment(
                    MetricIntervalLowerBound=get_final_value(name + 'MetricIntervalLowerBound2'),
                    MetricIntervalUpperBound=get_final_value(name + 'MetricIntervalUpperBound2'),
                    ScalingAdjustment=get_final_value(name + 'ScalingAdjustment2')
                    ),
                aas.StepAdjustment(
                    ScalingAdjustment=get_final_value(name + 'ScalingAdjustment3')
                )
            ]
        )


class APPASScalingPolicyStepDown(APPASScalingPolicyStep):
    def setup(self):
        super(APPASScalingPolicyStepDown, self).setup()
        name = self.title
        self.StepScalingPolicyConfiguration.StepAdjustments[2].MetricIntervalUpperBound = get_final_value(name + 'MetricIntervalUpperBound3')


class APPASScalingPolicyStepUp(APPASScalingPolicyStep):
    def setup(self):
        super(APPASScalingPolicyStepUp, self).setup()
        name = self.title
        self.StepScalingPolicyConfiguration.StepAdjustments[2].MetricIntervalLowerBound = get_final_value(name + 'MetricIntervalLowerBound3')


class APPASScheduledAction(aas.ScheduledAction):
    def setup(self):
        name = self.title
        self.ScalableTargetAction = aas.ScalableTargetAction(
            MinCapacity=If(
                name + 'CapacityMinSize',
                get_final_value('CapacityMin'),
                get_final_value(name + 'MinSize', nocondition=name + 'KeepMinSize')
            ),
            MaxCapacity=If(
                name + 'CapacityMaxSize',
                get_final_value('CapacityMax'),
                get_final_value(name + 'MaxSize', nocondition=name + 'KeepMaxSize')
            )
        )
        self.Schedule = get_final_value(name + 'Recurrence')
        self.ScheduledActionName = name
        self.StartTime = If(
            name + 'StartTimeOverride',
            Ref(name + 'StartTime'),
            Ref('AWS::NoValue')
        )


class APPASScalableTarget(aas.ScalableTarget):
    def setup(self):
        self.MaxCapacity = get_final_value('CapacityMax')
        self.MinCapacity = get_final_value('CapacityMin')
        self.ResourceId = get_sub_mapex('service/${1E}/${Service.Name}', 'Cluster', 'ClusterStack')
        self.RoleARN = get_exported_value('RoleEC2ContainerServiceAutoscale', '')
        self.ScalableDimension = 'ecs:service:DesiredCount'
        self.ServiceNamespace = 'ecs'

# E - APPLICATION AUTOSCALING #

# ############################################
# ### START STACK META CLASSES AND METHODS ###
# ############################################

# S - AUTOSCALING #
class ASUpdatePolicy(pol.UpdatePolicy):
    def __init__(self, spot=None, **kwargs):
        super(ASUpdatePolicy, self).__init__(**kwargs)
        if spot:
            WillReplaceCondition = 'WillReplaceSpot' 
            AutoScalingRollingUpdateCondition = 'RollingUpdateSpot' 
        else:
            WillReplaceCondition = 'WillReplace' 
            AutoScalingRollingUpdateCondition = 'RollingUpdate' 
        self.AutoScalingReplacingUpdate = If(
            WillReplaceCondition,
            pol.AutoScalingReplacingUpdate(
                WillReplace=True
            ),
            Ref('AWS::NoValue')
        )
        self.AutoScalingRollingUpdate = If(
            AutoScalingRollingUpdateCondition,
            pol.AutoScalingRollingUpdate(
                MaxBatchSize=get_final_value('RollingUpdateMaxBatchSize'),
                # MinInstancesInService=get_final_value('RollingUpdateMinInstancesInService'),
                MinInstancesInService=get_final_value('CapacityDesired'),
                MinSuccessfulInstancesPercent=get_final_value('RollingUpdateMinSuccessfulInstancesPercent'),
                PauseTime=get_final_value('RollingUpdatePauseTime'),
                SuspendProcesses=[
                    'HealthCheck',
                    'ReplaceUnhealthy',
                    'AlarmNotification',
                    'ScheduledActions'
                ],
                WaitOnResourceSignals=True
            ),
            Ref('AWS::NoValue')
        )
        self.AutoScalingScheduledAction=pol.AutoScalingScheduledAction(
            IgnoreUnmodifiedGroupSizeProperties=True
        )


class ASInitConfigSets(cfm.InitConfigSets):
    def setup(self):
        self.data = {
            'default': [
                'REPOSITORIES',
                'PACKAGES',
                'SETUP',
                If('DeploymentGroup', 'CODEDEPLOY', Ref('AWS::NoValue')) if RP_cmm['Apps'] else Ref('AWS::NoValue'),
                'SERVICES',
                'ELBWAITER' if 'LoadBalancerClassic' in RP_cmm or 'LoadBalancerApplication' in RP_cmm else Ref('AWS::NoValue')
            ],
            'buildami': [
                'REPOSITORIES',
                'PACKAGES',
            ],
            'buildamifull': [
                'REPOSITORIES',
                'PACKAGES',
                'SETUP',
            ]
        }


class ASInitConfigSetup(cfm.InitConfig):
    def __init__(self, **kwargs):
        self.ibox_env_app = ''
        super(ASInitConfigSetup, self).__init__(**kwargs)

    def setup(self):
        self.files = {
            '/etc/profile.d/ibox_env.sh': {
                'content': Join('', [
                    '#setup ibox environment variables\n',
                    'export Env=', Ref('Env'), '\n',
                    'export EnvAbbr=', Ref('EnvShort'), '\n',
                    'export EnvRegion=', Ref('AWS::Region'), '\n',
                    'export EnvAccountId=', Ref('AWS::AccountId'), '\n',
                    'export EnvRole=', Ref('EnvRole'), '\n',
                    'export EnvBrand=', get_final_value('BrandDomain'), '\n',
                    'export EnvStackName=', Ref('AWS::StackName'), '\n',
                ] + self.ibox_env_app)
            },
            '/etc/cfn/cfn-hup.conf': {
                'content': Join('', [
                    '[main]\n',
                    'stack=', Ref('AWS::StackId'), '\n',
                    'region=', Ref('AWS::Region'), '\n',
                    'role=', Ref('RoleInstance'), '\n',
                    'interval=5\n'
                ]),
                'mode': '000400',
                'owner': 'root',
                'group': 'root'
            },
            '/etc/cfn/hooks.d/cfn-auto-reloader.conf': {
                'content': Join('', [
                    '[cfn-auto-reloader-hook]\n',
                    'triggers=post.add, post.update\n',
                    'path=Resources.LaunchConfiguration.Metadata.CloudFormationInitVersion\n',
                    'action=/opt/aws/bin/cfn-init -v',
                    ' --stack ', Ref('AWS::StackName'),
                    ' --role ', Ref('RoleInstance'),
                    ' --resource LaunchConfiguration',
                    ' --region ', Ref('AWS::Region'), '\n',
                    'runas=root\n'
                ])
            },
            '/usr/local/bin/chamber': {
                'mode': '000755',
                'source': Sub('https://' + RP_cmm['BucketAppRepository'] + '.s3.${AWS::Region}.amazonaws.com/ibox-tools/chamber'),
                'owner': 'root',
                'group': 'root',
            },
        }
        self.commands = {
            '01_disk': {
                'command': Join('', [
                    'n=0\n',
                    'for disk in /dev/xvd[b-d]; do\n',
                    '  [ -b "$disk" ] || continue\n',
                    '  file -s "$disk" | grep -q "ext[34] filesystem" || ',
                    '  { mkfs.ext4 $disk || continue; }\n',
                    '  mkdir -p /media/ephemeral${n} && ',
                    '  mount $disk /media/ephemeral${n}\n',
                    '  n=$(($n+1))\n',
                    'done'
                ])
            },
            '02_disk_additional': If(
                'AdditionalStorageMount',
                {
                    #'command': Join('', [
                    #    'file -s ', get_final_value('AdditionalStorageName'), '1', ' | grep -q "ext[34] filesystem" || ',
                    #    '{ parted -s ', get_final_value('AdditionalStorageName'), ' mklabel gpt', ' && ',
                    #    'parted -s ', get_final_value('AdditionalStorageName'), ' mkpart primary ext2 1 ',
                    #    get_final_value('AdditionalStorageSize'), 'G', ' && ',
                    #    'mkfs.ext4 ', get_final_value('AdditionalStorageName'), '1', ' || continue; }\n',
                    #    'mkdir -p /data', ' && ',
                    #    'mount /dev/xvdx1 /data'
                    #])
                    'command': get_sub_mapex(
                        'file -s ${1M}1 | grep -q "ext[34] filesystem" || { parted -s ${1M} mklabel gpt && parted -s ${1M} mkpart primary ext2 1 ${2M}G && mkfs.ext4 ${1M}1 || continue; }\nmkdir -p /data && mount ${1M}1 /data',
                        ['AdditionalStorageName', 'AdditionalStorageSize']
                    )
                },
                Ref('AWS::NoValue')
            ),
            '03_efs_mounts': If(
                'EfsMounts',
                {
                    'command': Join('', [
                        'for mounts in ', Join(' ', Ref('EfsMounts')), ';do\n',
                        '  mkdir -p "/media/${mounts}"\n',
                        '  mountpoint -q "/media/${mounts}" ||',
                        '    mount -t nfs4 -o nfsvers=4,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2 ',
                        '    efs-${mounts}.', get_final_value('HostedZoneNamePrivate'), ':/ ',
                        '    /media/${mounts}\n',
                        'done'
                    ]),
                },
                Ref('AWS::NoValue')
            ),
            '04_rmdir_tmp_ibox': {
                'command': 'rm -fr /tmp/ibox'
            }
        }
        self.services = {
            'sysvinit': {
                'cfn-hup': {
                    'enabled': 'false',
                    'ensureRunning': 'true',
                    'files': [
                        '/etc/cfn/cfn-hup.conf',
                        '/etc/cfn/hooks.d/cfn-auto-reloader.conf'
                    ]
                }
            }
        }


class ASInitConfigCodeDeploy(cfm.InitConfig):
    def setup(self):
        self.files = {
            '/etc/codedeploy-agent/conf/codedeployagent.yml': {
                'content': Join('', [
                    '---\n',
                    ':log_aws_wire: false\n',
                    ':log_dir: \'/var/log/aws/codedeploy-agent/\'\n',
                    ':pid_dir: \'/opt/codedeploy-agent/state/.pid/\'\n',
                    ':program_name: codedeploy-agent\n',
                    ':root_dir: \'/opt/codedeploy-agent/deployment-root\'\n',
                    ':verbose: false\n',
                    ':wait_between_runs: 1\n',
                    ':proxy_uri:\n',
                    ':max_revisions: 2\n'
                ])
            },
            '/tmp/codedeployinstall.sh': {
                'source': Sub('https://aws-codedeploy-${AWS::Region}.s3.amazonaws.com/latest/install'),
                'mode': '000700'
            }
        }
        self.commands = {
            '03_codedeploy-install-and-run': {
                'command': '/tmp/codedeployinstall.sh auto'
            }
        }
        self.services = {
            'sysvinit': {
                'codedeploy-agent': {
                    'enabled': 'false',
                    'ensureRunning': 'true',
                    'files': ['/etc/codedeploy-agent/conf/codedeployagent.yml']
                }
            }
        }


class ASInitConfigApps(cfm.InitConfig):
    def __init__(self, title, **kwargs):
        super(ASInitConfigApps, self).__init__(title, **kwargs)
        name = self.title  # Ex. Apps1
        reponame = name + 'RepoName'
        n = name.replace('Apps', '')
        envappversion = 'EnvApp' + str(n) + 'Version'

        self.sources = {
            '/tmp/ibox/': If(
                'DeployRevision',
                Ref('AWS::NoValue'),
                get_sub_mapex(
                    'https://' + get_final_value('BucketAppRepository') + '.s3-${AWS::Region}.amazonaws.com/${1M}/${1M}-${' + envappversion + '}.tar.gz',
                    reponame, ''
                )
            )
        }
        self.commands = {
            '01_setup': If(
                'DeployRevision',
                Ref('AWS::NoValue'),
                {
                    'command': get_sub_mapex(
                        'EnvAppVersion=${' + envappversion + '} EnvRepoName=${1M} /tmp/ibox/bin/setup.sh', reponame
                    )
                }
            ),
            '02_setup_reboot_codedeploy': If(
                'DeployRevision',
                {
                    'command': get_sub_mapex(
                        'EnvAppVersion=${' + envappversion + '} EnvRepoName=${1M} /opt/ibox/${1M}/live/bin/setup.sh', reponame
                    ),
                    'test': 'test -e /var/lib/cloud/instance/sem/config_ssh_authkey_fingerprints'
                },
                Ref('AWS::NoValue')
            ),
            '03_rmdir_tmp_ibox': {
                'command': 'rm -fr /tmp/ibox'
            }
        }


class ASInitConfigAppsBuildAmi(ASInitConfigApps):
    def __init__(self, title, **kwargs):
        super(ASInitConfigAppsBuildAmi, self).__init__(title, **kwargs)
        for n, v in self.sources.iteritems():
            if not isinstance(v, dict):
                if 'Fn::If' in v.data:
                    self.sources[n] = v.data['Fn::If'][2]

        for n, v in self.commands.iteritems():
            if not isinstance(v, dict):
                if 'Fn::If' in v.data:
                    self.commands[n] = v.data['Fn::If'][2]


class ASInitConfigELBClassicExternal(cfm.InitConfig):
    def setup(self):
        self.commands = {
            'ELBClassicExternalHealthCheck': {
                'command': Join('', [
                    'until [ "$state" = \'"InService"\' ]; do',
                    '  state=$(aws --region ', Ref('AWS::Region'), ' elb describe-instance-health',
                    '  --load-balancer-name ', Ref('LoadBalancerClassicExternal'),
                    '  --instances $(curl -s http://169.254.169.254/latest/meta-data/instance-id)',
                    '  --query InstanceStates[0].State);',
                    '  sleep 10;',
                    'done'
                ])
            }
        }


class ASInitConfigELBClassicInternal(cfm.InitConfig):
    def setup(self):
        self.commands = {
            'ELBClassicInternalHealthCheck': {
                'command': Join('', [
                    'until [ "$state" = \'"InService"\' ]; do',
                    '  state=$(aws --region ', Ref('AWS::Region'), ' elb describe-instance-health',
                    '  --load-balancer-name ', Ref('LoadBalancerClassicInternal'),
                    '  --instances $(curl -s http://169.254.169.254/latest/meta-data/instance-id)',
                    '  --query InstanceStates[0].State);',
                    '  sleep 10;',
                    'done'
                ])
            }
        }


class ASInitConfigELBApplicationExternal(cfm.InitConfig):
    def setup(self):
        self.commands = {
            'ELBApplicationExternalHealthCheck': {
                'command': Join('', [
                    'until [ "$state" = \'"healthy"\' ]; do',
                    '  state=$(aws --region ', Ref('AWS::Region'), ' elbv2 describe-target-health',
                    '  --target-group-arn ', Ref('TargetGroupExternal'),
                    '  --targets Id=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)',
                    '  --query TargetHealthDescriptions[0].TargetHealth.State);',
                    '  sleep 10;',
                    'done'
                ])
            }
        }


class ASInitConfigELBApplicationInternal(cfm.InitConfig):
    def setup(self):
        self.commands = {
            'ELBApplicationInternalHealthCheck': {
                'command': Join('', [
                    'until [ "$state" = \'"healthy"\' ]; do',
                    '  state=$(aws --region ', Ref('AWS::Region'), ' elbv2 describe-target-health',
                    '  --target-group-arn ', Ref('TargetGroupInternal'),
                    '  --targets Id=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)',
                    '  --query TargetHealthDescriptions[0].TargetHealth.State);',
                    '  sleep 10;',
                    'done'
                ])
            }
        }


class ASNotificationConfiguration(asg.NotificationConfigurations):
    def setup(self):
        self.NotificationTypes = [
            'autoscaling:EC2_INSTANCE_LAUNCH',
            'autoscaling:EC2_INSTANCE_TERMINATE',
        ]
        self.TopicARN = get_exported_value('SNSTopicASGNotification')
# E - AUTOSCALING #

# ##########################################
# ### END STACK META CLASSES AND METHODS ###
# ##########################################

class AS_ScheduledAction(object):
    def __init__(self, resname, OutKey=[]):
        OutKey.extend([
            'MinSize',
            'MaxSize',
            'Recurrence',
            'StartTime',
        ])
        # Parameters
        P_MinSize = Parameter(resname + 'MinSize')
        P_MinSize.Description = resname + 'Min Capacity - k to keep current value - empty for default based on env/role'

        P_MaxSize = Parameter(resname + 'MaxSize')
        P_MaxSize.Description = resname + 'Max Capacity - k to keep current value - empty for default based on env/role'

        P_Recurrence = Parameter(resname + 'Recurrence')
        P_Recurrence.Description = resname + 'Recurrence - k to keep current value - empty for default based on env/role'

        P_StartTime = Parameter(resname + 'StartTime')
        P_StartTime.Description = resname + 'StartTime - k to keep current value - empty for default based on env/role'

        cfg.Parameters.extend([
            P_MinSize,
            P_MaxSize,
            P_Recurrence,
            P_StartTime,
        ])

        # Conditions
        do_no_override(True)
        C_KeepMinSize = {resname + 'KeepMinSize': Or(
            And(
                Condition(resname + 'MinSizeOverride'),
                Equals(Ref(resname + 'MinSize'), 'k')
            ),
            And(
                Not(Condition(resname + 'MinSizeOverride')),
                Equals(get_final_value(resname + 'MinSize'), 'k')
            )
        )}

        C_KeepMaxSize = {resname + 'KeepMaxSize': Or(
            And(
                Condition(resname + 'MaxSizeOverride'),
                Equals(Ref(resname + 'MaxSize'), 'k')
            ),
            And(
                Not(Condition(resname + 'MaxSizeOverride')),
                Equals(get_final_value(resname + 'MaxSize'), 'k')
            )
        )}

        C_CapacityMinSize = {resname + 'CapacityMinSize': Or(
            And(
                Condition(resname + 'MinSizeOverride'),
                Equals(Ref(resname + 'MinSize'), 'CapacityMin')
            ),
            And(
                Not(Condition(resname + 'MinSizeOverride')),
                Equals(get_final_value(resname + 'MinSize'), 'CapacityMin')
            )
        )}

        C_CapacityMaxSize = {resname + 'CapacityMaxSize': Or(
            And(
                Condition(resname + 'MaxSizeOverride'),
                Equals(Ref(resname + 'MaxSize'), 'CapacityMax')
            ),
            And(
                Not(Condition(resname + 'MaxSizeOverride')),
                Equals(get_final_value(resname + 'MaxSize'), 'CapacityMax')
            )
        )}

        C_ScheduledAction = {resname: Or(
            And(
                Condition(resname + 'RecurrenceOverride'),
                Not(Equals(Ref(resname + 'Recurrence'), 'None'))
            ),
            And(
                Not(Condition(resname + 'RecurrenceOverride')),
                Not(Equals(get_final_value(resname + 'Recurrence'), 'None'))
            )
        )}

        cfg.Conditions.extend([
            C_KeepMinSize,
            C_KeepMaxSize,
            C_CapacityMinSize,
            C_CapacityMaxSize,
            C_ScheduledAction,
        ])
        do_no_override(False)

        # outputs
        out_String = []
        out_Map = {}
        for k in OutKey:
            out_String.append(k + '=${' + k + '}')  # Ex. 'MinSize=${MinSize}'
            out_Map.update({k: get_final_value(resname + k) if k != 'StartTime' else Ref(resname + k)})

        O_ScheduledAction = Output(resname)
        O_ScheduledAction.Value = Sub(','.join(out_String), **out_Map)
        
        cfg.Outputs.append(O_ScheduledAction)


class AS_ScheduledActionsEC2(object):
    def __init__(self, key):
        for n, v in RP_cmm[key].iteritems():
            resname = key + str(n)
            # parameters
            p_DesiredSize = Parameter(resname + 'DesiredSize')
            p_DesiredSize.Description = resname + 'Desired Capacity - k to keep current value - empty for default based on env/role'
    
            cfg.Parameters.append(p_DesiredSize)
    
            # conditions
            do_no_override(True)
            c_DesiredSize = {resname + 'KeepDesiredSize': Or(
                And(
                    Condition(resname + 'DesiredSizeOverride'),
                    Equals(Ref(resname + 'DesiredSize'), 'k')
                ),
                And(
                    Not(Condition(resname + 'DesiredSizeOverride')),
                    Equals(get_final_value(resname + 'DesiredSize'), 'k')
                )
            )}
    
            c_CapacityDesiredSize = {resname + 'CapacityDesiredSize': Or(
                And(
                    Condition(resname + 'DesiredSizeOverride'),
                    Equals(Ref(resname + 'DesiredSize'), 'CapacityDesired')
                ),
                And(
                    Not(Condition(resname + 'DesiredSizeOverride')),
                    Equals(get_final_value(resname + 'DesiredSize'), 'CapacityDesired')
                )
            )}
    
            cfg.Conditions.extend([
                c_DesiredSize,
                c_CapacityDesiredSize,
            ])
            do_no_override(False)
    
            # resources
            OutKey = ['DesiredSize']
   
            AS_ScheduledAction(resname, OutKey)
            r_ScheduledAction = ASScheduledAction(resname)
            r_ScheduledAction.setup()
    
            cfg.Resources.append(r_ScheduledAction)
        

class AS_ScheduledActionsECS(object):
    def __init__(self, key):
        ScheduledActions = []
        for n, v in RP_cmm[key].iteritems():
            resname = key + str(n)
            # conditions
            do_no_override(True)
            c_disable = {resname + 'Disable': Or(
                Not(Condition(resname)),
                And(
                    Condition(resname + 'KeepMaxSize'),
                    Condition(resname + 'KeepMinSize'),
                )
            )}
    
            cfg.Conditions.append(c_disable)
            do_no_override(False)

            # resources
            AS_ScheduledAction(resname, [])
            ScheduledAction = APPASScheduledAction(resname)
            ScheduledAction.setup()

            ScheduledActions.append(
                If(
                    resname + 'Disable',
                    Ref('AWS::NoValue'),
                    ScheduledAction,
                )
            )

        self.ScheduledActions = ScheduledActions


class AS_ScalingPoliciesStepEC2(object):
    def __init__(self, key):
        R_Down = ASScalingPolicyStepDown('ScalingPolicyDown')
        R_Down.setup()

        R_Up = ASScalingPolicyStepUp('ScalingPolicyUp')
        R_Up.setup()

        cfg.Resources.extend([
            R_Down,
            R_Up,
        ])


class AS_ScalingPoliciesStepECS(object):
    def __init__(self, key):
        R_Down = APPASScalingPolicyStepDown('ScalingPolicyDown')
        R_Down.setup()

        R_Up = APPASScalingPolicyStepUp('ScalingPolicyUp')
        R_Up.setup()

        cfg.Resources.extend([
            R_Down,
            R_Up,
        ])


class AS_ScalingPoliciesTracking(object):
    def __init__(self, key):
        ScalingPolicyTrackings_Out_String = []
        ScalingPolicyTrackings_Out_Map = {}
        for n, v in RP_cmm[key].iteritems():
            if not ('Enabled' in v and v['Enabled'] is True):
                continue
            resname = key + str(n)
            # Autoscaling
            if 'TargetTrackingConfiguration' in v:
                TargetTrackingConfigurationName = 'TargetTrackingConfiguration'
                p_type = 'autoscaling'
            # Application Autoscaling
            elif 'TargetTrackingScalingPolicyConfiguration' in v:
                TargetTrackingConfigurationName = 'TargetTrackingScalingPolicyConfiguration'
                p_type = 'application_autoscaling'
            basename = resname + TargetTrackingConfigurationName

            # parameters
            p_Value = Parameter(basename + 'TargetValue')
            p_Value.Description = 'Tracking ' + n + ' Value - 0 to disable - empty for default based on env/role'
            
            p_Statistic = Parameter(basename + 'CustomizedMetricSpecificationStatistic')
            p_Statistic.Description = 'Tracking ' + n + ' Statistic - 0 to disable - empty for default based on env/role'

            cfg.Parameters.extend([
                p_Value,
                p_Statistic,
            ])

            #  conditions
            do_no_override(True)
            c_Value = {resname: Or(
                And(
                    Condition(basename + 'TargetValueOverride'),
                    Not(Equals(Ref(basename + 'TargetValue'), '0'))
                ),
                And(
                    Not(Condition(basename + 'TargetValueOverride')),
                    Not(Equals(get_final_value(basename + 'TargetValue'), '0'))
                )
            )}

            cfg.Conditions.append(c_Value)
            do_no_override(False)

            # outputs
            if v['Type'] == 'Cpu' or (v['Type'] == 'Custom' and
                v[TargetTrackingConfigurationName]['CustomizedMetricSpecification']['MetricName'] == 'CPUUtilization'
            ):
                ScalingPolicyTrackings_Out_String.append('Cpu${Statistic}:${Cpu}')
                ScalingPolicyTrackings_Out_Map.update({
                    'Statistic': get_final_value(basename + 'CustomizedMetricSpecificationStatistic') if v['Type'] == 'Custom'  else '',
                    'Cpu': get_final_value(basename + 'TargetValue'),
                })

            # resources
            r_Tracking = asg.ScalingPolicy(resname) if p_type == 'autoscaling' else aas.ScalingPolicy(resname)
            auto_get_props(r_Tracking, v, recurse=True)
            r_Tracking.Condition = resname

            cfg.Resources.append(r_Tracking)

        # Outputs
        O_Policy = Output(key)
        O_Policy.Value = Sub(','.join(ScalingPolicyTrackings_Out_String), **ScalingPolicyTrackings_Out_Map)

        cfg.Outputs.extend([
            O_Policy,
        ])


class AS_Autoscaling(object):
    def __init__(self):
        # Parameters
        P_Desired = Parameter('CapacityDesired')
        P_Desired.Description = 'Desired Autoscaling Capacity - empty for default based on env/role'

        P_Min = Parameter('CapacityMin')
        P_Min.Description = 'Min Autoscaling Capacity - empty for default based on env/role'

        P_Max = Parameter('CapacityMax')
        P_Max.Description = 'Max Autoscaling Capacity - empty for default based on env/role'

        cfg.Parameters.extend([
            P_Desired,
            P_Min,
            P_Max,
        ])

        # Outputs
        O_Capacity = Output('Capacity')
        O_Capacity.Value = get_sub_mapex(
            'Desired=${1M},Min=${2M},Max=${3M}',
            [
                'CapacityDesired',
                'CapacityMin',
                'CapacityMax',
            ]
        )

        cfg.Outputs.extend([
            O_Capacity,
        ])


class AS_LaunchConfiguration(object):
    def __init__(self):
        # Parameters
        P_AdditionalStorageSize = Parameter('AdditionalStorageSize')
        P_AdditionalStorageSize.Description = 'Size in GiB of additional EBS storage - 0 to disable - empty for default'
        P_AdditionalStorageSize.AllowedValues = ['', '0', '4', '8', '16', '32', '64', '128', '256', '512', '1024']

        P_DoNotSignal = Parameter('DoNotSignal')
        P_DoNotSignal.Description = 'Do Not Signal ASG - WARNING need to manually exec cfn-signal!'
        P_DoNotSignal.AllowedValues = ['False', 'True']
        P_DoNotSignal.Default = 'False'

        P_EfsMounts = Parameter('EfsMounts')
        P_EfsMounts.Type = 'CommaDelimitedList'
        P_EfsMounts.Description = 'Efs Mounts List'
        # to use String Default Type - need to change cfn scripts too, using IFS a storing value in a bash var:
        # P_EfsMounts.AllowedPattern = '^(\w+(,\w+)?)*$'

        P_ImageId = Parameter('ImageId')
        P_ImageId.Description = 'AMI ID - empty for default based on env/role/region'

        P_InstanceType = Parameter('InstanceType')
        P_InstanceType.ConstraintDescription = 'must be a valid EC2 instance type.'
        P_InstanceType.Description = 'InstanceType - default for default based on env/role'
        P_InstanceType.AllowedValues = cfg.template.mappings['InstanceTypes'].keys()
        P_InstanceType.Default = 'default'

        P_KeyName = Parameter('KeyName')
        P_KeyName.Description = 'EC2 SSH Key - empty for default'

        P_VolumeSize = Parameter('VolumeSize')
        P_VolumeSize.Description = 'Size of HD in GB - empty for default based on env/role'

        cfg.Parameters.extend([
            P_AdditionalStorageSize,
            P_DoNotSignal,
            P_EfsMounts,
            P_ImageId,
            P_InstanceType,
            P_KeyName,
            P_VolumeSize,
        ])

        # Conditions
        do_no_override(True)
        C_AdditionalStorage = {'AdditionalStorage': Or(
            And(
                Condition('AdditionalStorageSizeOverride'),
                Not(Equals(Ref('AdditionalStorageSize'), '0'))
            ),
            And(
                Not(Condition('AdditionalStorageSizeOverride')),
                Not(Equals(get_final_value('AdditionalStorageSize'), '0'))
            )
        )}

        C_AdditionalStorageMount = {'AdditionalStorageMount': And(
            Condition('AdditionalStorage'),
            Not(Equals(get_final_value('AdditionalStorageMount'), 'None'))
        )}

        C_CloudFormationInit = {'CloudFormationInit': Equals(
            Ref('UpdateMode'), 'Cfn'
        )}

        C_DoNotSignal = {'DoNotSignal': And(
            Condition('RollingUpdate'),
            Equals(Ref('DoNotSignal'), 'True')
        )}

        C_EfsMounts = {'EfsMounts': Not(
            Equals(Select('0', Ref('EfsMounts')), '')
        )}

        C_InstaceEphemeral0 = {'InstaceEphemeral0': Or(
            And(
                Condition('InstanceTypeOverride'),
                Equals(FindInMap('InstanceTypes', Ref('InstanceType'), 'InstaceEphemeral0'), '1')
            ),
            And(
                Not(Condition('InstanceTypeOverride')),
                Equals(FindInMap('InstanceTypes', get_final_value('InstanceType'), 'InstaceEphemeral0'), '1')
            )
        )}

        C_InstaceEphemeral1 = {'InstaceEphemeral1': Or(
            And(
                Condition('InstanceTypeOverride'),
                Equals(FindInMap('InstanceTypes', Ref('InstanceType'), 'InstaceEphemeral1'), '1')
            ),
            And(
                Not(Condition('InstanceTypeOverride')),
                Equals(FindInMap('InstanceTypes', get_final_value('InstanceType'), 'InstaceEphemeral1'), '1')
            )
        )}

        C_InstaceEphemeral2 = {'InstaceEphemeral2': Or(
            And(
                Condition('InstanceTypeOverride'),
                Equals(FindInMap('InstanceTypes', Ref('InstanceType'), 'InstaceEphemeral2'), '1')
            ),
            And(
                Not(Condition('InstanceTypeOverride')),
                Equals(FindInMap('InstanceTypes', get_final_value('InstanceType'), 'InstaceEphemeral2'), '1')
            )
        )}

        cfg.Conditions.extend([
            C_AdditionalStorage,
            C_AdditionalStorageMount,
            C_CloudFormationInit,
            C_DoNotSignal,
            C_EfsMounts,
            C_InstaceEphemeral0,
            C_InstaceEphemeral1,
            C_InstaceEphemeral2,
        ])
        do_no_override(False)

        InitConfigSets = ASInitConfigSets()
        InitConfigSets.setup()

        CfmInitArgs = {}
        IBoxEnvApp = []
        Tags = []
        UserDataApp = []

        for n in RP_cmm['Apps']:
            name = 'Apps' + str(n)  # Ex. Apps1
            envname = 'EnvApp' + str(n) + 'Version'  # Ex EnvApp1Version
            reponame = name + 'RepoName'  # Ex Apps1RepoName

            UserDataApp.extend(['#${' + envname + '}\n'])

            # parameters
            cfg.Parameters.extend([
                Parameter(
                    envname,
                    Description='Application ' + str(n) + ' version',
                    AllowedPattern='^[a-zA-Z0-9-_.]*$',
                ),
                Parameter(
                    reponame,
                    Description='App ' + str(n) + ' Repo Name - empty for default based on env/role',
                    AllowedPattern='^[a-zA-Z0-9-_.]*$',
                )
            ])

            # conditions
            do_no_override(True)
            cfg.Conditions.append({
                name: And(
                    Not(Equals(Ref(envname), '')),
                    Not(
                        Or(
                            And(
                                Condition(reponame + 'Override'),
                                Equals(Ref(reponame), 'None')
                            ),
                            And(
                                Not(Condition(reponame + 'Override')),
                                Equals(get_final_value(reponame), 'None')
                            )
                        )
                    )
                )
            })
            do_no_override(False)

            InitConfigApps = ASInitConfigApps(name)
            CfmInitArgs[name] = InitConfigApps

            InitConfigAppsBuilAmi = ASInitConfigAppsBuildAmi(name)
            # AUTOSPOT - Let cfn-init always prepare instances on boot
            #CfmInitArgs[name + 'BuildAmi'] = InitConfigAppsBuilAmi
            CfmInitArgs[name] = InitConfigAppsBuilAmi

            IBoxEnvApp.extend([
                'export EnvApp' + str(n) + 'Version=', Ref(envname), "\n",
                'export EnvRepo' + str(n) + 'Name=', get_final_value(reponame), "\n",
            ])

            InitConfigSetsApp = If(name, name, Ref('AWS::NoValue'))
            InitConfigSetsAppBuilAmi = If(name, name + 'BuildAmi', Ref('AWS::NoValue'))
            IndexSERVICES = InitConfigSets.data['default'].index('SERVICES')
            InitConfigSets.data['default'].insert(IndexSERVICES, InitConfigSetsApp)
            # AUTOSPOT - Let cfn-init always prepare instances on boot
            #InitConfigSets.data['buildamifull'].append(InitConfigSetsAppBuilAmi)
            InitConfigSets.data['buildamifull'].append(InitConfigSetsApp)

            Tags.append(asg.Tag(envname, Ref(envname), True))

            # resources
            # FOR MULTIAPP CODEDEPLOY
            if len(RP_cmm['Apps']) > 1:
                r_DeploymentGroup = CDDeploymentGroup('DeploymentGroup' + name)
                r_DeploymentGroup.setup(index=n)

                cfg.Resources.append(r_DeploymentGroup)

            # outputs
            Output_app = Output(envname)
            Output_app.Value = Ref(envname)
            cfg.Outputs.append(Output_app)

            Output_repo = Output(reponame)
            Output_repo.Value = get_final_value(reponame)
            cfg.Outputs.append(Output_repo)

        InitConfigSetup = ASInitConfigSetup()
        InitConfigSetup.ibox_env_app = IBoxEnvApp
        InitConfigSetup.setup()

        InitConfigCodeDeploy = ASInitConfigCodeDeploy()
        InitConfigCodeDeploy.setup()

        CfmInitArgs['SETUP'] = InitConfigSetup

        if RP_cmm['Apps']:
            CfmInitArgs['CODEDEPLOY'] = InitConfigCodeDeploy
            CD_DeploymentGroup()

        if 'LoadBalancerClassic' in RP_cmm:
            if 'External' in RP_cmm['LoadBalancerClassic']:
                InitConfigELBExternal = ASInitConfigELBClassicExternal()
                InitConfigELBExternal.setup()
                CfmInitArgs['ELBWAITER'] = InitConfigELBExternal
            if 'Internal' in RP_cmm['LoadBalancerClassic']:
                InitConfigELBInternal = ASInitConfigELBClassicInternal()
                InitConfigELBInternal.setup()
                CfmInitArgs['ELBWAITER'] = InitConfigELBInternal
        if 'LoadBalancerApplication' in RP_cmm:
            if 'External' in RP_cmm['LoadBalancerApplication']:
                InitConfigELBExternal = ASInitConfigELBApplicationExternal()
                InitConfigELBExternal.setup()
                CfmInitArgs['ELBWAITER'] = InitConfigELBExternal
            if 'Internal' in RP_cmm['LoadBalancerApplication']:
                InitConfigELBInternal = ASInitConfigELBApplicationInternal()
                InitConfigELBInternal.setup()
                CfmInitArgs['ELBWAITER'] = InitConfigELBInternal

        SecurityGroups = SG_SecurityGroupsEC2().SecurityGroups

        # Resources
        R_LaunchConfiguration = ASLaunchConfiguration('LaunchConfiguration')
        R_LaunchConfiguration.setup(UserDataApp=UserDataApp)
        R_LaunchConfiguration.SecurityGroups.extend(SecurityGroups)

        R_InstanceProfile = IAMInstanceProfile('InstanceProfile')
        R_InstanceProfile.setup()

        # Import role specific cfn definition
        if 'cfn_' + cfg.classenvrole in globals():  # Ex cfn_client_portal
            CfnRole = globals()['cfn_' + cfg.classenvrole]()
            CfmInitArgs.update(CfnRole)

        R_LaunchConfiguration.Metadata = cfm.Metadata(
            cfm.Init(
                InitConfigSets,
                **CfmInitArgs
            ),
            cfm.Authentication({
                'CfnS3Auth': cfm.AuthenticationBlock(
                    type='S3',
                    buckets=[
                        Sub(get_final_value('BucketAppRepository')),
                        Sub(get_final_value('BucketAppData'))
                    ],
                    roleName=Ref('RoleInstance')
                )
            })
        )

        R_LaunchConfigurationSpot = ASLaunchConfiguration('LaunchConfigurationSpot')
        R_LaunchConfigurationSpot.setup(UserDataApp=UserDataApp, spot=True)
        R_LaunchConfigurationSpot.SecurityGroups = R_LaunchConfiguration.SecurityGroups
        R_LaunchConfigurationSpot.SpotPrice = get_final_value('SpotPrice')

        cfg.Resources.extend([
            R_LaunchConfiguration,
            R_InstanceProfile,
        ])

        if 'SpotASG' in RP_cmm:
            cfg.Resources.append(R_LaunchConfigurationSpot)

        self.LaunchConfiguration = R_LaunchConfiguration
        self.Tags = Tags

        # Outputs
        O_AdditionalStorageSize = Output('AdditionalStorageSize')
        O_AdditionalStorageSize.Value = get_final_value('AdditionalStorageSize')

        O_DoNotSignal = Output('DoNotSignal')
        O_DoNotSignal.Value = Ref('DoNotSignal')

        O_EfsMounts = Output('EfsMounts')
        O_EfsMounts.Condition = 'EfsMounts'
        O_EfsMounts.Value = Join(',', Ref('EfsMounts'))

        O_ImageId = Output('ImageId')
        O_ImageId.Value = self.LaunchConfiguration.ImageId

        O_InstanceType = Output('InstanceType')
        O_InstanceType.Value = get_final_value('InstanceType')

        O_KeyName = Output('KeyName')
        O_KeyName.Value = get_final_value('KeyName')

        O_VolumeSize = Output('VolumeSize')
        O_VolumeSize.Value = get_final_value('VolumeSize')

        cfg.Outputs.extend([
            O_AdditionalStorageSize,
            O_DoNotSignal,
            O_EfsMounts,
            O_ImageId,
            O_InstanceType,
            O_KeyName,
            O_VolumeSize,
        ])


class AS_AutoscalingEC2(AS_Autoscaling):
    def __init__(self, key):
        super(AS_AutoscalingEC2, self).__init__()

        LoadBalancers = []
        if 'LoadBalancerClassic' in RP_cmm:
            for n in RP_cmm['LoadBalancerClassic']:
                LoadBalancers.append(Ref('LoadBalancerClassic' + n))

        TargetGroups = []
        if 'LoadBalancerApplication' in RP_cmm:
            for n in RP_cmm['LoadBalancerApplication']:
                TargetGroups.append(Ref('TargetGroup' + n))

        # Resources
        AS_ScheduledActionsEC2('ScheduledAction')
        #AS_ScalingPoliciesEC2()

        LaunchConfiguration = AS_LaunchConfiguration()
        Tags = LaunchConfiguration.Tags

        NotificationConfiguration = ASNotificationConfiguration()
        NotificationConfiguration.setup()

        R_ASG = ASAutoScalingGroup('AutoScalingGroup')
        R_ASG.setup()
        R_ASG.LoadBalancerNames = LoadBalancers
        R_ASG.TargetGroupARNs = TargetGroups
        R_ASG.Tags.extend(Tags)
        R_ASG.Tags.extend([
            If(
                'SpotAuto',
                asg.Tag(('spot-enabled'), 'true', True),
                Ref('AWS::NoValue')
            ),
            If(
                'SpotAutoMinOnDemandNumber',
                asg.Tag(('autospotting_min_on_demand_number'), get_final_value('SpotAutoMinOnDemandNumber'), True),
                Ref('AWS::NoValue')
            )
        ])
        # Notifications currently are not associeted to "any actions" - now using CW events - this way works with autospotting too
        R_ASG.NotificationConfigurations = [NotificationConfiguration]

        R_ASGSpot = ASAutoScalingGroup('AutoScalingGroupSpot')
        R_ASGSpot.setup(spot=True)
        R_ASGSpot.LoadBalancerNames = LoadBalancers
        R_ASGSpot.TargetGroupARNs = TargetGroups
        R_ASGSpot.Tags.extend(Tags)
        R_ASGSpot.NotificationConfigurations = [NotificationConfiguration]
        
        cfg.Resources.extend([
            R_ASG,
        ])

        if 'SpotASG' in RP_cmm:
            cfg.Resources.append(R_ASGSpot)

        self.LaunchConfiguration = LaunchConfiguration

        # Outputs
        O_UpdateMode = Output('UpdateMode')
        O_UpdateMode.Value = Ref('UpdateMode')

        cfg.Outputs.extend([
            O_UpdateMode,
        ])


class AS_AutoscalingECS(AS_Autoscaling):
    def __init__(self, key):
        super(AS_AutoscalingECS, self).__init__()
        # Resources
        R_ScalableTarget = APPASScalableTarget('ScalableTarget')
        R_ScalableTarget.setup()
        R_ScalableTarget.ScheduledActions = AS_ScheduledActionsECS('ScheduledAction').ScheduledActions

        cfg.Resources.extend([
            R_ScalableTarget
        ])


class AS_LifecycleHook(object):
    def __init__(self,key):
        for n, v in RP_cmm[key].iteritems():
            resname = key + str(n)

            # resources
            r_Hook = ASLifecycleHook(resname, name=n, key=v)
            r_Hook.AutoScalingGroupName = Ref('AutoScalingGroup')

            r_HookSpot = ASLifecycleHook(resname, name=n, key=v)
            r_HookSpot.title = resname + 'Spot'
            r_HookSpot.Condition = 'SpotASG'
            r_HookSpot.AutoScalingGroupName = Ref('AutoScalingGroupSpot')
                
            cfg.Resources.extend([
                r_Hook,
            ])

            if 'SpotASG' in RP_cmm:
                cfg.Resources.append(r_HookSpot)
            
# Need to stay as last lines
import_modules(globals())
