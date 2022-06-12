# How to use IBOX Special Keys

## Key List ##
- `IBOX_AUTO_P`
- IBOX\_AUTO\_PO
- IBOX\_BASE
- IBOX\_CLUSTER\_AUTO\_REDUCE
- IBOX\_CODE
- IBOX\_CODE\_IF
- IBOX\_CONDITION
- IBOX\_ENABLED
- IBOX\_IF
- IBOX\_IFVALUE
- IBOX\_INDEXNAME
- IBOX\_LAUNCH\_TEMPLATE\_NO\_SG\_EXTRA
- IBOX\_LAUNCH\_TEMPLATE\_NO\_WAIT\_ELB\_HEALTH
- IBOX\_LIST
- IBOX\_MAPNAME
- IBOX\_NO\_OUTPUT
- IBOX\_OUTPUT
- IBOX\_PARAMETER
- IBOX\_PCO
- IBOX\_REMAPNAME
- IBOX\_RESNAME
- IBOX\_RESNAMEL
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
Same as `IBOX_AUTO_P`
