import os
import sys

import troposphere.autoscaling as asg
import troposphere.cloudformation as cfm
import troposphere.policies as pol
import troposphere.applicationautoscaling as aas

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
                     get_subvalue, auto_get_props, get_condition, add_obj)
from .cfn import *
from .codedeploy import CD_DeploymentGroup
from .securitygroup import SG_SecurityGroupsEC2
from .iam import IAMInstanceProfile

parent_dir_name = os.getcwd()
sys.path.append(parent_dir_name + '/lib')

try:
    from cfnExt import *
except ImportError:
    pass


# S - AUTOSCALING #
class ASAutoScalingGroup(asg.AutoScalingGroup):
    def __init__(self, title, spot=None, **kwargs):
        super().__init__(title, **kwargs)

        if spot:
            CapacityDesiredASGMainIsSpot = get_endvalue('CapacityDesired')
            CapacityDesiredASGMainIsNotSpot = 0
            CapacityMinASGMainIsSpot = get_endvalue('CapacityMin')
            CapacityMinASGMainIsNotSpot = 0
            self.Condition = 'SpotASG'
            self.LaunchConfigurationName = Ref('LaunchConfigurationSpot')
            self.UpdatePolicy = ASUpdatePolicy(spot=True)
        else:
            CapacityDesiredASGMainIsSpot = 0
            CapacityDesiredASGMainIsNotSpot = get_endvalue('CapacityDesired')
            CapacityMinASGMainIsSpot = 0
            CapacityMinASGMainIsNotSpot = get_endvalue('CapacityMin')
            self.LaunchConfigurationName = Ref('LaunchConfiguration')
            self.UpdatePolicy = ASUpdatePolicy()

        self.AvailabilityZones = GetAZs()

        if cfg.SpotASG:
            self.DesiredCapacity = If('ASGMainIsSpot',
                                      CapacityDesiredASGMainIsSpot,
                                      CapacityDesiredASGMainIsNotSpot)
            self.MinSize = If('ASGMainIsSpot',
                              CapacityMinASGMainIsSpot,
                              CapacityMinASGMainIsNotSpot)
        else:
            self.DesiredCapacity = get_endvalue('CapacityDesired')
            self.MinSize = get_endvalue('CapacityMin')

        self.CreationPolicy = pol.CreationPolicy(
            ResourceSignal=pol.ResourceSignal(
                Count=self.DesiredCapacity,
                Timeout=get_endvalue('AutoscalingCreationTimeout')
            )
        )
        self.HealthCheckGracePeriod = get_endvalue('HealthCheckGracePeriod')
        self.HealthCheckType = get_endvalue('HealthCheckType')
        self.MaxSize = get_endvalue('CapacityMax')
        self.MetricsCollection = [asg.MetricsCollection(
            Granularity='1Minute'
        )]
        self.Tags = [
            asg.Tag(('Name'), Ref('EnvRole'), True),
            asg.Tag(('EnvStackName'), Ref('AWS::StackName'), True),
        ]
        self.TerminationPolicies = ['OldestInstance']

        if cfg.VPCZoneIdentifier == 'SubnetsPublic':
            self.VPCZoneIdentifier = Split(',', get_expvalue('SubnetsPublic'))
        else:
            self.VPCZoneIdentifier = Split(',', get_expvalue('SubnetsPrivate'))


