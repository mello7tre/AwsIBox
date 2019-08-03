import troposphere.ecs as ecs
import troposphere.ecr as ecr

from shared import *


class ECSService(ecs.Service):
    def setup(self, scheme):
        self.Cluster = get_exported_value('Cluster', 'ClusterStack')
        # DAEMON MODE DO NOT SUPPORT DESIRED OR PLACEMENT STRATEGIES, IS SIMPLY ONE TASK FOR CONTAINER INSTANCE
        if 'SchedulingStrategy' not in RP_cmm or RP_cmm['SchedulingStrategy'] == 'REPLICA':
            self.DesiredCount = get_final_value('CapacityDesired')
            self.DeploymentConfiguration = ecs.DeploymentConfiguration(
                MaximumPercent = get_final_value('DeploymentConfigurationMaximumPercent'),
                MinimumHealthyPercent = get_final_value('DeploymentConfigurationMinimumHealthyPercent'),
            )
            self.PlacementStrategies = If(
                'LaunchTypeFarGate',
                Ref('AWS::NoValue'),
                [
                    #ecs.PlacementStrategy(
                    #    Type='spread',
                    #    Field='attribute:ecs.availability-zone'
                    #),
                    ecs.PlacementStrategy(
                        Type='spread',
                        Field='instanceId'
                    )
                ]
            )
        elif RP_cmm['SchedulingStrategy'] == 'DAEMON':
            self.SchedulingStrategy = 'DAEMON'

        self.LaunchType = get_final_value('LaunchType')
        if 'HealthCheckGracePeriodSeconds' in RP_cmm:
            self.HealthCheckGracePeriodSeconds = get_final_value('HealthCheckGracePeriodSeconds')
        if scheme:
            self.LoadBalancers = [
                ecs.LoadBalancer(
                    ContainerName=Ref('EnvRole'),
                    ContainerPort=get_final_value('ContainerDefinitions1ContainerPort'),
                    TargetGroupArn=Ref('TargetGroup' + scheme)
                )
            ]
        #self.PlatformVersion = 'LATEST'
        if scheme:
            self.Role = If(
                'NetworkModeAwsVpc',
                Ref('AWS::NoValue'),
                get_exported_value('RoleECSService')
            )
        self.TaskDefinition = Ref('TaskDefinition')


class ECSTaskDefinition(ecs.TaskDefinition):
    def setup(self):
        self.ExecutionRoleArn = If(
            'LaunchTypeFarGate',
            get_exported_value('RoleECSTaskExecution'),
            Ref('AWS::NoValue')
        )
        self.TaskRoleArn = Ref('RoleTask')
        if 'Cpu' in RP_cmm:
            self.Cpu = If(
                'CpuTask',
                get_final_value('Cpu'),
                Ref('AWS::NoValue')
            )
        if 'Memory' in RP_cmm:
            self.Memory = If(
                'LaunchTypeFarGate',
                get_final_value('Memory'),
                Ref('AWS::NoValue')
            )
        self.NetworkMode = If(
            'NetworkModeAwsVpc',
            'awsvpc',
            Ref('AWS::NoValue')
        )
        self.RequiresCompatibilities = If(
            'LaunchTypeFarGate',
            ['EC2', 'FARGATE'],
            ['EC2']
        )
        

class ECRRepositories(ecr.Repository):
    def setup(self):
        self.RepositoryName = get_final_value(self.title)
        self.RepositoryPolicyText = {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': [
                        'ecr:GetDownloadUrlForLayer',
                        'ecr:BatchGetImage',
                        'ecr:BatchCheckLayerAvailability',
                        'ecr:PutImage',
                        'ecr:InitiateLayerUpload',
                        'ecr:UploadLayerPart',
                        'ecr:CompleteLayerUpload',
                        'ecr:ListImages',
                        'ecr:DescribeRepositories',
                        'ecr:DescribeImages'
                    ],
                    'Effect': 'Allow',
                    'Principal': {
                        'AWS': [
                            Sub('arn:aws:iam::${AWS::AccountId}:root')
                        ]
                    },
                    'Sid': 'AllowPushPull'
                },
            ]
        }

