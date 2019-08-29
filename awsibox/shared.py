import troposphere.ssm as ssm

from .common import *


# S - PARAMETERS #
class Parameter(Parameter):
    Type = 'String'
    Default = ''


class SSMParameter(ssm.Parameter):
    Type = 'String'
# E - PARAMETERS #


def stack_add_res():
    for v in cfg.Parameters:
        name = v.title
        # Automatically create override conditions for parameters
        if not name.startswith(PARAMETERS_SKIP_OVERRIDE_CONDITION):

            if name == 'InstanceType':
                default = 'default'
            elif name == 'SecurityGroups':
                default = cfg.SECURITY_GROUPS_DEFAULT
            else:
                default = ''

            condition = {
                name + 'Override': Not(Equals(Ref(name), default))
            }

            cfg.Conditions.append(condition)
        # End
        cfg.template.add_parameter(v)

    del cfg.Parameters[:]

    for v in cfg.Conditions:
        for name in v:
            cfg.template.add_condition(name, v[name])
    del cfg.Conditions[:]

    for v in cfg.Mappings:
        for name in v:
            cfg.template.add_mapping(name, v[name])
    del cfg.Mappings[:]

    for v in cfg.Resources:
        cfg.template.add_resource(v)
    del cfg.Resources[:]

    for v in cfg.Outputs:
        cfg.template.add_output(v)
    del cfg.Outputs[:]


def do_no_override(action):
    if action is True:
        cfg.no_override = True
    else:
        cfg.no_override = False


# def import_modules(gbl):
#     for module in cfg.IMPORT_MODULES:
#         mod = importlib.import_module('.%s' % module, package='awsibox')
#         gbl.update(mod.__dict__)


def get_endvalue(
        param,
        ssm=False,
        condition=False,
        nocondition=False,
        nolist=False,
        inlist=False,
        split=False,
        issub=False,
        strout=False,
        fixedvalues=None
):
    # Its not pythonic, but it's only way to avoid circular import problems
    from securitygroup import SG_SecurityGroupsTSK

    v = ''
    param_override = param + 'Override'

    # set default if not defined
    if not fixedvalues:
        fixedvalues = cfg.fixedvalues

    # if param in fixedvalues means its value do not changes based on Env/Region so hardcode the value in json, ...
    if param in fixedvalues:
        endvalue = fixedvalues[param]
        # check if value start with method and use eval to run code ... in list too
        if isinstance(endvalue, list):
            endvalue = [eval(r) if r.startswith(cfg.EVAL_FUNCTIONS_IN_CFG) else r for r in endvalue]
        if isinstance(endvalue, str):
            endvalue = eval(endvalue.replace('\n', '')) if endvalue.startswith(cfg.EVAL_FUNCTIONS_IN_CFG) else endvalue
    # ... otherway use mapping
    else:
        endvalue = FindInMap(Ref('EnvShort'), Ref("AWS::Region"), param)

    if strout is True and isinstance(endvalue, int):
        endvalue = str(endvalue)

    if nolist is True and isinstance(endvalue, list):
        endvalue = ','.join(endvalue)

    if issub is False:
        override_value = If(param_override, Ref(param), endvalue)
    else:
        override_value = If(param_override, Ref(param), Sub(endvalue))

    if (cfg.no_override is False and
            any(param == p.title for p in cfg.Parameters) and not
            param.startswith(PARAMETERS_SKIP_OVERRIDE_CONDITION)):
        v = override_value
    # elif param in mappings['dev']['eu-west-1'] or param in fixedvalues:
    else:
        v = endvalue
        # using ssm - DISABLED FOR NOW
        # v = endvalue if ssm is True else GetAtt('SSMParameter' + param, 'Value')

    if condition:
        if condition is True:
            condname = param
        else:
            condname = condition

        v = If(
            condname,
            v,
            Ref('AWS::NoValue'),
        )
    elif nocondition:
        if nocondition is True:
            condname = param
        else:
            condname = nocondition

        v = If(
            condname,
            Ref('AWS::NoValue'),
            v,
        )

    if split:
        v = Select(split, Split(',', v))

    if inlist:
        v = Select(inlist, v)

    return v


