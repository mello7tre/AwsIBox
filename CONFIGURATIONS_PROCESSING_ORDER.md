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

### Processing Order for Generic Configuration
Every time a new template is generated files are processed in the following order:
- common.yml - BaseInt
- common.yml - BaseExt
- {StackType}.yml - BaseInt
- {StackType}.yml - BaseExt
- {StackType}.yml - BrandExt
- {EnvRole}.yml - BaseInt
- {EnvRole}.yml - BaseExt
- {EnvRole}.yml - BrandExt

A key/property defined in a file can be overriden by the following ones.\
At least one EnvRole file must be present.\
If a file do not exists an empty dictionary is returned.

While reading the yaml file only some specific `keys` are processed:
- global - traversed for common.yml, {StackType}.yml and {EnvRole}.yml
- {StackType} - traversed only for {StackType}.yml
- {EnvRole} - traversed only for {EnvRole}.yml



This process create the main configuration parsed by awsibox to build the template.\ 
The following section describe how is automatically created the CloudFormation Mapping to take in account values specific for Env/Region.

### Processing Order for Env/Region
The generated CloudFormation template can be deployed in all enabled Regions and Envs [Ex. dev, stg, prd].\
This is achieved by using the template's Mapping section.