class ASLaunchConfiguration(asg.LaunchConfiguration):
    def __init__(self, title, UserDataApp, spot=None, **kwargs):
        super().__init__(title, **kwargs)

        if spot:
            AutoScalingGroupName = 'AutoScalingGroupSpot'
            self.Condition = 'SpotASG'
        else:
            AutoScalingGroupName = 'AutoScalingGroup'
        self.AssociatePublicIpAddress = get_endvalue(
            'AssociatePublicIpAddress')
        self.BlockDeviceMappings = [
            asg.BlockDeviceMapping(
                DeviceName='/dev/xvda',
                Ebs=asg.EBSBlockDevice(
                    VolumeSize=get_endvalue('VolumeSize'),
                    VolumeType=get_endvalue('VolumeType'),
                )
            ),
            If(
                'AdditionalStorage',
                asg.BlockDeviceMapping(
                    DeviceName=get_endvalue('AdditionalStorageName'),
                    Ebs=asg.EBSBlockDevice(
                        VolumeSize=get_endvalue('AdditionalStorageSize'),
                        VolumeType=get_endvalue('AdditionalStorageType'),
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
            get_endvalue('ImageId'),
        ) if 'ImageIdLatest' in cfg.Parameter else get_endvalue('ImageId')
        self.InstanceMonitoring = get_endvalue('InstanceMonitoring')
        self.InstanceType = get_endvalue('InstanceType')
        self.KeyName = get_endvalue('KeyName')
        self.SecurityGroups = [
            GetAtt('SecurityGroupInstancesRules', 'GroupId'),
        ]
        self.SpotPrice = If('SpotPrice',
                            get_endvalue('SpotPrice'),
                            Ref('AWS::NoValue'))
        self.UserData = Base64(Join('', [
            '#!/bin/bash\n',
            'PATH=/opt/aws/bin:$PATH\n',
            'export BASH_ENV=/etc/profile.d/ibox_env.sh\n',
            'export ENV=$BASH_ENV\n',
            'yum -C list installed aws-cfn-bootstrap || '
            'yum install -y aws-cfn-bootstrap\n',
            Sub(''.join(UserDataApp)),
            'cfn-init -v',
            ' --stack ', Ref('AWS::StackName'),
            ' --role ', Ref('RoleInstance'),
            ' --resource LaunchConfiguration',
            ' --region ', Ref('AWS::Region'), '\n',
            If(
                'DoNotSignal',
                Ref('AWS::NoValue'),
                Sub(
                    'cfn-signal -e $? --stack ${AWS::StackName} '
                    '--role ${RoleInstance} '
                    f'--resource {AutoScalingGroupName} '
                    '--region ${AWS::Region}\n')
            ),
            'rm /var/lib/cloud/instance/sem/config_scripts_user\n',
        ]))


class ASScalingPolicyStep(asg.ScalingPolicy):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        name = self.title  # Ex. ScalingPolicyDown
        self.AdjustmentType = 'ChangeInCapacity'
        self.AutoScalingGroupName = Ref('AutoScalingGroup')
        self.EstimatedInstanceWarmup = get_endvalue(
            f'{name}EstimatedInstanceWarmup')
        self.PolicyType = 'StepScaling'
        self.StepAdjustments = [
            asg.StepAdjustments(
                MetricIntervalLowerBound=get_endvalue(
                    f'{name}MetricIntervalLowerBound1'),
                MetricIntervalUpperBound=get_endvalue(
                    f'{name}MetricIntervalUpperBound1'),
                ScalingAdjustment=get_endvalue(
                    f'{name}ScalingAdjustment1')
            ),
            asg.StepAdjustments(
                MetricIntervalLowerBound=get_endvalue(
                    f'{name}MetricIntervalLowerBound2'),
                MetricIntervalUpperBound=get_endvalue(
                    f'{name}MetricIntervalUpperBound2'),
                ScalingAdjustment=get_endvalue(
                    f'{name}ScalingAdjustment2')
            ),
            asg.StepAdjustments(
                ScalingAdjustment=get_endvalue(
                    f'{name}ScalingAdjustment3')
            )
        ]


class ASScheduledAction(asg.ScheduledAction):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        name = self.title
        self.Condition = name

        if cfg.SpotASG:
            self.AutoScalingGroupName = If('ASGMainIsSpot',
                                           Ref('AutoScalingGroupSpot'),
                                           Ref('AutoScalingGroup'))
        else:
            self.AutoScalingGroupName = Ref('AutoScalingGroup')

        self.DesiredCapacity = If(
            f'{name}CapacityDesiredSize',
            get_endvalue('CapacityDesired'),
            get_endvalue(f'{name}DesiredSize',
                         nocondition=f'{name}KeepDesiredSize')
        )
        self.MinSize = If(
            f'{name}CapacityMinSize',
            get_endvalue('CapacityMin'),
            get_endvalue(f'{name}MinSize',
                         nocondition=f'{name}KeepMinSize')
        )
        self.MaxSize = If(
            f'{name}CapacityMaxSize',
            get_endvalue('CapacityMax'),
            get_endvalue(f'{name}MaxSize',
                         nocondition=f'{name}KeepMaxSize')
        )
        self.Recurrence = get_endvalue(f'{name}Recurrence')
        self.StartTime = If(
            f'{name}StartTimeOverride',
            Ref(f'{name}StartTime'),
            Ref('AWS::NoValue')
        )


class ASLifecycleHook(asg.LifecycleHook):
    def __init__(self, title, name, key, **kwargs):
        super().__init__(title, **kwargs)

        auto_get_props(self, key)
        self.HeartbeatTimeout = get_endvalue(f'{title}HeartbeatTimeout')

# E - AUTOSCALING #


class ASScalingPolicyStepDown(ASScalingPolicyStep):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        name = self.title
        self.StepAdjustments[2].MetricIntervalUpperBound = get_endvalue(
            f'{name}MetricIntervalUpperBound3')


class ASScalingPolicyStepUp(ASScalingPolicyStep):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        name = self.title
        self.StepAdjustments[2].MetricIntervalLowerBound = get_endvalue(
            f'{name}MetricIntervalLowerBound3')


# S - APPLICATION AUTOSCALING #
class APPASScalingPolicy(aas.ScalingPolicy):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        name = self.title
        self.PolicyName = self.title
        self.ScalingTargetId = Ref('ScalableTarget')


class APPASScalingPolicyStep(APPASScalingPolicy):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        name = self.title
        self.PolicyType = 'StepScaling'
        self.StepScalingPolicyConfiguration = (
            aas.StepScalingPolicyConfiguration(
                AdjustmentType='ChangeInCapacity',
                MetricAggregationType='Average',
                StepAdjustments=[
                    aas.StepAdjustment(
                        MetricIntervalLowerBound=get_endvalue(
                            f'{name}MetricIntervalLowerBound1'),
                        MetricIntervalUpperBound=get_endvalue(
                            f'{name}MetricIntervalUpperBound1'),
                        ScalingAdjustment=get_endvalue(
                            f'{name}ScalingAdjustment1')
                        ),
                    aas.StepAdjustment(
                        MetricIntervalLowerBound=get_endvalue(
                            f'{name}MetricIntervalLowerBound2'),
                        MetricIntervalUpperBound=get_endvalue(
                            f'{name}MetricIntervalUpperBound2'),
                        ScalingAdjustment=get_endvalue(
                            f'{name}ScalingAdjustment2')
                        ),
                    aas.StepAdjustment(
                        ScalingAdjustment=get_endvalue(
                            f'{name}ScalingAdjustment3')
                    )
                ]
            )
        )


class APPASScalingPolicyStepDown(APPASScalingPolicyStep):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        name = self.title
        step = self.StepScalingPolicyConfiguration.StepAdjustments[2]
        step.MetricIntervalUpperBound = get_endvalue(
            f'{name}MetricIntervalUpperBound3')


class APPASScalingPolicyStepUp(APPASScalingPolicyStep):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        name = self.title
        step = self.StepScalingPolicyConfiguration.StepAdjustments[2]
        step.MetricIntervalLowerBound = get_endvalue(
            f'{name}MetricIntervalLowerBound3')


class APPASScheduledAction(aas.ScheduledAction):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        name = self.title
        self.ScalableTargetAction = aas.ScalableTargetAction(
            MinCapacity=If(
                f'{name}CapacityMinSize',
                get_endvalue('CapacityMin'),
                get_endvalue(
                    f'{name}MinSize', nocondition=f'{name}KeepMinSize')
            ),
            MaxCapacity=If(
                f'{name}CapacityMaxSize',
                get_endvalue('CapacityMax'),
                get_endvalue(
                    f'{name}MaxSize', nocondition=f'{name}KeepMaxSize')
            )
        )
        self.Schedule = get_endvalue(f'{name}Recurrence')
        self.ScheduledActionName = name
        self.StartTime = If(
            f'{name}StartTimeOverride',
            Ref(f'{name}StartTime'),
            Ref('AWS::NoValue')
        )


class APPASScalableTarget(aas.ScalableTarget):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        self.MaxCapacity = get_endvalue('CapacityMax')
        self.MinCapacity = get_endvalue('CapacityMin')
        self.ResourceId = get_subvalue(
            'service/${1E}/${Service.Name}', 'Cluster', 'ClusterStack')
        self.RoleARN = get_expvalue('RoleEC2ContainerServiceAutoscale', '')
        self.ScalableDimension = 'ecs:service:DesiredCount'
        self.ServiceNamespace = 'ecs'

# E - APPLICATION AUTOSCALING #

# ############################################
# ### START STACK META CLASSES AND METHODS ###
# ############################################


# S - AUTOSCALING #
class ASUpdatePolicy(pol.UpdatePolicy):
    def __init__(self, spot=None, **kwargs):
        super().__init__(**kwargs)

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
                MaxBatchSize=get_endvalue('RollingUpdateMaxBatchSize'),
                # MinInstancesInService=get_endvalue('RollingUpdateMinInstancesInService'),
                MinInstancesInService=get_endvalue('CapacityDesired'),
                MinSuccessfulInstancesPercent=get_endvalue(
                    'RollingUpdateMinSuccessfulInstancesPercent'),
                PauseTime=get_endvalue('RollingUpdatePauseTime'),
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
        self.AutoScalingScheduledAction = pol.AutoScalingScheduledAction(
            IgnoreUnmodifiedGroupSizeProperties=True
        )


class ASInitConfigSets(cfm.InitConfigSets):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if cfg.Apps:
            CODEDEPLOY = If(
                'DeploymentGroup', 'CODEDEPLOY', Ref('AWS::NoValue'))
        else:
            CODEDEPLOY = Ref('AWS::NoValue')

        CWAGENT = If(
            'CloudWatchAgent', 'CWAGENT', Ref('AWS::NoValue'))

        if cfg.LoadBalancerClassic or cfg.LoadBalancerApplication:
            ELBWAITER = 'ELBWAITER'
        else:
            ELBWAITER = Ref('AWS::NoValue')

        self.data = {
            'default': [
                'REPOSITORIES',
                'PACKAGES',
                'SETUP',
                CODEDEPLOY,
                'SERVICES',
                CWAGENT,
                ELBWAITER,
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
                    'export EnvBrand=', cfg.BrandDomain, '\n',
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
                    'path=Resources.LaunchConfiguration'
                    '.Metadata.CloudFormationInitVersion\n',
                    'action=/opt/aws/bin/cfn-init -v',
                    ' --stack ', Ref('AWS::StackName'),
                    ' --role ', Ref('RoleInstance'),
                    ' --resource LaunchConfiguration',
                    ' --region ', Ref('AWS::Region'), '\n',
                    'runas=root\n'
                ])
            },
            # '/usr/local/bin/chamber': {
            #     'mode': '000755',
            #     'source': Sub(
            #         f'https://{cfg.BucketAppRepository}'
            #         '.s3.${AWS::Region}.amazonaws.com/ibox-tools/chamber'),
            #     'owner': 'root',
            #     'group': 'root',
            # },
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
                    # 'command': Join('', [
                    #    'file -s ',
                    #    get_endvalue('AdditionalStorageName'), '1',
                    #    ' | grep -q "ext[34] filesystem" || ',
                    #    '{ parted -s ', get_endvalue('AdditionalStorageName'),
                    #    ' mklabel gpt', ' && ',
                    #    'parted -s ', get_endvalue('AdditionalStorageName'),
                    #    ' mkpart primary ext2 1 ',
                    #    get_endvalue('AdditionalStorageSize'), 'G', ' && ',
                    #    'mkfs.ext4 ', get_endvalue('AdditionalStorageName'),
                    #    '1', ' || continue; }\n',
                    #    'mkdir -p /data', ' && ',
                    #    'mount /dev/xvdx1 /data'
                    # ])
                    'command': get_subvalue(
                        'file -s ${1M}1 | grep -q "ext[34] filesystem" ||'
                        ' { parted -s ${1M} mklabel gpt &&'
                        ' parted -s ${1M} mkpart primary ext2 1 ${2M}G &&'
                        ' mkfs.ext4 ${1M}1 || continue; }\nmkdir -p /data &&'
                        ' mount ${1M}1 /data',
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
                        '    mount -t nfs4 -o nfsvers=4,rsize=1048576,'
                        'wsize=1048576,hard,timeo=600,retrans=2 ',
                        '    efs-${mounts}.', cfg.HostedZoneNamePrivate, ':/ ',
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
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

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
                'source': Sub(
                    'https://aws-codedeploy-${AWS::Region}'
                    '.s3.amazonaws.com/latest/install'),
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
                    'files': [
                        '/etc/codedeploy-agent/conf/codedeployagent.yml'
                    ]
                }
            }
        }


