## Summary

Templates are built starting from a yaml file named as the EnvRole of the Cloudformation Stack that will be created.\
The EnvRole should be a short name with only alphanumeric characters and dash `[a-Z,-]`, it's name should describe the Main Role of the AWS Resources created by the Stack.

Every EnvRole yaml file must have the root key named as the EnvRole (Ex. ecs-cluster) and a child key `StackType` having as value the StackType of the Role (Ex. ec2).

Current StackTypes are:
- agw - ApiGateway
- alb - Application Load Balancer
- cch - Elastic Cache
- clf - CloudFront
- ec2 - EC2
- ecr - Elastic Container Registry
- ecs - Elastic Container Service
- rds - RDS
- res - Generic AWS Resources
- tsk - Scheduled Task (CloudWatch Events + ECS Tasks)
 
Configurations yaml files are read from multiple locations.
- Base Internal (BaseInt)
- Base External (BaseExt)
- Brand External (BrandExt)

##### Base Internal
Contains the files under path `awsibox/cfg/BASE/` and is normally located in python packages install dir.

##### Base External
Contains the files under path `cfg/BASE/` in the working directory where is executed `ibox_generate_templates.py`.

##### Brand External
Contains the files under path `cfg/{Brand}/` in the working directory where is executed `ibox_generate_templates.py`.

### Types of file
There are four types of file for yaml configurations:
- EnvRole files - named as {EnvRole}.yml
- StackType files - named as {StackType}.yml
- common files - named as common.yml
- included files - named as you like but limited to only alphanumeric characters and dash. 

they have different yaml root key:
- EnvRole - root key is the {EnvRole}
- StackType - root key is the {StackType}
- common - root key is the value `global`
- included - root key is the value `global`

for all apart `common` there can be root keys for Env/Region too.

## Processing Order and Rules for Configuration used to build template resources
Every time a new template is generated yaml files are read and processed in the following order:
- common
  - common.yml - BaseInt
  - common.yml - BaseExt
  - common.yml - BrandExt
- {StackType}
  - {StackType}.yml - BaseInt
  - {StackType}.yml - BaseExt
  - {StackType}.yml - BrandExt
- {EnvRole}
  - {EnvRole}.yml - BaseInt
  - {EnvRole}.yml - BaseExt
  - {EnvRole}.yml - BrandExt

At least one EnvRole file must be present.\
Even if it's processed as last, is the first to be read as it is the starting point of the whole process and its' needed to know the relative {StackType}.

If a file do not exists an empty dictionary is returned.

#### Use of include in yaml files
To be able to use the same block of configurations in multiple yaml files, yaml Loader has been extended to support `!include` as additional constructor.

The syntax is the following:
```
IBoxLoader: !include [
 included_yaml_file_one.yml,
 included_yaml_file_two.yml,
 included_yaml_file_three.yml,
]
```
For every yaml file in the list, we proceed in this order:
- if source file, the one with the !include key, is in Ext dirs (Base, Brand) - we try to read the included file from BaseInt too
- we try to read the included file from the same dir of the source file
- we try to read the included file from BaseExt
- we try to read the included file from BrandExt

every file read is added to the inclusion list.\
So we can, potentially, rewrite the previous syntax as:
```
IBoxLoader: !include [
 included_yaml_file_one.yml,
   included_yaml_file_one.yml - BaseInt,
   included_yaml_file_one.yml - SameDir,
   included_yaml_file_one.yml - BaseExt,
   included_yaml_file_one.yml - BrandExt,
 included_yaml_file_two.yml,
   included_yaml_file_two.yml - BaseInt,
   included_yaml_file_two.yml - SameDir,
   included_yaml_file_two.yml - BaseExt,
   included_yaml_file_two.yml - BrandExt,
 included_yaml_file_three.yml,
   included_yaml_file_three.yml - BaseInt,
   included_yaml_file_three.yml - SameDir,
   included_yaml_file_three.yml - BaseExt,
   included_yaml_file_three.yml - BrandExt,
]
```
At the end of the whole yaml read and inclusion process we will have a dictionary key called IBoxLoader and as value a list where each element will be a dictionary representing the read file.

This list represent the order in which included files are processed, so that the last ones have priority over the previous.

### Rules used for processing the resulted dictionaries
The python dictionaries produced are read and then processed by some rules.\
For keys as child of block Mappings/dictionary the following ones are used:
- if the value of the yaml key is a string, int or list, the key is returned as is
- if the value of the yaml key is a dictionary other rules are considered:
  - if the name of the key is different from current {EnvRole}, {StackType} and any Env and Regions enabled, every dictionary sub-keys are parsed and returned named as: key + subkey.
  - if the name of the key is `global` dictionary is traversed/processed for common, {StackType} and {EnvRole} types
  - if the name of the key is `{EnvRole}` dictionary is traversed/processed only for {EnvRole} types.
  - if the name of the key is `{StackType}` dictionary is traversed/processed only for {StackType} types.
  - in all other cases dictionary is simply ignored and not traversed.

