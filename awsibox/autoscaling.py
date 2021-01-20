import troposphere.autoscaling as asg
import troposphere.ec2 as ec2
import troposphere.cloudformation as cfm
import troposphere.policies as pol
import troposphere.applicationautoscaling as aas

from .common import *
from .shared import (Parameter, get_endvalue, get_expvalue, get_subvalue,
                     auto_get_props, get_condition, add_obj)
from .cfn import *
from .codedeploy import CD_DeploymentGroup
from .securitygroup import SG_SecurityGroupsEC2
from .iam import IAMInstanceProfile

try:
    from cfnExt import *
except ModuleNotFoundError:
    pass


class ASLaunchTemplateData(ec2.LaunchTemplateData):
    def __init__(self, title, UserDataApp, **kwargs):
        super().__init__(title, **kwargs)
        auto_get_props(self, 'LaunchTemplateData')
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
            ' --resource LaunchTemplate',
            ' --region ', Ref('AWS::Region'), '\n',
            If(
                'DoNotSignal',
                Ref('AWS::NoValue'),
                Sub(
                    'cfn-signal -e $? --stack ${AWS::StackName} '
                    '--role ${RoleInstance} '
                    f'--resource AutoScalingGroup '
                    '--region ${AWS::Region}\n')
            ),
            'rm /var/lib/cloud/instance/sem/config_scripts_user\n',
        ]))


# ############################################
# ### START STACK META CLASSES AND METHODS ###
# ############################################


