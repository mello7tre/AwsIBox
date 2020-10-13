import troposphere.ssm as ssm

from .common import *


# S - PARAMETERS #
class Parameter(Parameter):
    def __init__(self, title, **kwargs):
        super(Parameter, self).__init__(title, **kwargs)
        self.Type = 'String'
        self.Default = ''


class SSMParameter(ssm.Parameter):
    Type = 'String'
# E - PARAMETERS #


def stack_add_res():
    for n, v in cfg.Parameters.items():
        # Automatically create override conditions for parameters
        if not n.startswith(PARAMETERS_SKIP_OVERRIDE_CONDITION):

            if n == 'InstanceType':
                default = 'default'
            elif n == 'SecurityGroups':
                default = cfg.SECURITY_GROUPS_DEFAULT
            else:
                default = ''

            condition = {
                f'{n}Override': Not(Equals(Select(0, Ref(n)), default))
            } if v.Type == 'CommaDelimitedList' else {
                f'{n}Override': Not(Equals(Ref(n), default))
            }

            add_obj(condition)
        # End
        cfg.template.add_parameter(v)

    cfg.Parameters.clear()

    for n, v in cfg.Conditions.items():
        cfg.template.add_condition(n, v)
    cfg.Conditions.clear()

    for n, v in cfg.Mappings.items():
        cfg.template.add_mapping(n, v)
    cfg.Mappings.clear()

    for n, v in cfg.Resources.items():
        cfg.template.add_resource(v)
    cfg.Resources.clear()

    for n, v in cfg.Outputs.items():
        cfg.template.add_output(v)
    cfg.Outputs.clear()


def add_obj(obj):
    if isinstance(obj, list):
        for n in obj:
            add_obj(n)
    elif isinstance(obj, Parameter):
        cfg.Parameters[obj.title] = obj
    elif isinstance(obj, dict):
        cfg.Conditions.update(obj)
    elif isinstance(obj, Output):
        cfg.Outputs[obj.title] = obj
    else:
        cfg.Resources[obj.title] = obj


def do_no_override(action):
    if action is True:
        cfg.no_override = True
    else:
        cfg.no_override = False


def _get_value(param, fixedvalues, strout, nolist, issub):
    # Its not pythonic, but it's only way to avoid circular import problems
    from .securitygroup import SG_SecurityGroupsTSK

    # set default if not defined
    if not fixedvalues:
        fixedvalues = cfg.fixedvalues

    # if param in fixedvalues means its value do not changes
    # based on Env/Region so hardcode the value in json, ...
    if param in fixedvalues:
        value = fixedvalues[param]
        # check if value start with method and use eval to run code
        if isinstance(value, list):
            value = [
                eval(r) if r.startswith(cfg.EVAL_FUNCTIONS_IN_CFG)
                else r for r in value
            ]
        if isinstance(value, str):
            value = (
                eval(value.replace('\n', ''))
                if value.startswith(cfg.EVAL_FUNCTIONS_IN_CFG)
                else value)
    # ... otherway use mapping
    else:
        value = FindInMap(Ref('EnvShort'), Ref('AWS::Region'), param)

    if strout is True and isinstance(value, int):
        value = str(value)

    if nolist is True and isinstance(value, list):
        value = ','.join(value)

    if issub:
        value = Sub(value)

    return value


def _get_overridevalue(param, value, condname=None):
    if param not in cfg.Parameters and condname in cfg.Parameters:
        param = condname

    if (cfg.no_override is False and param in cfg.Parameters and not
            param.startswith(PARAMETERS_SKIP_OVERRIDE_CONDITION)):
        override_value = If(f'{param}Override', Ref(param), value)
    else:
        override_value = value

    return override_value