class ASInitConfigCloudWatchAgent(cfm.InitConfig):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        self.packages = {
            'rpm': {
                'amazon-cloudwatch-agent': (
                    'https://s3.amazonaws.com'
                    '/amazoncloudwatch-agent/amazon_linux/amd64/latest/'
                    'amazon-cloudwatch-agent.rpm'
                )
            }
        }
        self.files = {
            '/opt/aws/amazon-cloudwatch-agent/etc/'
            'amazon-cloudwatch-agent.json': {
                'content': Join('', [
                    '{\n',
                    '  "metrics": {\n',
                    '    "append_dimensions": {\n',
                    '      "AutoScalingGroupName": '
                    '"${aws:AutoScalingGroupName}",\n',
                    '      "InstanceId": "${!aws:InstanceId}"\n',
                    '    },\n',
                    '    "aggregation_dimensions": [\n',
                    '      ["AutoScalingGroupName"]\n',
                    '    ],\n',
                    '    "metrics_collected": {\n',
                    '      "mem": {\n',
                    '        "measurement": [\n',
                    '          "mem_used_percent"\n',
                    '        ]\n',
                    '      },\n',
                    '      "disk": {\n',
                    '        "resources": [\n',
                    '          "/"\n',
                    '        ],\n',
                    '        "measurement": [\n',
                    '          {\n',
                    '            "name": "disk_used_percent",\n',
                    '            "rename": "root_disk_used_percent"\n',
                    '          }\n',
                    '        ],\n',
                    '        "drop_device": true\n',
                    '      }\n',
                    '    }\n',
                    '  }\n',
                    '}\n',
                ]),
            },
        }
        self.services = {
            'sysvinit': {
                'amazon-cloudwatch-agent': {
                    'ensureRunning': 'true',
                    'files': [
                        '/opt/aws/amazon-cloudwatch-agent/etc/'
                        'amazon-cloudwatch-agent.json'
                    ]
                }
            }
        }