# ############################################
# ### START STACK META CLASSES AND METHODS ###
# ############################################

class ECSEnvironment(ecs.Environment):
    def setup(self, key):
        name = self.title
        valuename = name + 'Value'
        self.Name = get_final_value(name + 'Name')
        self.Value = get_final_value(valuename)


class ECSMountPoint(ecs.MountPoint):
    def __init__(self, title, key, **kwargs):
        super(ECSMountPoint, self).__init__(title, **kwargs)
        self.ReadOnly = False
        self.SourceVolume = self.title
        self.ContainerPath = key['ContainerPath']


class ECSContainerDefinition(ecs.ContainerDefinition):
    def setup(self, key, index):
        name = self.title  # Ex. ContainerDefinitions1
        auto_get_props(self, key)

        self.Essential = True

        if len(RP_cmm['ContainerDefinitions']) == 1:
            self.Cpu = If(
                'CpuTask',
                get_final_value('Cpu'),
                get_final_value(name + 'Cpu')
            )
            self.Memory = If(
                'LaunchTypeFarGate',
                get_final_value('Memory'),
                get_final_value(name + 'Memory')
            )

        if 'RepoName' in key:
            self.Image=get_sub_mapex(
                '${1M}.dkr.ecr.${AWS::Region}.amazonaws.com/${2M}:${EnvApp' + str(index) + 'Version}',
                ['EcrAccount', name + 'RepoName']
            )
        # use the same EnvApp version for all containers
        elif 'RepoName' in RP_cmm:
            self.Image=get_sub_mapex(
                '${1M}.dkr.ecr.${AWS::Region}.amazonaws.com/${2M}:${EnvApp1Version}',
                ['EcrAccount', 'RepoName']
            )
        elif 'Image' in RP_cmm:
            self.Image=get_final_value('Image')

        self.LogConfiguration=If(
            'LogConfiguration',
            ecs.LogConfiguration(
                LogDriver=get_final_value('LogDriver'),
                Options={
                    #'awslogs-group': get_final_value('AwsLogsGroup'),
                    #'awslogs-create-group': True,
                    'awslogs-group': Ref('LogsLogGroup'),
                    'awslogs-region': Ref('AWS::Region'),
                    'awslogs-stream-prefix': Ref('AWS::StackName')
                }
            ),
            Ref('AWS::NoValue')
        )

        if 'MountPoints' in key:
            self.MountPoints = [
                ECSMountPoint(n, key=k) for n, k in key['MountPoints'].iteritems()
            ]

        if 'Name' in key:
            self.Name = get_sub_mapex('${EnvRole}-${1M}', name + 'Name')
        else:
            self.Name = Ref('EnvRole')

        if 'ContainerPort' in key:
            PortMapping = ecs.PortMapping()
            auto_get_props(PortMapping, key, mapname=self.title)
            if 'HostPort' not in key:
                PortMapping.HostPort = If(
                    'NetworkModeAwsVpc',
                    get_final_value(name + 'ContainerPort'),
                    0
                )
            self.PortMappings = [PortMapping]


class ECSVolume(ecs.Volume):
    def __init__(self, title, key, **kwargs):
        super(ECSVolume, self).__init__(title, **kwargs)
        self.Name = self.title
        self.Host = ecs.Host(
            SourcePath=key['SourcePath']
        )


class ECSAwsvpcConfiguration(ecs.AwsvpcConfiguration):
    def setup(self):
        self.SecurityGroups = [
            GetAtt('SecurityGroupEcsService', 'GroupId'),
        ]
        self.Subnets = Split(',', get_exported_value('SubnetsPrivate'))