def get_endvalue(param, ssm=False, condition=False, nocondition=False,
                 nolist=False, inlist=False, split=False, issub=False,
                 strout=False, fixedvalues=None, mapinlist=False):

    value = _get_value(param, fixedvalues, strout, nolist, issub)

    if mapinlist is not False:
        value = Select(mapinlist, value)

    if condition or nocondition:
        if condition is True or nocondition is True:
            condname = param
        elif condition:
            condname = condition
        elif nocondition:
            condname = nocondition

        value = _get_overridevalue(param, value, condname)

        value = If(
            condname,
            value if condition else Ref('AWS::NoValue'),
            Ref('AWS::NoValue') if condition else value,
        )
    else:
        value = _get_overridevalue(param, value)

    if split is not False:
        value = Select(split, Split(',', value))

    if inlist is not False:
        value = Select(inlist, value)

    return value


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
            listitem = (
                subvar[int(myindex) - 1] if isinstance(subvar, list)
                else subvar)
            stackitem = (
                stack[int(myindex) - 1] if isinstance(stack, list)
                else stack)
            if mytype == 'M':
                submap[listitem] = get_endvalue(listitem)
            else:
                submap[listitem] = get_expvalue(listitem, stackitem)

            substring = substring.replace(
                '${%s%s}' % (myindex, mytype), '${%s}' % listitem)

        found = substring.find('${', posindex)

    v = Sub(substring, **submap)

    return v


def get_resvalue(resname, propname):
    res = cfg.Resources[resname]

    loc = propname.find('.')
    while loc > 0:
        prop = propname[0:loc]
        res = getattr(res, prop)
        propname = propname[loc + 1:]
        loc = propname.find('.')

    return getattr(res, propname)


def get_condition(cond_name, cond, value2,
                  key=None, OrExtend=[], mapinlist=False, nomap=None):
    # record current state
    override_state = cfg.no_override
    do_no_override(True)

    key_name = key if key else cond_name
    if isinstance(key, FindInMap):
        map_name = key.data['Fn::FindInMap'][0]
        key_name = key.data['Fn::FindInMap'][1]
        value_name = key.data['Fn::FindInMap'][2]
        if not value_name and cond_name:
            value_name = cond_name

        value1_param = FindInMap(map_name, Ref(key_name), value_name)
        value1_map = FindInMap(map_name, get_endvalue(key_name), value_name)
    elif isinstance(key, Select):
        select_index = key.data['Fn::Select'][0]
        select_list = key.data['Fn::Select'][1]

        if 'Fn::Split' in select_list.data:
            split_sep = select_list.data['Fn::Split'][0]
            key_name = select_list.data['Fn::Split'][1]
            select_value_param = Split(split_sep, Ref(key_name))
            select_value_map = Split(split_sep, get_endvalue(key_name))
        else:
            select_value_param = select_list
            select_value_map = get_endvalue(select_list)

        value1_param = Select(
            select_index, select_value_param)
        value1_map = Select(
            select_index, select_value_map)
    else:
        value1_param = Ref(key_name)
        # Used new param "mapinlist" when you have a mapped value in a list
        # but multiple values as override parameters
        if mapinlist:
            value1_map = get_endvalue(mapinlist[0], mapinlist=mapinlist[1])
        else:
            value1_map = get_endvalue(key_name)

    # if beginning state was False set it back
    if not override_state:
        do_no_override(False)

    eq_param = Equals(value1_param, value2)
    eq_map = Equals(value1_map, value2)

    if cond == 'equals':
        cond_param = eq_param
        cond_map = eq_map
    elif cond == 'not_equals':
        cond_param = Not(eq_param)
        cond_map = Not(eq_map)

    if (key_name in cfg.Parameters and
            not key_name.startswith(PARAMETERS_SKIP_OVERRIDE_CONDITION) and
            not nomap):
        key_override = f'{key_name}Override'
        condition = Or(
            And(
                Condition(key_override),
                cond_param,
            ),
            And(
                Not(Condition(key_override)),
                cond_map,
            )
        )
        if OrExtend:
            condition.data['Fn::Or'].extend(OrExtend)
    elif nomap:
        condition = cond_param
    else:
        condition = cond_map

    if cond_name:
        condition = {cond_name: condition}

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
        logging.warning(f'Lambda code {name} not found')
        exit(1)