class ASInitConfigApps(cfm.InitConfig):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        name = self.title  # Ex. Apps1
        reponame = f'{name}RepoName'
        n = name.replace('Apps', '')
        envappversion = f'EnvApp{n}Version'

        self.sources = {
            '/tmp/ibox/': If(
                'DeployRevision',
                Ref('AWS::NoValue'),
                get_subvalue(
                    'https://%s.s3-${AWS::Region}.amazonaws.com/'
                    '${1M}/${1M}-${%s}.tar.gz' % (
                        cfg.BucketAppRepository, envappversion),
                    reponame, ''
                )
            )
        }
        self.commands = {
            '01_setup': If(
                'DeployRevision',
                Ref('AWS::NoValue'),
                {
                    'command': get_subvalue(
                        'EnvAppVersion=${%s} EnvRepoName=${1M} '
                        '/tmp/ibox/bin/setup.sh' % envappversion,
                        reponame
                    )
                }
            ),
            '02_setup_reboot_codedeploy': If(
                'DeployRevision',
                {
                    'command': get_subvalue(
                        'EnvAppVersion=${%s} EnvRepoName=${1M} '
                        '/opt/ibox/${1M}/live/bin/setup.sh' % envappversion,
                        reponame
                    ),
                    'test': 'test -e /var/lib/cloud/instance/sem/'
                    'config_ssh_authkey_fingerprints'
                },
                Ref('AWS::NoValue')
            ),
            '03_rmdir_tmp_ibox': {
                'command': 'rm -fr /tmp/ibox'
            }
        }