Consider the following yaml sample for ec2.yml (a {StackType} type):
```
ec2:
  AdditionalStorage:
    Size: 0
    Type: gp2
  Parameter:
    - UpdateMode:
        Description: 'How to update Instances'
	AllowedValue: ['None', 'Replace', 'Rolling', 'CodeDeploy', 'Cfn']
	Default: 'None'
AnyOtherKey:
  IgnoredValues: 0
```

after processing we will have the following dictionary:
```
{
  AdditionalStorageSize: 0,
  AdditionalStorageType: gp2,
  Parameter: [
    'UpdateMode': {
      'Description': 'How to update Instances',
      'AllowedValue': ['None', 'Replace', 'Rolling', 'CodeDeploy', 'Cfn'],
      'Default': 'None',
    }
  ]
}
```
- AdditionalStorage subkeys names have been concatenated
- Parameter list have been returned as is 
- AnyOtherKey have been ignored (not even traversed/processed) 

#### Dictionary merging
As a result of the previous processes the same key name can be read from multiple `sources`.\
The rules are:
- if the key value is a dictionary, we try to recursive merge them
- in all other cases the last value overwrite the previous ones

#### Main configuration
All the described process create the main configuration parsed by awsibox using [troposphere](https://github.com/cloudtools/troposphere) to build the template.\
The following section describe how is automatically created the CloudFormation Mapping to take in account values specific for Env/Region.

## Processing Order and Rules for Env/Region Configuration used to build template Mapping
The generated CloudFormation template can be deployed in all enabled Regions and Envs [Ex. dev, stg, prd].\
This is achieved by using the template's Mapping section.

After having created the main configuration, yaml files are re-processed but only the following root sub-keys are considered/processed:
- Env
- Region

For example if we have (look in awsibox/cfg.py):
```
ENV_BASE = ['dev', 'stg', 'prd']
``` 
and
```
DEFAULT_REGIONS = [                                                             
    'eu-west-1',                                                                
    'us-east-1',                                                                
    'eu-central-1',                                                             
]    
```
we will process only block Mappings subkeys: `'dev', 'stg', 'prd', 'eu-west-1', 'us-east-1', 'eu-central-1'`.

The Env/Region part of the yaml configuration is reserved ONLY to create the template Mapping section and usually to override values already defined before in the `main` part.\
It's not `directly used` to build the template resources.

The processing is the following:
If the value of a key differ from the one in the main configuration a sub-entry is created in the following mapping:
```
{
  Env: {
    Region: {}
  }
}
```
the name of the key is created by concatenating all traversed keys.

To better undestand how works we consider the following sample yaml file:

```
global:
  ContainerDefinitions:
    - 1:
        Cpu: 128

dev:
  ContainerDefinitions:
    - 1:
        Cpu: 256

eu-west-1:
  ContainerDefinitions: 192

  dev:
    ContainerDefinitions:
      - 1:
          Cpu: 64
  prd:
    ContainerDefinitions:
      - 1:
          Cpu: 512
```

considering the above `ENV_BASE` and `DEFAULT_REGIONS` the Mapping will be:
```
{
  'dev': {
    'eu-west-1': {
      'ContainerDefinitions1Cpu': '64'
    },
    'us-east-1': {
      'ContainerDefinitions1Cpu': '256'
    },
    'eu-central-1': {
      'ContainerDefinitions1Cpu': '128'
    },
  },
  'stg': {
    'eu-west-1': {
      'ContainerDefinitions1Cpu': '192',
    },
    'us-east-1': {
      'ContainerDefinitions1Cpu': '128',
    },
    'eu-central-1': {
      'ContainerDefinitions1Cpu': '128',
    },
  },
  'prd': {
    'eu-west-1': {
      'ContainerDefinitions1Cpu': '512',
    },
    'us-east-1': {
      'ContainerDefinitions1Cpu': '128',
    },
    'eu-central-1': {
      'ContainerDefinitions1Cpu': '128',
    },
  }
}
```

#### Real Processing Order for Env/Region
The real processing order for the Env/Region section of yaml files is more complex.
Consider the process described in [Configuration used to build template resources](#processing-order-and-rules-for-configuration-used-to-build-template-resources), the whole process is executed in order for:
1. Env
2. Region
3. Region/Env

A property defined in `Region/Env` have always precedence over one defined in `Region` and so on, no matter in which files it resides.\
So the full order would be:
- Env
  - common.yml - BaseInt
  - common.yml - BaseExt
  - {StackType}.yml - BaseInt
  - {StackType}.yml - BaseExt
  - {StackType}.yml - BrandExt
  - {EnvRole}.yml - BaseInt
  - {EnvRole}.yml - BaseExt
  - {EnvRole}.yml - BrandExt
- Region
  - common.yml - BaseInt
  - common.yml - BaseExt
  - {StackType}.yml - BaseInt
  - {StackType}.yml - BaseExt
  - {StackType}.yml - BrandExt
  - {EnvRole}.yml - BaseInt
  - {EnvRole}.yml - BaseExt
  - {EnvRole}.yml - BrandExt
- Region/Env
  - common.yml - BaseInt
  - common.yml - BaseExt
  - {StackType}.yml - BaseInt
  - {StackType}.yml - BaseExt
  - {StackType}.yml - BrandExt
  - {EnvRole}.yml - BaseInt
  - {EnvRole}.yml - BaseExt
  - {EnvRole}.yml - BrandExt

