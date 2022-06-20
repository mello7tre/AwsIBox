# How to use IBOX Special Keys

## Key List ##
- [IBOX\_AUTO\_P](#IBOX_AUTO_P)
- [IBOX\_AUTO\_PO](#IBOX_AUTO_PO)
- [IBOX\_BASE](#IBOX_BASE)
- [IBOX\_CODE](#IBOX_CODE)
- [IBOX\_CODE\_IF](#IBOX_CODE_IF)
- [IBOX\_CONDITION](#IBOX_CONDITION)
- [IBOX\_ENABLED](#IBOX_ENABLED)
- [IBOX\_IF](#IBOX_IFVALUE)
- [IBOX\_IFCONDVALUE](#IBOX_IFCONDVALUE)
- [IBOX\_IFVALUE](#IBOX_IFVALUE)
- [IBOX\_INDEXNAME](#IBOX_INDEXNAME)
- [IBOX\_LINKED\_OBJ](#IBOX_LINKED_OBJ)
- [IBOX\_LINKED\_OBJ\_NAME](#IBOX_LINKED_OBJ_NAME)
- [IBOX\_LINKED\_OBJ\_INDEX](#IBOX_LINKED_OBJ_INDEX)
- [IBOX\_LIST](#IBOX_LIST)
- [IBOX\_MAPNAME](#IBOX_MAPNAME)
- [IBOX\_OUTPUT](#IBOX_OUTPUT)
- [IBOX\_PARAMETER](#IBOX_PARAMETER)
- [IBOX\_PCO](#IBOX_PCO)
- [IBOX\_RESNAME](#IBOX_RESNAME)
- [IBOX\_ROLE\_EX](#IBOX_ROLE_EX)
- [IBOX\_SKIP\_FUNC](#IBOX_SKIP_FUNC)
- [IBOX\_SOURCE\_OBJ](#IBOX_SOURCE_OBJ)
- [IBOX\_SUB\_OBJ](#IBOX_SUB_OBJ)
- [IBOX\_TITLE](#IBOX_TITLE)

### Usage ###
#### IBOX\_AUTO\_P
Automatically create a default parameter.\
To create a parameter for the key "Key" simply prepende the key with:
`Key.IBOX_AUTO_P: {}`
Will be created a Parameter named as the full mapname of the key.\
Ex base:
```
Field.IBOX_AUTO_P: {}

```
Ex extended:
```
Type.IBOX_AUTO_P:
  AllowedValues: ['', 'binpack', 'random', 'spread']
```

#### IBOX\_AUTO\_PO
Same as `IBOX_AUTO_P`, but create a default Output too.\
Output value is named like the key mapname and have the same value.\
As properties key for Parameters and Outputs are not the same, both can be used in the dictionary to use custom values.\
Ex extended:
```
Type.IBOX_AUTO_PO:
  AllowedValues: ['', 'binpack', 'random', 'spread']
  Value: 'custom value'
  Export: 'custom export value'
```

#### IBOX\_BASE
Is used to define a base configuration for a resource or sub-resource.\
Can only be used as dictionary key of a first level node.\
Ex:
```
Base: &base
  IBOX_OUTPUT:
    - _:
        Value: Ref(IBOX_RESNAME)
        Export: Export(IBOX_RESNAME)
  DBSubnetGroupDescription: Sub("${EnvShort}-%s" % IBOX_INDEXNAME)
  SubnetIds: Split(",", ImportValue(f"Subnets{IBOX_INDEXNAME}"))

global:
  DBSubnetGroup:
    - IBOX_BASE: *base
    - Private: {}
    - Public: {}
```

Both DBSubnetGroup Private and Public will inherit the `IBOX_BASE` configuration.

#### IBOX\_CODE
Can be used to set the value of a key using python/cloudformation code.\
If the key is present `IBOX_CODE` must be defined before the key _normal_ value.\
If there is a `IBOX_AUTO_P, IBOX_AUTO_PO, IBOX_PCO` key too, `IBOX_CODE` must be defined as first.\
Ex:
```
LaunchTemplate:
  - Data:
      ImageId.IBOX_CODE: If(
        'LaunchTemplateDataImageIdLatest', Ref('LaunchTemplateDataImageIdLatest'), get_endvalue('LaunchTemplateDataImageId'))
      ImageId: latest
```
This way we can use a single key ImageId to choose between a _real_ imageID or the latest one (from Parameter `LaunchTemplateDataImageIdLatest`).

The relative key can also be missing, put it's name must be a valid object property.\
Ex:
```
LaunchTemplate:
  - Data:
      ImageId.IBOX_CODE: If(
        'LaunchTemplateDataImageIdLatest', Ref('LaunchTemplateDataImageIdLatest'), get_endvalue('ImageIdAlternateName'))
ImageIdAlternateName: latest
```

#### IBOX\_CODE\_IF
Can be used to skip the creation of an Output defined inside an `IBOX_OUTPUT` key.\
The skip is executed at python level while processing the Outputs.\
The value of the key is processed using eval and must return True or False.\
Ex:
```
IBOX_OUTPUT:
  - _:
      IBOX_CODE_IF: get_endvalue(f"{IBOX_RESNAME}Export") == True
      Value: Ref(IBOX_RESNAME)
      Export: Export(IBOX_RESNAME)
```

#### IBOX\_CONDITION
Can be used both as property key of a resource or inside a specific key using `IBOX_PCO`.\
Ex as resource key:
```
Condition:
  - EnableExecuteCommand:
      get_condition('', 'equals', True, f'EnableExecuteCommand')

```
Ex using `IBOX_PCO`
```
Field.IBOX_PCO:
  IBOX_CONDITION:
    - _PlacementStrategies0TypeRandom:
        get_condition('', 'equals', 'random', f'{IBOX_RESNAME}PlacementStrategies0Type')
```

####  IBOX\_ENABLED
Is used to skip resource processing by python code.\
Can have values: `True` or `False`.\
Not all resource module support this (`joker` module automatically support it).\

#### IBOX\_IF
Can be used to define a CloudFormation If Condition inside the yaml cfg files.\
Is defined as list where the first element represent the condition name, the second what to do if the condition is true and the last one what do if the condition is false.\
The special key `IBOX_IF_VALUE` can be used to specify where to put (second or third) the code following.\
Ex used inside a list of object:
```
PlacementStrategies:
  - IBOX_IF:
      - LaunchTypeFarGate
      - Ref('AWS::NoValue')
      - IBOX_IFVALUE
  - 0:
      Type: spread
      Field: instanceId
```
the whole PlacementStrategies property will be wrapped inside an If Condition with name LaunchTypeFarGate.\
If LaunchTypeFarGate resolve to true (for FarGate LaunchType), it will not be created, otherway it will be created and will have an element named `0`.\
Ex used inside a sub-resource:
```
PlacementStrategies:
  - 0:
      IBOX_IF:
        - LaunchTypeFarGate
        - Ref('AWS::NoValue')
        - IBOX_IFVALUE
      Type: spread
      Field: instanceId
```
only the element `0` of type PlacementStrategy will be wrapped in and If Condition.

#### IBOX\_IFCONDVALUE
Can be used as value of a resource final property (no sub-resource) to automatically create a Condition named as the full mapname of the key.\
The condition is true if the key value is different from `IBOX_IFCONDVALUE`.\
In that case the key will be _removed_ (will have value ` Ref("AWS::NoValue")`).\
Is used to quickly create a condition for a value that change in template Mapping.

#### IBOX\_IFVALUE
Is used to specify where to replace the following code. Look at the key `IBOX_IF`.

#### IBOX\_INDEXNAME
Can be used as python var or inside other IBOX keys.\
Represent the name of resource.\
Not all modules define it, but `joker` always do.\
Ex:
```
EC2RouteTable:
  - Private:
      IBOX_TITLE: RouteTable.IBOX_INDEXNAME
      Tags: Tags(Name=Sub("${VPCName}-%s" % IBOX_INDEXNAME))
      VpcId: Ref("VPC")
  - Public:
      IBOX_TITLE: RouteTable.IBOX_INDEXNAME
      Tags: Tags(Name=Sub("${VPCName}-%s" % IBOX_INDEXNAME))
      VpcId: Ref("VPC")
```
`IBOX_INDEXNAME` will have as value `Private` inside `EC2RouteTablePrivate` `Public` inside `EC2RouteTablePublic`.\
(A dot can be used to separate a _normal_ string from the `IBOX_INDEXNAME` one, it's simply used to better read it, during processing any `.` will be removed.)

#### IBOX\_LINKED\_OBJ
###### Change an existing single object
Can be used to _enable_ a resource normally disabled by `IBOX_ENABLE` or to inject a custom configuration in another resource.\
The resource to be changed must include a `dep` key in `CFG_TO_FUNC` with dependency on the resource where is used, because it need to be processed later.\
It's value is a dict where `Key` represent the resource mapname to be changed, `Name`, if present, the `IBOX_RESNAME` of the changed resource and `Conf` is a dict used to update the changed resource current configuration.\
Ex:
```
ApiGatewayDomainName:
  - Regional:
      IBOX_ENABLED: True
      IBOX_ENABLED: False
      IBOX_LINKED_OBJ:
        Key: R53RecordSetApiGatewayDomainName.IBOX_INDEXNAME
        Name: RecordSet.IBOX_RESNAME
        Conf:
          IBOX_ENABLED: True
      IBOX_OUTPUT:
        - _:
            Value: Ref(IBOX_RESNAME)
            Export: Export(IBOX_RESNAME)
      DomainName: Sub('api.%s' % cfg.HostedZoneNameRegionEnv)
      EndpointConfiguration:
        Types:
          - 'REGIONAL'
      RegionalCertificateArn: get_endvalue('RegionalCertificateArn')

```
In resource `R53RecordSetApiGatewayDomainNameRegional` will be added the properties keys:
```
IBOX_RESNAME: RecordSetApiGatewayDomainNameRegional
IBOX_ENABLED: True
```
###### Create multiple objects from already existings ones
Can also be used to create multiple resource from a single one.\
As example, you want to create two RecordSet, _External_ and _Internal_, for every resource of type DBInstance.\
You define a configuration for RecordSet resources to use for RDS External and Internal.\
And use `IBOX_LINKED_OBJ` inside the _DBInstance_ configuration.
Ex:
```
IBOX_LINKED_OBJ:
  Key: Route53RecordSet
  Name: RecordSet
  Conf: {}
  Type: RDS
  For: ["External", "Internal"]

```
For any value in `For`, look for a already defined object named liked `Route53RecordSet` + `RDS` + `For` _value_ and use its' configuration  for a new object named `TYPE` + `For` _value_.\
Enable it setting `IBOX_ENABLED` to _True_.\
Update it using `Conf`.\
Change the object `IBOX_RESNAME` key to `IBOX_RESNAME` value, the one of the _DBInstance_.\
And finally create/update an `IBOX_TITLE` key with value `Name` + `For` _value_.

In the above example, if having multiple DBInstance alls of them should have RecordSet with the same name and should overwrite it each other.\
A better example should be using a value for name `Name` like: `Name: IBOX_RESNAME` or `Name: RecordSet.IBOX_INDEXNAME`.

Can be subject to change.

#### IBOX\_LINKED\_OBJ\_NAME
Can be used inside `IBOX_LINKED_OBJ` Conf key to propagate a value parsed in the _main_ object to the _linked_ object.\
Ex:\
In the main obj conf
``` 
IBOX_LINKED_OBJ:
  Key: Route53RecordSetEFS
  Name: RecordSetEFS.IBOX_INDEXNAME
  Conf:
    IBOX_LINKED_OBJ_NAME: IBOX_RESNAME
    IBOX_LINKED_OBJ_INDEX: IBOX_INDEXNAME
```
In the linked obj conf
```
EFS:
  Condition: IBOX_LINKED_OBJ_NAME
  Name: Sub("efs-%s.%s" % (IBOX_LINKED_OBJ_INDEX, cfg.HostedZoneNamePrivate))
  ResourceRecords:
    - Sub("${%s}.efs.${AWS::Region}.amazonaws.com" % IBOX_LINKED_OBJ_NAME)
  Type: "CNAME"
  TTL: '300'

```

#### IBOX\_LINKED\_OBJ\_INDEX
Same as `IBOX_LINKED_OBJ_NAME`.

#### IBOX\_LIST
Can be used only for resource processed by the `joker` module.\
Is used to wrap the resource in a list.\
Ex:
```
KMSKey:
  - ParameterStore:
      KeyPolicy:
        Version: "2012-10-17"
        Id: key-default-1
        Statement:
          - IBOX_LIST:
            Action: "kms:*"
            Effect: "Allow"
            Principal:
              AWS: Sub("arn:aws:iam::${AWS::AccountId}:root")
            Resource: "*"
            Sid: "Enable IAM User Permissions"

```
Statement will be a list with a single element.\
Just one `- IBOX_LIST` is needed, but if you need to have multple element in the list, define the other under different keys (As `- IBOX_LIST1`, `- IBOX_LIST2` etc..).

#### IBOX\_MAPNAME
Can be used as python var or inside other IBOX keys.\
Represent the mapname used to create the resource.\
If used inside the Condition name of `IBOX_IF` is replaced with the full mapname of the key where is found `IBOX_IF`.
All modules support this.\
Ex:
```
AllowedIp:
  - Base:
      IBOX_CONDITION:
        - IBOX_MAPNAME:
            get_condition('', 'equals', 'yes', f'{IBOX_MAPNAME}Enabled')
      Enabled: 'yes'
      CidrIp: '127.0.0.1/32'
```
`AllowedIp` do not represent any CloudFormation resource or sub-resource, but it's keys are used, in the code, to populate another one: `SecurityGroupIngress`.\
So i cannot use `IBOX_RESNAME` to find out the resource name because it should resolve with the name used for `SecurityGroupIngress`.\
In the above case `IBOX_MAPNAME` will have the value: `AllowedIpBase`.

#### IBOX\_OUTPUT
Same as `IBOX_CONDITION`.

#### IBOX\_PARAMETER
Same as `IBOX_CONDITION`.

#### IBOX\_PCO
Represent the key suffix used to specify `IBOX_CONDITION`, `IBOX_PARAMETER`, `IBOX_OUTPUT` for a specific key.\
Look at `IBOX_CONDITION`.

#### IBOX\_RESNAME
Can be used as python var or inside other IBOX keys.\
Represent the name/tile of the resource.\
Inside IBOX keys can be represented simply as `_`. Usefull for `IBOX_CONDITION`,  `IBOX_PARAMETER`, `IBOX_OUTPUT` named as the resource.\
Ex:
```
Base: &base
  DisplayName: Sub("${AWS::StackName}.${EnvRole}-SNS%s" % IBOX_INDEXNAME)
  Export: False
  IBOX_OUTPUT:
    - _:
        IBOX_CODE_IF: get_endvalue(f"{IBOX_RESNAME}Export") == True
        Value: Ref(IBOX_RESNAME)
        Export: Export(IBOX_RESNAME)

global:
  SNSTopic:
    - IBOX_BASE: *base
    - MYTopic

```
`IBOX_RESNAME` will have value `SNSTopicMYTopic`.\

For resources using module `joker`, can also be used as key name to change `IBOX_RESNAME`global variable.\
Ex:
```
R53RecordSet:
  - CCHReadOnlyInternal:
      IBOX_RESNAME: RecordSetInternalRO
```

#### IBOX\_ROLE\_EX
Is used for multi stack type role, it represent the additional stack type to include.
Ex: `IBOX_ROLE_EX: ecs-cluster`.

#### IBOX\_SKIP\_FUNC
When assigned to a main key that trigger the relative module, skip processing it.
Ex: `ScalableTarget: IBOX_SKIP_FUNC`.

#### IBOX\_SOURCE\_OBJ
Is used to preprocess a resource using another key\.
It's value represent the full _mapname_ of the key to use to pre-process it\.
Ex:
```
ElastiCacheCacheCluster:
  - IBOX_BASE:
      <<: [*base, *cluster]
      IBOX_TITLE: ElastiCacheCacheCluster
  - Base: {}

ElastiCacheReplicationGroup:
  - IBOX_BASE:
      <<: [*base, *replication-group]
      IBOX_SOURCE_OBJ: 'ElastiCacheCacheCluster{IBOX_INDEXNAME}'
      IBOX_TITLE: ElastiCacheReplicationGroup
  - Base: {}
```
`ElastiCacheReplicationGroupBase` object will be pre-processed using the relative key `ElastiCacheCacheClusterBase`.\
All properties defined for `ElastiCacheCacheCluster` that are used for `ElastiCacheReplicationGroup` too, will be assigned.\

#### IBOX\_SUB\_OBJ
Is used to process another key and include the result as value of the current one.\
Ex:
```
ScalableTarget:
  - Service:
      <<: *ecs
      IBOX_TITLE: ScalableTarget
      ScheduledActions: {"IBOX_SUB_OBJ": "ScalableTargetScheduledAction"}
ScalableTargetScheduledAction:
  - Down: *scheduledaction
  - Up: *scheduledaction
```
`ScalableTarget` `ScheduledActions` property will be a list of `ScalableTargetScheduledAction` created processing the key `ScalableTargetScheduledAction`.

#### IBOX\_TITLE
Is used to replace the resource title after having processed it.\
Usefull if the resource title differ from the mapname of the resource. 