class ASInitConfigSets(cfm.InitConfigSets):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if cfg.Apps:
            CODEDEPLOY = If(
                'DeploymentGroup', 'CODEDEPLOY', Ref('AWS::NoValue'))
        else:
            CODEDEPLOY = Ref('AWS::NoValue')

        CWAGENT = If('CloudWatchAgent', 'CWAGENT', Ref('AWS::NoValue'))

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
                    'path=Resources.LaunchTemplate'
                    '.Metadata.CloudFormationInitVersion\n',
                    'action=/opt/aws/bin/cfn-init -v',
                    ' --stack ', Ref('AWS::StackName'),
                    ' --role ', Ref('RoleInstance'),
                    ' --resource LaunchTemplate',
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
                'LaunchTemplateDataBlockDeviceMappingsAdditionalStorageMount',
                {
                    'command': get_subvalue(
                        'file -s ${1M}1 | grep -q "ext[34] filesystem" ||'
                        ' { parted -s ${1M} mklabel gpt &&'
                        ' parted -s ${1M} mkpart primary ext2 1 ${2M}G &&'
                        ' mkfs.ext4 ${1M}1 || continue; }\nmkdir -p /data &&'
                        ' mount ${1M}1 /data',
                        [
                            ('LaunchTemplateDataBlockDeviceMappings'
                             'AdditionalStorageDeviceName'),
                            ('LaunchTemplateDataBlockDeviceMappings'
                             'AdditionalStorageEbsVolumeSize'),
                        ]
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


# ##########################################
# ### END STACK META CLASSES AND METHODS ###
# ##########################################

def AS_ScheduledActionsEC2(key):
    for n, v in getattr(cfg, key).items():
        resname = f'{key}{n}'

        # trick - obj mapped props have same name/key of the one used for
        # code, so i create a subpro named IBOXCODE and used that as
        # rootdict
        try:
            rootdict = cfg.ScheduledAction[n]['IBOXCODE']
        except Exception:
            kwargs = {}
        else:
            kwargs = {'rootdict': rootdict}

        r_ScheduledActions = asg.ScheduledAction(resname)
        auto_get_props(r_ScheduledActions, **kwargs)
        add_obj(r_ScheduledActions)


def AS_ScalingPolicies(key):
    Out_String = []
    Out_Map = {}
    for n, v in getattr(cfg, key).items():
        if not v['IBOXENABLED']:
            continue

        resname = f'{key}{n}'

        # resources
        if key == 'AutoScalingScalingPolicy':
            r_Policy = asg.ScalingPolicy(resname)
        else:
            r_Policy = aas.ScalingPolicy(resname)

        auto_get_props(r_Policy)
        add_obj(r_Policy)

        # for tracking create output
        if v['PolicyType'] == 'TargetTrackingScaling':
            # Autoscaling
            if 'TargetTrackingConfiguration' in v:
                TargetTrackingConfigurationName = (
                    'TargetTrackingConfiguration')
            # Application Autoscaling
            elif 'TargetTrackingScalingPolicyConfiguration' in v:
                TargetTrackingConfigurationName = (
                    'TargetTrackingScalingPolicyConfiguration')

            basename = f'{resname}{TargetTrackingConfigurationName}'

            # outputs
            if v['Type'] == 'Cpu' or (
                    v['Type'] == 'Custom' and
                    v[TargetTrackingConfigurationName]
                    ['CustomizedMetricSpecification']
                    ['MetricName'] == 'CPUUtilization'):
                # Use Cpu Metric
                Out_String.append('Cpu${Statistic}:${Cpu}')

                if v['Type'] == 'Custom':
                    statistic = get_endvalue(
                        f'{basename}'
                        'CustomizedMetricSpecificationStatistic')
                else:
                    statistic = ''

                Out_Map.update({
                    'Statistic': statistic,
                    'Cpu': get_endvalue(f'{basename}TargetValue'),
                })

    if Out_String:
        # Outputs
        O_Policy = Output(key)
        O_Policy.Value = Sub(','.join(Out_String), **Out_Map)

        add_obj(O_Policy)


def AS_LaunchTemplate():
    InitConfigSets = ASInitConfigSets()

    CfmInitArgs = {}
    IBoxEnvApp = []
    Tags_List = []
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
                Not(get_condition('', 'equals', 'None', reponame)))})

        InitConfigApps = ASInitConfigApps(name)
        CfmInitArgs[name] = InitConfigApps

        InitConfigAppsBuilAmi = ASInitConfigAppsBuildAmi(name)
        # AUTOSPOT - Let cfn-init always prepare instances on boot
        # CfmInitArgs[name + 'BuildAmi'] = InitConfigAppsBuilAmi
        CfmInitArgs[name] = InitConfigAppsBuilAmi

        IBoxEnvApp.extend([
            f'export EnvApp{n}Version=', Ref(envname), "\n",
            f'export EnvRepo{n}Name=', get_endvalue(reponame), "\n"])

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

        Tags_List.append(asg.Tag(envname, Ref(envname), True))

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

    SecurityGroups = SG_SecurityGroupsEC2()

    # Resources
    R_LaunchTemplate = ec2.LaunchTemplate(
        'LaunchTemplate',
        LaunchTemplateName=Sub('${AWS::StackName}-${EnvRole}'),
        LaunchTemplateData=ASLaunchTemplateData('LaunchTemplateData',
                                                UserDataApp=UserDataApp))
    R_LaunchTemplate.LaunchTemplateData.NetworkInterfaces[0].Groups.extend(
        SecurityGroups)

    R_InstanceProfile = IAMInstanceProfile('InstanceProfile')

    # Import role specific cfn definition
    cfn_envrole = f'cfn_{cfg.func_envrole}'
    if cfn_envrole in globals():  # Ex cfn_client_portal
        CfnRole = globals()[cfn_envrole]()
        CfmInitArgs.update(CfnRole)

    R_LaunchTemplate.Metadata = cfm.Metadata(
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

    add_obj([
        R_LaunchTemplate,
        R_InstanceProfile])

    Tags = asg.Tags()
    Tags.tags = Tags_List
    return Tags


def AS_Autoscaling(key):
    LoadBalancers = []
    for n in cfg.LoadBalancerClassic:
        LoadBalancers.append(Ref(f'LoadBalancerClassic{n}'))

    TargetGroups = []
    for n in cfg.LoadBalancerApplication:
        TargetGroups.append(Ref(f'TargetGroup{n}'))

    # Resources
    AS_ScheduledActionsEC2('ScheduledAction')

    LaunchTemplateTags = AS_LaunchTemplate()

    R_ASG = asg.AutoScalingGroup('AutoScalingGroup')
    auto_get_props(R_ASG, f'{key}Base')

    R_ASG.LoadBalancerNames = LoadBalancers
    R_ASG.TargetGroupARNs = TargetGroups
    R_ASG.Tags += LaunchTemplateTags

    add_obj([
        R_ASG])


def AS_ScalableTargetECS(key):
    for n, v in getattr(cfg, key).items():
        resname = f'{key}{n}'

        # resources
        # trick - use fixed name ScalableTarget to avoid changin too much
        # code for now
        r_ScalableTarget = aas.ScalableTarget('ScalableTarget')
        auto_get_props(r_ScalableTarget, f'{key}Service')

        ScheduledActions = []
        for m, w in cfg.ScheduledAction.items():
            sc_name = f'ScheduledAction{m}'
            r_ScheduledAction = aas.ScheduledAction(sc_name)
            auto_get_props(r_ScheduledAction)
            ScheduledActions.append(If(
                f'{sc_name}Disable',
                Ref('AWS::NoValue'),
                r_ScheduledAction))
        r_ScalableTarget.ScheduledActions = ScheduledActions

        add_obj([
            r_ScalableTarget])


def AS_LifecycleHook(key):
    for n, v in getattr(cfg, key).items():
        resname = f'{key}{n}'

        # resources
        r_Hook = asg.LifecycleHook(resname)
        auto_get_props(r_Hook)

        add_obj([
            r_Hook])