class ECRRepositoryLifecyclePolicy(ecr.LifecyclePolicy):
    def __init__(self, title, **kwargs):
        super(ECRRepositoryLifecyclePolicy, self).__init__(title, **kwargs)
        LifecyclePolicyText = {
            'rules': [
                {
                    'rulePriority': 1,
                    'description': 'Images are sorted on pushed_at_time (desc), images greater than specified count are expired.',
                    'selection': {
                        'tagStatus': 'any',
                        'countType': 'imageCountMoreThan',
                        'countNumber': 9500
                    },
                    'action': {
                        'type': 'expire'
                    }
                }
            ]
        }
        self.LifecyclePolicyText = json.dumps(LifecyclePolicyText)
        self.RegistryId = Ref('AWS::AccountId')


def ECRRepositoryPolicyStatementAccountPull(name):
    policy = {   
        'Action': [
            'ecr:GetDownloadUrlForLayer',
            'ecr:BatchGetImage',
            'ecr:BatchCheckLayerAvailability',
            'ecr:ListImages',
            'ecr:DescribeRepositories',
            'ecr:DescribeImages'
        ],
        'Effect': 'Allow',
        'Principal': {
            'AWS': [
                get_sub_mapex('arn:aws:iam::${1M}:root', name)
            ]
        },
        'Sid': 'AllowPull'
    }

    return policy


def ECRRepositoryPolicyStatementAccountPush(name):
    policy = {   
        'Action': [
            'ecr:PutImage',
            'ecr:InitiateLayerUpload',
            'ecr:UploadLayerPart',
            'ecr:CompleteLayerUpload',
        ],
        'Effect': 'Allow',
        'Principal': {
            'AWS': [
                get_sub_mapex('arn:aws:iam::${1M}:root', name)
            ]
        },
        'Sid': 'AllowPush'
    }

    return policy


# ##########################################
# ### END STACK META CLASSES AND METHODS ###
# ##########################################