class ASInitConfigAppsBuildAmi(ASInitConfigApps):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        for n, v in self.sources.items():
            if not isinstance(v, dict):
                if 'Fn::If' in v.data:
                    self.sources[n] = v.data['Fn::If'][2]

        for n, v in self.commands.items():
            if not isinstance(v, dict):
                if 'Fn::If' in v.data:
                    self.commands[n] = v.data['Fn::If'][2]


class ASInitConfigELBClassicExternal(cfm.InitConfig):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.commands = {
            'ELBClassicExternalHealthCheck': {
                'command': Join('', [
                    'until [ "$state" = \'"InService"\' ]; do',
                    '  state=$(aws --region ', Ref('AWS::Region'),
                    ' elb describe-instance-health',
                    '  --load-balancer-name ',
                    Ref('LoadBalancerClassicExternal'),
                    '  --instances $(curl -s '
                    'http://169.254.169.254/latest/meta-data/instance-id)',
                    '  --query InstanceStates[0].State);',
                    '  sleep 10;',
                    'done'
                ])
            }
        }


class ASInitConfigELBClassicInternal(cfm.InitConfig):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.commands = {
            'ELBClassicInternalHealthCheck': {
                'command': Join('', [
                    'until [ "$state" = \'"InService"\' ]; do',
                    '  state=$(aws --region ', Ref('AWS::Region'),
                    ' elb describe-instance-health',
                    '  --load-balancer-name ',
                    Ref('LoadBalancerClassicInternal'),
                    '  --instances $(curl -s '
                    'http://169.254.169.254/latest/meta-data/instance-id)',
                    '  --query InstanceStates[0].State);',
                    '  sleep 10;',
                    'done'
                ])
            }
        }


class ASInitConfigELBApplicationExternal(cfm.InitConfig):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.commands = {
            'ELBApplicationExternalHealthCheck': {
                'command': Join('', [
                    'until [ "$state" = \'"healthy"\' ]; do',
                    '  state=$(aws --region ', Ref('AWS::Region'),
                    ' elbv2 describe-target-health',
                    '  --target-group-arn ', Ref('TargetGroupExternal'),
                    '  --targets Id=$(curl -s '
                    'http://169.254.169.254/latest/meta-data/instance-id)',
                    '  --query '
                    'TargetHealthDescriptions[0].TargetHealth.State);',
                    '  sleep 10;',
                    'done'
                ])
            }
        }


class ASInitConfigELBApplicationInternal(cfm.InitConfig):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.commands = {
            'ELBApplicationInternalHealthCheck': {
                'command': Join('', [
                    'until [ "$state" = \'"healthy"\' ]; do',
                    '  state=$(aws --region ', Ref('AWS::Region'),
                    ' elbv2 describe-target-health',
                    '  --target-group-arn ', Ref('TargetGroupInternal'),
                    '  --targets Id=$(curl -s '
                    'http://169.254.169.254/latest/meta-data/instance-id)',
                    '  --query '
                    'TargetHealthDescriptions[0].TargetHealth.State);',
                    '  sleep 10;',
                    'done'
                ])
            }
        }


class ASNotificationConfiguration(asg.NotificationConfigurations):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.NotificationTypes = [
            'autoscaling:EC2_INSTANCE_LAUNCH',
            'autoscaling:EC2_INSTANCE_TERMINATE',
        ]
        self.TopicARN = get_expvalue('SNSTopicASGNotification')
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

        # parameters
        P_MinSize = Parameter(f'{resname}MinSize')
        P_MinSize.Description = (
            f'{resname}Min Capacity - k to keep current value - '
            'empty for default based on env/role')

        P_MaxSize = Parameter(f'{resname}MaxSize')
        P_MaxSize.Description = (
            f'{resname}Max Capacity - k to keep current value - '
            'empty for default based on env/role')

        P_Recurrence = Parameter(f'{resname}Recurrence')
        P_Recurrence.Description = (
            f'{resname}Recurrence - k to keep current value - '
            'empty for default based on env/role')

        P_StartTime = Parameter(f'{resname}StartTime')
        P_StartTime.Description = (
            f'{resname}StartTime - k to keep current value - '
            'empty for default based on env/role')

        add_obj([
            P_MinSize,
            P_MaxSize,
            P_Recurrence,
            P_StartTime,
        ])

        # conditions
        C_KeepMinSize = get_condition(
            f'{resname}KeepMinSize', 'equals', 'k', f'{resname}MinSize')

        C_KeepMaxSize = get_condition(
            f'{resname}KeepMaxSize', 'equals', 'k', f'{resname}MaxSize')

        C_CapacityMinSize = get_condition(
            f'{resname}CapacityMinSize', 'equals', 'CapacityMin',
            f'{resname}MinSize')

        C_CapacityMaxSize = get_condition(
            f'{resname}CapacityMaxSize', 'equals', 'CapacityMax',
            f'{resname}MaxSize')

        C_Recurrence = get_condition(
            resname, 'not_equals', 'None', f'{resname}Recurrence')

        add_obj([
            C_KeepMinSize,
            C_KeepMaxSize,
            C_CapacityMinSize,
            C_CapacityMaxSize,
            C_Recurrence,
        ])

        # outputs
        out_String = []
        out_Map = {}
        for k in OutKey:
            out_String.append('%s=${%s}' % (k, k))  # Ex. 'MinSize=${MinSize}'
            out_Map.update({
                k: get_endvalue(f'{resname}{k}') if k != 'StartTime'
                else Ref(f'{resname}{k}')})

        O_ScheduledAction = Output(resname)
        O_ScheduledAction.Value = Sub(','.join(out_String), **out_Map)

        add_obj(O_ScheduledAction)


