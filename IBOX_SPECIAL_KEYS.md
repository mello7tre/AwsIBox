# How to use IBOX Special Keys

## Key List ##
- IBOX\_AUTO\_P
- IBOX\_AUTO\_PO
- IBOX\_BASE
- IBOX\_CODE
- IBOX\_CODE\_IF
- IBOX\_CONDITION
- IBOX\_ENABLED
- IBOX\_IF
- IBOX\_IFVALUE
- IBOX\_INDEXNAME
- IBOX\_LIST
- IBOX\_MAPNAME
- IBOX\_NO\_OUTPUT
- IBOX\_OUTPUT
- IBOX\_PARAMETER
- IBOX\_PCO
- IBOX\_REMAPNAME
- IBOX\_RESNAME
- IBOX\_ROLE\_EX
- IBOX\_SKIP\_FUNC
- IBOX\_SOURCE\_OBJ
- IBOX\_SUB\_OBJ
- IBOX\_TITLE

### Usage ###
#### IBOX\_AUTO\_P
Automatically create a default parameter.
To create a parameter for the key "Key" simply prepende the key with:
`Key.IBOX_AUTO_P: {}`
Will be created a Parameter named as the full mapname of the key.
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
Same as `IBOX_AUTO_P`, but create a default Output too.
Output value is named like the key mapname and have the same value.
As properties key for Parameters and Outputs are not the same, both can be used in the dictionary to use custom values.
Ex extended:
```
Type.IBOX_AUTO_PO:
  AllowedValues: ['', 'binpack', 'random', 'spread']
  Value: 'custom value'
  Export: 'custom export value'
```

#### IBOX\_BASE
Is used to define a base configuration for a resource or sub-resource.
Can only be used as dictionary key of a first level node.
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
Can be used to set the value of a key using python/cloudformation code.
If the key is present `IBOX_CODE` must be defined before the key _normal_ value.
If there is a `IBOX_AUTO_P, IBOX_AUTO_PO, IBOX_PCO` key too, `IBOX_CODE` must be defined as first.
Ex:
```
LaunchTemplate:
  - Data:
      ImageId.IBOX_CODE: If(
        'LaunchTemplateDataImageIdLatest', Ref('LaunchTemplateDataImageIdLatest'), get_endvalue('LaunchTemplateDataImageId'))
      ImageId: latest
```
This way we can use a single key ImageId to choose between a _real_ imageID or the latest one (from Parameter `LaunchTemplateDataImageIdLatest`).

The relative key can also be missing, put it's name must be a valid object property.
Ex:
```
LaunchTemplate:
  - Data:
      ImageId.IBOX_CODE: If(
        'LaunchTemplateDataImageIdLatest', Ref('LaunchTemplateDataImageIdLatest'), get_endvalue('ImageIdAlternateName'))
ImageIdAlternateName: latest
```