def auto_get_props_recurse(obj, key, props, obj_propname, mapname,
                           propname, rootkey=None, rootname=None):
    prop_class = props[obj_propname][0]
    if (isinstance(prop_class, type) and
            prop_class.__bases__[0].__name__ == 'AWSProperty'):
        # If object already have that props, object class is
        # the existing already defined object,
        # so extend its property with auto_get_props
        if obj_propname in obj.properties:
            prop_obj = obj.properties[obj_propname]
        else:
            prop_obj = prop_class()
        auto_get_props(
            prop_obj,
            key=key[obj_propname],
            mapname=f'{mapname}{obj_propname}',
            recurse=True,
            rootkey=rootkey[obj_propname] if rootkey else None,
            rootname=f'{rootname}{obj_propname}' if rootname else None,
        )

        return prop_obj

    elif (isinstance(prop_class, list) and
            isinstance(prop_class[0], type) and
            prop_class[0].__bases__[0].__name__ == 'AWSProperty'):
        # If object props already is a list, keep existing list objects
        # need to make a change, if object already exist,
        # i must first iterate over old list with rootkey and
        # rootname and then over new one
        prop_list = []
        prop_class = props[obj_propname][0][0]
        # If rootkey is defined, first iterate over rootkey and
        # execute auto_get_props passing rootkey and rootname,
        # but check if element exist in key too,
        # in that case execute execute auto_get_props passing key and mapname
        if rootkey:
            for o, v in rootkey[obj_propname].items():
                name_o = str(o)
                rootname_o = f'{rootname}{obj_propname}{name_o}'
                mapname_o = f'{mapname}{obj_propname}{name_o}'
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
        # ...then iterate over key, but check if element exist in rootkey too,
        # in that case skip it (already included in previous rootkey iteration)
        # when calling auto_get_props rootkey and rootname can be setted to
        # None, cause if element has not been skipped mean that
        # it do not exist in rootkey so there is no need to pass it
        # (there cannot be a corrispective node in rootkey)
        for o, v in key[obj_propname].items():
            name_o = str(o)
            mapname_o = f'{mapname}{obj_propname}{name_o}'
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

    return get_endvalue(f'{mapname}{propname}')


def auto_get_props(obj, key=None, del_prefix='', mapname=None,
                   recurse=False, rootkey=None, rootname=None, rootdict=None):
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
        mapname = f'{classname}{mapname}'

    # iterate over props or key choosing the one with less objects
    use_key = True if len(props) > len(key) else None
    for propname in key if use_key else props:
        obj_propname = (propname.replace(del_prefix, '') if use_key
                        else f'{del_prefix}{propname}')
        if obj_propname in (props if use_key else key):
            if recurse and isinstance(key[obj_propname], dict):
                value = auto_get_props_recurse(
                    obj, key, obj.props, obj_propname,
                    mapname, propname, rootkey, rootname)
            # needed for lib/efs.py EFS_FileStorage SGIExtra -
            # where is passed as key a new dictionary to parse for parameters
            elif rootdict:
                value = get_endvalue(
                    f'{mapname}{propname}', fixedvalues=rootdict)
            else:
                value = get_endvalue(
                    f'{mapname}{propname}')

            # if key value == 'AWS::NoValue' automatically add condition and
            # wrap value in AWS If Condition
            try:
                key_value = key[obj_propname]
            except Exception:
                pass
            else:
                if key_value == 'AWS::NoValue':
                    add_obj(
                        get_condition(
                            f'{mapname}{propname}', 'not_equals', 'None')
                    )
                    value = If(
                        f'{mapname}{propname}',
                        value,
                        Ref('AWS::NoValue')
                    )

            # Avoid intercepting a Template Condition as a Resource Condition
            if obj_propname == 'Condition' and not isinstance(value, str):
                continue

            try:
                setattr(obj, obj_propname, value)
            except TypeError:
                pass


def auto_build_obj(obj, key):
    props = vars(obj)['propnames']
    classname = obj.__class__
    for resname, resvalue in key.items():
        final_obj = classname(resname)
        auto_get_props(final_obj, resvalue)

        add_obj(final_obj)


def change_obj_data(obj, find, value):
    if isinstance(obj, list):
        for n, v in enumerate(obj):
            change_obj_data(obj[n], find, value)
    elif isinstance(obj, If):
        obj_if = obj.data['Fn::If']
        for n, v in enumerate(obj_if):
            if isinstance(v, Ref) and v.data['Ref'] == find:
                obj_if[n] = value


def gen_random_string():
    length = 16
    char_set = f'{string.ascii_letters}{string.digits}'
    if not hasattr(gen_random_string, "rng"):
        # Create a static variable
        gen_random_string.rng = random.SystemRandom()
    secret_string = ''.join(
        [gen_random_string.rng.choice(char_set) for _ in range(length)])

    return secret_string