class ECS_TaskDefinition(object):
    def __init__(self, key):
        Environments_Base = [
            ecs.Environment(
                Name='EnvRegion',
                Value=Ref('AWS::Region')
            ),
            ecs.Environment(
                Name='Env',
                Value=Ref('Env')
            ),
            ecs.Environment(
                Name='EnvAbbr',
                Value=Ref('EnvShort')
            ),
            ecs.Environment(
                Name='EnvBrand',
                Value=get_final_value('BrandDomain')
            ),
            ecs.Environment(
                Name='EnvRole',
                Value=Ref('EnvRole')
            ),
            ecs.Environment(
                Name='EnvStackName',
                Value=Ref('AWS::StackName')
            ),
            ecs.Environment(
                Name='EnvClusterStackName',
                Value=get_final_value('ClusterStack')
            ),
        ]

        # Parameters
        P_DockerLabelLastUpdate = Parameter('DockerLabelLastUpdate')
        P_DockerLabelLastUpdate.Description = 'Use to force redeploy'

        cfg.Parameters.extend([
            P_DockerLabelLastUpdate,
        ])

        Containers = []
        for n, v in RP_cmm['ContainerDefinitions'].iteritems():
            Environments = []
            MountPoints = []

            name = 'ContainerDefinitions' + str(n)  # Ex. ContainerDefinitions1

            # parameters
            # if ContainerDefinitions have RepoName use different EnvApp version
            if n == 1 or 'RepoName' in v:  
                nameenvapp = 'EnvApp' + str(n) + 'Version'  # Ex. EnvApp1Version

                EnvApp = Parameter(nameenvapp)
                EnvApp.Description = nameenvapp
                EnvApp.AllowedPattern = '^[a-zA-Z0-9-_.]*$'
                EnvApp.Default = '1'

                cfg.Parameters.append(EnvApp)

                # outputs
                o_EnvAppOut = Output(nameenvapp)
                o_EnvAppOut.Value = Ref(nameenvapp)

                # and use different output for RepoName
                if 'RepoName' in RP_cmm:
                    if 'RepoName' in v:
                        o_Repo = Output(name + 'RepoName')
                        o_Repo.Value = get_final_value(name + 'RepoName')
                    else:
                        o_Repo = Output('RepoName')
                        o_Repo.Value = get_final_value('RepoName')

                    cfg.Outputs.append(o_Repo)

                cfg.Outputs.extend([
                    o_EnvAppOut,
                ])

            # outputs
            EnvValue_Out_String = []
            EnvValue_Out_Map = {}
            if 'Envs' in v:
                for m, w in v['Envs'].iteritems():
                    envname = name + 'Envs' + str(m)
                    # parameters
                    EnvValue = Parameter(envname + 'Value')
                    EnvValue.Description = w['Name']  + ' - empty for default based on env/role'

                    cfg.Parameters.append(EnvValue)

                    Environment = ECSEnvironment(envname)
                    Environment.setup(key=w)
                    Environments.append(Environment)

                    # outputs
                    EnvValue_Out_String.append(w['Name'] + '=${' + w['Name'] + '}')
                    EnvValue_Out_Map.update({
                        w['Name']: Environment.Value
                    })

            o_EnvValueOut = Output(name + 'Envs')
            o_EnvValueOut.Value = Sub(','.join(EnvValue_Out_String), **EnvValue_Out_Map)

            cfg.Outputs.append(o_EnvValueOut)

            Environments.extend(Environments_Base)

            # parameters
            if 'Cpu' in v:
                p_Cpu = Parameter(name + 'Cpu')
                p_Cpu.Description = 'Cpu Share for containers - empty for default based on env/role'

                cfg.Parameters.append(p_Cpu)

            if 'Memory' in v:
                p_Memory = Parameter(name + 'Memory')
                p_Memory.Description = 'Memory hard limit for containers - empty for default based on env/role'

                cfg.Parameters.append(p_Memory)

            if 'MemoryReservation' in v:
                p_MemoryReservation = Parameter(name + 'MemoryReservation')
                p_MemoryReservation.Description = 'Memory soft limit for containers - empty for default based on env/role'

                cfg.Parameters.append(p_MemoryReservation)

            Container = ECSContainerDefinition(name)
            Container.setup(key=v, index=n)
            Container.Environment = Environments
            # Trick to force reload of Service using parameter
            Container.DockerLabels = If(
                'DockerLabelLastUpdateOverride',
                {'LastUpdate': Ref('DockerLabelLastUpdate')},
                Ref('AWS::NoValue'),
            )
            
            Containers.append(Container)

            # outputs
            Constraints_Out_String = []
            Constraints_Out_Map = {}

            if 'Cpu' in v:
                Constraints_Out_String.append('Cpu:${Cpu}')
                Constraints_Out_Map.update({
                    'Cpu': Container.Cpu
                })

            if 'Memory' in v:
                Constraints_Out_String.append('Memory:${Memory}')
                Constraints_Out_Map.update({
                    'Memory': Container.Memory
                })

            if 'MemoryReservation' in v:
                Constraints_Out_String.append('MemoryReservation:${MemoryReservation}')
                Constraints_Out_Map.update({
                    'MemoryReservation': Container.MemoryReservation
                })

            if Constraints_Out_String:
                o_Constraints = Output(name + 'Constraints')
                o_Constraints.Value = Sub(','.join(Constraints_Out_String), **Constraints_Out_Map)

                cfg.Outputs.append(o_Constraints)

        # Resources
        R_TaskDefinition = ECSTaskDefinition('TaskDefinition')
        R_TaskDefinition.setup()
        R_TaskDefinition.ContainerDefinitions = Containers

        if 'Volumes' in RP_cmm:
            Volumes = []
            for n, v in RP_cmm['Volumes'].iteritems():
                Volume = ECSVolume(n, key=v)
                Volumes.append(Volume)

            R_TaskDefinition.Volumes = Volumes

        cfg.Resources.extend([
            R_TaskDefinition,
        ])