class AS_ScheduledActionsEC2(object):
    def __init__(self, key):
        for n, v in getattr(cfg, key).items():
            resname = f'{key}{n}'
            # parameters
            p_DesiredSize = Parameter(f'{resname}DesiredSize')
            p_DesiredSize.Description = (
                f'{resname}Desired Capacity - k to keep current value - '
                'empty for default based on env/role')

            add_obj(p_DesiredSize)

            # conditions
            c_KeepDesiredSize = get_condition(
                f'{resname}KeepDesiredSize', 'equals', 'k',
                f'{resname}DesiredSize')

            c_CapacityDesiredSize = get_condition(
                f'{resname}CapacityDesiredSize', 'equals', 'CapacityDesired',
                f'{resname}DesiredSize')

            add_obj([
                c_KeepDesiredSize,
                c_CapacityDesiredSize,
            ])

            # resources
            OutKey = ['DesiredSize']

            AS_ScheduledAction(resname, OutKey)
            r_ScheduledAction = ASScheduledAction(resname)

            add_obj(r_ScheduledAction)


class AS_ScheduledActionsECS(object):
    def __init__(self, key):
        ScheduledActions = []
        for n, v in getattr(cfg, key).items():
            resname = f'{key}{n}'
            # conditions
            c_disable = {f'{resname}Disable': Or(
                Not(Condition(resname)),
                And(
                    Condition(f'{resname}KeepMaxSize'),
                    Condition(f'{resname}KeepMinSize'),
                )
            )}

            add_obj(c_disable)

            # resources
            AS_ScheduledAction(resname, [])
            ScheduledAction = APPASScheduledAction(resname)

            ScheduledActions.append(
                If(
                    f'{resname}Disable',
                    Ref('AWS::NoValue'),
                    ScheduledAction,
                )
            )

        self.ScheduledActions = ScheduledActions


class AS_ScalingPoliciesStepEC2(object):
    def __init__(self, key):
        R_Down = ASScalingPolicyStepDown('ScalingPolicyDown')

        R_Up = ASScalingPolicyStepUp('ScalingPolicyUp')

        add_obj([
            R_Down,
            R_Up,
        ])


class AS_ScalingPoliciesStepECS(object):
    def __init__(self, key):
        R_Down = APPASScalingPolicyStepDown('ScalingPolicyDown')

        R_Up = APPASScalingPolicyStepUp('ScalingPolicyUp')

        add_obj([
            R_Down,
            R_Up,
        ])


class AS_ScalingPoliciesTracking(object):
    def __init__(self, key):
        ScalingPolicyTrackings_Out_String = []
        ScalingPolicyTrackings_Out_Map = {}
        for n, v in getattr(cfg, key).items():
            if not ('Enabled' in v and v['Enabled'] is True):
                continue

            resname = f'{key}{n}'

            # Autoscaling
            if 'TargetTrackingConfiguration' in v:
                TargetTrackingConfigurationName = (
                    'TargetTrackingConfiguration')
                p_type = 'autoscaling'
            # Application Autoscaling
            elif 'TargetTrackingScalingPolicyConfiguration' in v:
                TargetTrackingConfigurationName = (
                    'TargetTrackingScalingPolicyConfiguration')
                p_type = 'application_autoscaling'

            basename = f'{resname}{TargetTrackingConfigurationName}'

            # parameters
            p_Value = Parameter(f'{basename}TargetValue')
            p_Value.Description = (
                f'Tracking {n} Value - 0 to disable - '
                'empty for default based on env/role')

            p_Statistic = Parameter(
                f'{basename}CustomizedMetricSpecificationStatistic')
            p_Statistic.Description = (
                f'Tracking {n} Statistic - 0 to disable - '
                'empty for default based on env/role')

            add_obj([
                p_Value,
                p_Statistic,
            ])

            #  conditions
            c_TargetValue = get_condition(
                resname, 'not_equals', '0', f'{basename}TargetValue')

            add_obj(c_TargetValue)

            # outputs
            if v['Type'] == 'Cpu' or (
                    v['Type'] == 'Custom' and
                    v[TargetTrackingConfigurationName]
                    ['CustomizedMetricSpecification']
                    ['MetricName'] == 'CPUUtilization'):
                # Use Cpu Metric
                ScalingPolicyTrackings_Out_String.append(
                        'Cpu${Statistic}:${Cpu}')

                if v['Type'] == 'Custom':
                    statistic = get_endvalue(
                        f'{basename}CustomizedMetricSpecificationStatistic')
                else:
                    statistic = ''

                ScalingPolicyTrackings_Out_Map.update({
                    'Statistic': statistic,
                    'Cpu': get_endvalue(f'{basename}TargetValue'),
                })

            # resources
            if p_type == 'autoscaling':
                r_Tracking = asg.ScalingPolicy(resname)
            else:
                r_Tracking = aas.ScalingPolicy(resname)

            auto_get_props(r_Tracking, v, recurse=True)
            r_Tracking.Condition = resname

            add_obj(r_Tracking)

        # Outputs
        O_Policy = Output(key)
        O_Policy.Value = Sub(
            ','.join(ScalingPolicyTrackings_Out_String),
            **ScalingPolicyTrackings_Out_Map)

        add_obj([
            O_Policy,
        ])


