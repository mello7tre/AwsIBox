# How to use Key Special Suffixes
There some special suffixes that can be appended to yaml cfg keys to change how they are precessed.

## Key Suffixes ##
- [\*\*](#DOUBLE_STAR-)
- [++](#DOUBLE_PLUS-)
- [@](#AT_SIGN-)

### Usage ###

#### DOUBLE\_STAR \*\*
Only on key that have as value a dict.
Usually dict keys, in different yaml files, with the same name are, recursive, merged.
If you append \*\* to a key it will not be merged and only it's value will taken in account.

#### DOUBLE\_PLUS ++
Only on key that have as value a list.
Usually list keys, in different yaml files, with the same name are replaced/overwritten.
If you append ++ to a key it's element will be appended to the ones of a key with the same name.
Ex:
```
# in file cfg/ibox/stacks/ec2/i_type.yml
  IAMRole:
    - Instance:
        ManagedPolicyArns:
          - get_expvalue('IAMPolicyBaseInstance')
          - get_expvalue('IAMPolicySSM')

# in file cfg/ibox/stacks/ec2/ecs-cluster.yml
  IAMRole:
    - Instance:
        ManagedPolicyArns++:
          - get_expvalue('IAMPolicyEcs')

```
File `cfg/ibox/stacks/ec2/i_type.yml` define an Instance IAMRole that have for property ManagedPolicyArns a list of policy arn.
Later in file `cfg/ibox/stacks/ec2/ecs-cluster.yml` for stack `ecs-cluster` of type `ec2` i need to add another policy arn to the already defined list.
To do this i append `++` to the list key name: `ManagedPolicyArns`.


#### AT\_SIGN @
Only on key that have as value a string or int, in general key that represent a final value (no list/dict).
Usally if a final key value change in environment or region, it's automatically created a CloudFormation Map and to get it's value is used FindInMap.
In `global` section if you want to avoid that this happen just append `@` at the key name.
Ex:
```
in file cfg/ibox/stacks/ecs/i_type.yml (AwsIBoxExt dir)
dev:
  ECSServiceBaseDeploymentConfiguration:
    MaximumPercent: 100
prd:
  ECSServiceBaseDeploymentConfiguration:
    MaximumPercent: 200

in file cfg/ibox/stacks/ecs/dummy_service_name.yml (AwsIBoxExt dir)
global:
  ECSService:
    - Base:
        DeploymentConfiguration:
          MaximumPercent@: 150
```
Can be usefull to set in dev environment ECS Service DeploymentConfigurationMaximumPercent to 100 for all services.
Later i want, for a specific one, to use another value in all environments, as example 150.
To avoid overwriting the value in both dev and prd section i can simply append `@` to MaximumPercent key and in all env/region the value will be fixed to 150.