def get_expvalue(param, stack=False, prefix=''):
    v = ''
    if stack:
        v = ImportValue(
            Sub('%s-${%s}' % (param, stack), **{stack: get_endvalue(stack)})
        )
    elif not isinstance(param, str):
        v = ImportValue(
            Sub(prefix + '${ImportName}', **{'ImportName': param})
        )
    else:
        v = ImportValue(param)

    return v


def get_subvalue(substring, subvar, stack=False):
    submap = {}
    found = substring.find('${')

    while found != -1:
        posindex = found + 2
        myindex = substring[posindex]
        mytype = substring[posindex + 1]
        # M = Mapped, E = Exported
        if myindex.isdigit() and mytype in ['M', 'E']:
            listitem = subvar[int(myindex) - 1] if isinstance(subvar, list) else subvar
            stackitem = stack[int(myindex) - 1] if isinstance(stack, list) else stack
            if mytype == 'M':
                submap[listitem] = get_endvalue(listitem)
            else:
                submap[listitem] = get_expvalue(listitem, stackitem)
            substring = substring.replace('${' + myindex + mytype + '}', '${' + listitem + '}')
        found = substring.find('${', posindex)

    v = Sub(substring, **submap)

    return v


def get_condition(name, cond, value, key_name=None):
    key_name = key_name if key_name else name
    key_override = key_name + 'Override'

    if cond == 'equals':
        cond_param = Equals(Ref(key_name), value)
        cond_map = Equals(get_endvalue(key_name), value)
    elif cond == 'not_equals':
        cond_param = Not(Equals(Ref(key_name), value))
        cond_map = Not(Equals(get_endvalue(key_name), value))

    if (any(key_name == p.title for p in cfg.Parameters) and not
            key_name.startswith(PARAMETERS_SKIP_OVERRIDE_CONDITION)):
        condition = {name: Or(
            And(
                Condition(key_override),
                cond_param,
            ),
            And(
                Not(Condition(key_override)),
                cond_map,
            )
        )}
    else:
        condition = {name: cond_map}

    return condition


def import_lambda(name):
    parent_dir_name = os.path.dirname(os.path.realpath(__file__))
    lambda_file = os.path.join(os.getcwd(), 'lib/lambdas/%s.code' % name)
    if not os.path.exists(lambda_file):
        lambda_file = os.path.join(parent_dir_name, 'lambdas/%s.code' % name)
    try:
        with open(lambda_file, 'r') as f:
            file_lines = []
            for x in f.readlines():
                if x.startswith(cfg.EVAL_FUNCTIONS_IN_CFG):
                    value = eval(x)
                elif x.startswith('STRING_EVAL_FUNCTIONS_IN_CFG'):
                    value = '"'
                else:
                    value = ''.join(x)

                file_lines.append(value)

            return(file_lines)

    except IOError:
        logging.error('Lambda code %s not found' % name)
        exit(1)