class ECS_Service(object):
    def __init__(self, key):
        # Parameters
        P_MaximumPercent = Parameter('DeploymentConfigurationMaximumPercent')
        P_MaximumPercent.Description = 'DeploymentConfiguration MaximumPercent - empty for default based on env/role'

        P_MinimumHealthyPercent = Parameter('DeploymentConfigurationMinimumHealthyPercent')
        P_MinimumHealthyPercent.Description = 'DeploymentConfiguration MinimumHealthyPercent - empty for default based on env/role'

        cfg.Parameters.extend([
            P_MaximumPercent,
            P_MinimumHealthyPercent,
        ])

        # Resources
        R_SG = SecurityGroupEcsService('SecurityGroupEcsService')
        R_SG.setup()

        R_Service = ECSService('Service')

        if 'LoadBalancerApplication' in RP_cmm:
            if 'External' in RP_cmm['LoadBalancerApplication']:
                R_Service.setup(scheme='External')

                SGRule = SecurityGroupRuleEcsService()
                SGRule.setup(scheme='External')
                R_SG.SecurityGroupIngress.append(SGRule)

            if 'Internal' in RP_cmm['LoadBalancerApplication']:
                R_Service.setup(scheme='Internal')

                SGRule = SecurityGroupRuleEcsService()
                SGRule.setup(scheme='Internal')
                R_SG.SecurityGroupIngress.append(SGRule)
        else:
            R_Service.setup(scheme='')

        SecurityGroups = SG_SecurityGroupsECS().SecurityGroups
        NetworkConfiguration = ecs.NetworkConfiguration()
        NetworkConfiguration.AwsvpcConfiguration = ECSAwsvpcConfiguration()
        NetworkConfiguration.AwsvpcConfiguration.setup()
        NetworkConfiguration.AwsvpcConfiguration.SecurityGroups.extend(SecurityGroups)

        R_Service.NetworkConfiguration = If(
            'NetworkModeAwsVpc',
            NetworkConfiguration,
            Ref('AWS::NoValue')
        )

        cfg.Resources.extend([
            R_Service,
            R_SG,
        ])

        # Output
        try:
            O_MaximumPercent = Output('DeploymentConfigurationMaximumPercent')
            O_MaximumPercent.Value = R_Service.DeploymentConfiguration.MaximumPercent
    
            O_MinimumHealthyPercent = Output('DeploymentConfigurationMinimumHealthyPercent')
            O_MinimumHealthyPercent.Value = R_Service.DeploymentConfiguration.MinimumHealthyPercent
    
            cfg.Outputs.extend([
                O_MaximumPercent,
                O_MinimumHealthyPercent,
            ])
        except AttributeError:
            pass


class ECR_Repositories(object):
    def __init__(self, key):
        PolicyStatementAccounts = []
        for n, v in RP_cmm['EcrAccount'].iteritems():
            mapname = 'EcrAccount' + n  + 'Id'  # Ex. EcrAccountPrdId
            # conditions
            do_no_override(True)
            c_Account = {mapname: Not(
                Equals(get_final_value(mapname), 'None')
            )}

            cfg.Conditions.extend([
                c_Account,
            ])
            do_no_override(False)

            if 'Pull' in v['Policy']:
                PolicyStatementAccount = ECRRepositoryPolicyStatementAccountPull(name=mapname)
                PolicyStatementAccounts.append(
                    If(
                        mapname,
                        PolicyStatementAccount,
                        Ref('AWS::NoValue')
                    )
                )

            if 'Push' in v['Policy']:
                PolicyStatementAccount = ECRRepositoryPolicyStatementAccountPush(name=mapname)
                PolicyStatementAccounts.append(
                    If(
                        mapname,
                        PolicyStatementAccount,
                        Ref('AWS::NoValue')
                    )
                )

        # Resources
        for n, v in RP_cmm[key].iteritems():
            Repo = ECRRepositories(key + n)  # Ex. RepositoryApiLocationHierarchy
            Repo.setup()
            Repo.RepositoryPolicyText['Statement'].extend(PolicyStatementAccounts)
            Repo.LifecyclePolicy = ECRRepositoryLifecyclePolicy('')

            cfg.Resources.append(Repo)


class ECS_Cluster(object):
    def __init__(self, key):
        # Resources
        R_Cluster = ecs.Cluster('Cluster')

        cfg.Resources.extend([
            R_Cluster,
        ])

# Need to stay as last lines
import_modules(globals())