class AS_LaunchConfiguration(object):
    def __init__(self):
        InitConfigSets = ASInitConfigSets()

        CfmInitArgs = {}
        IBoxEnvApp = []
        Tags = []
        UserDataApp = []

        for n in cfg.Apps:
            name = f'Apps{n}'              # Ex. Apps1
            envname = f'EnvApp{n}Version'  # Ex EnvApp1Version
            reponame = f'{name}RepoName'   # Ex Apps1RepoName

            UserDataApp.extend(['#${%s}\n' % envname])

            p_EnvAppVersion = Parameter(envname)
            p_EnvAppVersion.Description = f'Application {n} version'
            p_EnvAppVersion.AllowedPattern = '^[a-zA-Z0-9-_.]*$'

            p_AppsRepoName = Parameter(reponame)
            p_AppsRepoName.Description = (
                f'App {n} Repo Name - empty for default based on env/role')
            p_AppsRepoName.AllowedPattern = '^[a-zA-Z0-9-_.]*$'

            # parameters
            add_obj([
                p_EnvAppVersion,
                p_AppsRepoName,
            ])

            # conditions
            add_obj({
                name: And(
                    Not(Equals(Ref(envname), '')),
                    Not(get_condition('', 'equals', 'None', reponame))
                )
            })

            InitConfigApps = ASInitConfigApps(name)
            CfmInitArgs[name] = InitConfigApps

            InitConfigAppsBuilAmi = ASInitConfigAppsBuildAmi(name)
            # AUTOSPOT - Let cfn-init always prepare instances on boot
            # CfmInitArgs[name + 'BuildAmi'] = InitConfigAppsBuilAmi
            CfmInitArgs[name] = InitConfigAppsBuilAmi

            IBoxEnvApp.extend([
                f'export EnvApp{n}Version=', Ref(envname), "\n",
                f'export EnvRepo{n}Name=', get_endvalue(reponame), "\n",
            ])

            InitConfigSetsApp = If(name, name, Ref('AWS::NoValue'))
            InitConfigSetsAppBuilAmi = If(
                name, f'{name}BuildAmi', Ref('AWS::NoValue'))
            IndexSERVICES = InitConfigSets.data['default'].index('SERVICES')
            InitConfigSets.data['default'].insert(
                IndexSERVICES, InitConfigSetsApp)
            # AUTOSPOT - Let cfn-init always prepare instances on boot
            # InitConfigSets.data['buildamifull'].append(
            #    InitConfigSetsAppBuilAmi)
            InitConfigSets.data['buildamifull'].append(InitConfigSetsApp)

            Tags.append(asg.Tag(envname, Ref(envname), True))

            # resources
            # FOR MULTIAPP CODEDEPLOY
            if len(cfg.Apps) > 1:
                r_DeploymentGroup = CDDeploymentGroup(f'DeploymentGroup{name}')
                r_DeploymentGroup.setup(index=n)

                add_obj(r_DeploymentGroup)

            # outputs
            Output_app = Output(envname)
            Output_app.Value = Ref(envname)
            add_obj(Output_app)

            Output_repo = Output(reponame)
            Output_repo.Value = get_endvalue(reponame)
            add_obj(Output_repo)

        InitConfigSetup = ASInitConfigSetup()
        InitConfigSetup.ibox_env_app = IBoxEnvApp
        InitConfigSetup.setup()

        InitConfigCodeDeploy = ASInitConfigCodeDeploy()

        CfmInitArgs['SETUP'] = InitConfigSetup
        CfmInitArgs['CWAGENT'] = ASInitConfigCloudWatchAgent('')

        if cfg.Apps:
            CfmInitArgs['CODEDEPLOY'] = InitConfigCodeDeploy
            CD_DeploymentGroup()

        # LoadBalancerClassic External
        if cfg.LoadBalancerClassicExternal:
            InitConfigELBExternal = ASInitConfigELBClassicExternal()
            CfmInitArgs['ELBWAITER'] = InitConfigELBExternal

        # LoadBalancerClassic Internal
        if cfg.LoadBalancerClassicInternal:
            InitConfigELBInternal = ASInitConfigELBClassicInternal()
            CfmInitArgs['ELBWAITER'] = InitConfigELBInternal

        # LoadBalancerApplication External
        if cfg.LoadBalancerApplicationExternal:
            InitConfigELBExternal = ASInitConfigELBApplicationExternal()
            CfmInitArgs['ELBWAITER'] = InitConfigELBExternal

        # LoadBalancerApplication Internal
            InitConfigELBInternal = ASInitConfigELBApplicationInternal()
            CfmInitArgs['ELBWAITER'] = InitConfigELBInternal

        SecurityGroups = SG_SecurityGroupsEC2().SecurityGroups

        # Resources
        R_LaunchConfiguration = ASLaunchConfiguration(
            'LaunchConfiguration', UserDataApp=UserDataApp)
        R_LaunchConfiguration.SecurityGroups.extend(SecurityGroups)

        R_InstanceProfile = IAMInstanceProfile('InstanceProfile')

        # Import role specific cfn definition
        cfn_envrole = f'cfn_{cfg.classenvrole}'
        if cfn_envrole in globals():  # Ex cfn_client_portal
            CfnRole = globals()[cfn_envrole]()
            CfmInitArgs.update(CfnRole)

        R_LaunchConfiguration.Metadata = cfm.Metadata(
            {
                'CloudFormationInitVersion': If(
                    'CloudFormationInit',
                    Ref('EnvStackVersion'),
                    Ref('AWS::NoValue'),
                )
            },
            cfm.Init(
                InitConfigSets,
                **CfmInitArgs
            ),
            cfm.Authentication({
                'CfnS3Auth': cfm.AuthenticationBlock(
                    type='S3',
                    buckets=[
                        Sub(cfg.BucketAppRepository),
                        Sub(cfg.BucketAppData)
                    ],
                    roleName=Ref('RoleInstance')
                )
            })
        )

        R_LaunchConfigurationSpot = ASLaunchConfiguration(
            'LaunchConfigurationSpot', UserDataApp=UserDataApp, spot=True)
        R_LaunchConfigurationSpot.SecurityGroups = (
            R_LaunchConfiguration.SecurityGroups)
        R_LaunchConfigurationSpot.SpotPrice = get_endvalue('SpotPrice')

        add_obj([
            R_LaunchConfiguration,
            R_InstanceProfile,
        ])
        if cfg.SpotASG:
            add_obj(R_LaunchConfigurationSpot)

        self.LaunchConfiguration = R_LaunchConfiguration
        self.Tags = Tags