def auto_get_props_recurse(obj, key, props, obj_propname, mapname, propname, rootkey=None, rootname=None):
    prop_class = props[obj_propname][0]
    if isinstance(prop_class, type) and prop_class.__bases__[0].__name__ == 'AWSProperty':
        # If object already have that props, object class is the existing already defined object, so extend its property with auto_get_props
        if obj_propname in obj.properties:
            prop_obj = obj.properties[obj_propname]
        else:
            prop_obj = prop_class()
        auto_get_props(
            prop_obj,
            key=key[obj_propname],
            mapname=mapname + obj_propname,
            recurse=True,
            rootkey=rootkey[obj_propname] if rootkey else None,
            rootname=rootname + obj_propname if rootname else None,
        )

        return prop_obj

    elif isinstance(prop_class, list) and isinstance(prop_class[0], type) and prop_class[0].__bases__[0].__name__ == 'AWSProperty':
        # If object props already is a list, keep existing list objects
        # need to make a change, if object already exist, i must first iterate over old list with rootkey and rootname and then over new one
        prop_list = []
        prop_class = props[obj_propname][0][0]
        # If rootkey is defined, first iterate over rootkey and execute auto_get_props passing rootkey and rootname, but check if element exist in key too,
        # in that case execute execute auto_get_props passing key and mapname...
        if rootkey:
            for o, v in rootkey[obj_propname].iteritems():
                name_o = str(o)
                rootname_o = rootname + obj_propname + name_o
                mapname_o = mapname + obj_propname + name_o
                prop_obj = prop_class()
                auto_get_props(
                    prop_obj,
                    key=v,
                    mapname=rootname_o,
                    recurse=True,
                    rootkey=v,
                    rootname=rootname_o,
                )
                if o in key[obj_propname]:
                    key_o = key[obj_propname][o]
                    auto_get_props(
                        prop_obj,
                        key=key_o,
                        mapname=mapname_o,
                        recurse=True,
                        rootkey=key_o,
                        rootname=rootname_o,
                    )
                prop_list.append(prop_obj)
        # ...then iterate over key, but check if element exist in rootkey too, in that case skip it (already included in previous rootkey iteration)
        # when calling auto_get_props rootkey and rootname can be setted to None, cause if element has not been skipped mean that it do not exist in rootkey
        # so there is no need to pass it (there cannot be a corrispective node in rootkey)
        for o, v in key[obj_propname].iteritems():
            name_o = str(o)
            mapname_o = mapname + obj_propname + name_o
            prop_obj = prop_class()
            if rootkey and o in rootkey[obj_propname]:
                continue
            auto_get_props(
                prop_obj,
                key=v,
                mapname=mapname_o,
                recurse=True,
                rootkey=None,
                rootname=None,
            )
            prop_list.append(prop_obj)

        return prop_list

    return get_endvalue(mapname + propname)


def auto_get_props(obj, key=None, del_prefix='', mapname=None, recurse=False, rootkey=None, rootname=None, rootdict=None):
    # set default if not defined
    if not key:
        key = cfg.RP_cmm

    # Allowed object properties
    props = vars(obj)['propnames']
    props.extend(vars(obj)['attributes'])
    # Object class
    classname = obj.__class__.__name__

    # build up mapname
    mapname = mapname if mapname is not None else obj.title
    if classname in ['Output', 'Parameter']:
        mapname = classname + mapname

    # iterate over props or key choosing the one with less objects
    use_key = True if len(props) > len(key) else None
    for propname in key if use_key else props:
        obj_propname = propname.replace(del_prefix, '') if use_key else del_prefix + propname
        if obj_propname in (props if use_key else key):
            if recurse and isinstance(key[obj_propname], dict):
                value = auto_get_props_recurse(obj, key, obj.props, obj_propname, mapname, propname, rootkey, rootname)
            # needed for lib/efs.py EFS_FileStorage SGIExtra - where is passed as key a new dictionary to parse for parameters
            elif rootdict:
                value = get_endvalue(mapname + propname, fixedvalues=rootdict)
            else:
                value = get_endvalue(mapname + propname)
            try:
                setattr(obj, obj_propname, value)
            except TypeError:
                pass


def auto_build_obj(obj, key, obj_list=cfg.Resources):
    props = vars(obj)['propnames']
    classname = obj.__class__
    for resname, resvalue in key.iteritems():
        final_obj = classname(resname)
        auto_get_props(final_obj, resvalue)

        obj_list.append(final_obj)


def gen_random_string():
    length = 16
    char_set = string.ascii_letters + string.digits
    if not hasattr(gen_random_string, "rng"):
        gen_random_string.rng = random.SystemRandom()  # Create a static variable
    secret_string = ''.join([gen_random_string.rng.choice(char_set) for _ in xrange(length)])

    return secret_string