class AS_AutoscalingEC2(object):
    def __init__(self, key):
        LoadBalancers = []
        for n in cfg.LoadBalancerClassic:
            LoadBalancers.append(Ref(f'LoadBalancerClassic{n}'))

        TargetGroups = []
        for n in cfg.LoadBalancerApplication:
            TargetGroups.append(Ref(f'TargetGroup{n}'))

        # Resources
        AS_ScheduledActionsEC2('ScheduledAction')
        # AS_ScalingPoliciesEC2()

        LaunchConfiguration = AS_LaunchConfiguration()
        Tags = LaunchConfiguration.Tags

        R_ASG = ASAutoScalingGroup('AutoScalingGroup')
        R_ASG.LoadBalancerNames = LoadBalancers
        R_ASG.TargetGroupARNs = TargetGroups
        R_ASG.Tags.extend(Tags)
        R_ASG.Tags.extend([
            If(
                'SpotAuto',
                asg.Tag('spot-enabled', 'true', True),
                Ref('AWS::NoValue')
            ),
            If(
                'SpotAutoMinOnDemandNumber',
                asg.Tag(
                    'autospotting_min_on_demand_number',
                    get_endvalue('SpotAutoMinOnDemandNumber'), True),
                Ref('AWS::NoValue')
            ),
            If(
                'SpotAutoAllowedInstances',
                asg.Tag(
                    'autospotting_allowed_instance_types',
                    get_endvalue('SpotAutoAllowedInstances'), True),
                Ref('AWS::NoValue')
            )
        ])

        R_ASGSpot = ASAutoScalingGroup('AutoScalingGroupSpot', spot=True)
        R_ASGSpot.LoadBalancerNames = LoadBalancers
        R_ASGSpot.TargetGroupARNs = TargetGroups
        R_ASGSpot.Tags.extend(Tags)

        # Notifications currently are not associeted to "any actions" -
        # now using CW events - this way works with autospotting too
        try:
            cfg.NotificationConfiguration
        except Exception as e:
            pass
        else:
            NotificationConfiguration = ASNotificationConfiguration()
            R_ASG.NotificationConfigurations = [NotificationConfiguration]
            R_ASGSpot.NotificationConfigurations = [NotificationConfiguration]

        add_obj([
            R_ASG,
        ])

        if cfg.SpotASG:
            add_obj(R_ASGSpot)

        self.LaunchConfiguration = LaunchConfiguration


class AS_AutoscalingECS(object):
    def __init__(self, key):
        # Resources
        R_ScalableTarget = APPASScalableTarget('ScalableTarget')
        R_ScalableTarget.ScheduledActions = (
            AS_ScheduledActionsECS('ScheduledAction').ScheduledActions)

        add_obj([
            R_ScalableTarget
        ])


class AS_LifecycleHook(object):
    def __init__(self, key):
        for n, v in getattr(cfg, key).items():
            resname = f'{key}{n}'

            # resources
            r_Hook = ASLifecycleHook(resname, name=n, key=v)
            r_Hook.AutoScalingGroupName = Ref('AutoScalingGroup')

            r_HookSpot = ASLifecycleHook(resname, name=n, key=v)
            r_HookSpot.title = f'{resname}Spot'
            r_HookSpot.Condition = 'SpotASG'
            r_HookSpot.AutoScalingGroupName = Ref('AutoScalingGroupSpot')

            add_obj([
                r_Hook,
            ])

            if cfg.SpotASG:
                add_obj(r_HookSpot)
