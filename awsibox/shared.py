import troposphere.ssm as ssm
import troposphere.policies as pol

from .common import *


# S - PARAMETERS #
class Parameter(Parameter):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.Type = 'String'
        self.Default = ''


class SSMParameter(ssm.Parameter):
    Type = 'String'
# E - PARAMETERS #


def stack_add_res():
    for n, v in cfg.Parameters.items():
        # Automatically create override conditions for parameters
        if not n.startswith(PARAMETERS_SKIP_OVERRIDE_CONDITION):

            if n == 'LaunchTemplateDataInstanceType':
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
        add_objoutput(v)
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


def add_objoutput(res):
    try:
        iboxprops = res.IBOX
    except Exception:
        pass
    else:
        join_list = []
        for n in res.Value.split():
            n = n.strip()
            if n.startswith('${'):
                n = n.strip('${}')
                n = eval(f'iboxprops.{n}')
            join_list.append(n)

        res.Value = Join('', join_list)
        del res.properties['IBOX']


def do_no_override(action):
    if action is True:
        cfg.no_override = True
    else:
        cfg.no_override = False


def get_endvalue(param, ssm=False, condition=False, nocondition=False,
                 nolist=False, inlist=False, split=False, issub=False,
                 strout=False, fixedvalues=None, mapinlist=False,
                 resname=None):
    if not fixedvalues:
        # set default if not defined
        fixedvalues = cfg.fixedvalues

    def _get_overridevalue(param, value, condname=None):
        if param not in cfg.Parameters and condname in cfg.Parameters:
            param = condname
        if (cfg.no_override is False and param in cfg.Parameters and not
                param.startswith(PARAMETERS_SKIP_OVERRIDE_CONDITION)):
            override_value = If(f'{param}Override', Ref(param), value)
        else:
            override_value = value

        return override_value

    def _get_value():
        # Its not pythonic, but it's only way to avoid circular import problems
        from .securitygroup import (SG_SecurityGroupsTSK, SG_SecurityGroupsECS)

        if resname:
            IBOXRESNAME = resname
        # if param in fixedvalues means its value do not changes
        # based on Env/Region so hardcode the value in json, ...
        if param in fixedvalues:
            value = fixedvalues[param]
            # check if value start with method and use eval to run code
            if isinstance(value, list):
                scope_g = globals()
                scope_l = locals()
                value = [
                    eval(r, scope_g, scope_l) if r.startswith(
                        cfg.EVAL_FUNCTIONS_IN_CFG) else r for r in value
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

    value = _get_value()

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


def get_dictvalue(key):
    if isinstance(key, list):
        value = [get_dictvalue(k) for k in key]
    elif isinstance(key, dict):
        value = {i: get_dictvalue(k) for i, k in key.items()}
    else:
        value = eval(key) if key.startswith(
            cfg.EVAL_FUNCTIONS_IN_CFG) else key

    return value


def get_condition(cond_name, cond, value2, key=None, OrExtend=[],
                  mapinlist=False, nomap=None):
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


def auto_get_props(obj, mapname=None, key=None, rootdict=None):
    # IBOXRESNAME can be used in yaml
    IBOXOBJ = obj
    IBOXRESNAME = obj.title
    IBOXMAPNAME = mapname

    def _iboxif(if_wrapper, mapname, value):
        condname = if_wrapper[0].replace('IBOXMAPNAME_', mapname)
        condname = condname.replace('IBOXRESNAME', IBOXRESNAME)
        condvalues = []
        for i in if_wrapper[1:3]:
            if isinstance(i, str) and i.startswith(cfg.EVAL_FUNCTIONS_IN_CFG):
                v = eval(i)
            else:
                v = i
            condvalues.append(v)

        if condvalues[0] == 'IBOXIFVALUE':
            value = If(condname, value, condvalues[1])
        else:
            value = If(condname, condvalues[0], value)

        return value

    def _get_obj(obj, key, obj_propname, mapname):
        props = obj.props
        mapname_obj = f'{mapname}{obj_propname}'

        def _get_obj_tags():
            prop_list = []
            for k, v in key[obj_propname].items():
                try:
                    v['Value']
                except Exception:
                    pass
                else:
                    v['Value'] = get_endvalue(f'{mapname_obj}{k}Value')

                try:
                    if_wrapper = v['IBOXIF']
                except Exception:
                    pass
                else:
                    del v['IBOXIF']
                    v = _iboxif(if_wrapper, mapname, v)

                prop_list.append(v)

            obj_tags = Tags()
            obj_tags.tags = prop_list

            return obj_tags

        # trick (bad) to detect attributes as CreationPolicy and UpdatePolicy
        if obj_propname in ['CreationPolicy', 'UpdatePolicy']:
            prop_class = getattr(pol, obj_propname)
        else:
            prop_class = props[obj_propname][0]

        if isinstance(prop_class, type):
            # If object already have that props, object class is
            # the existing already defined object,
            # so extend its property with auto_get_props
            if obj_propname in obj.properties:
                prop_obj = obj.properties[obj_propname]
            else:
                prop_obj = prop_class()

            if prop_class.__bases__[0].__name__ in ['AWSProperty',
                                                    'AWSAttribute']:
                _populate(prop_obj, key=key[obj_propname], mapname=mapname_obj)
            elif prop_class.__name__ == 'dict':
                prop_obj = get_dictvalue(key[obj_propname])
            elif prop_class.__name__ == 'Tags':
                prop_obj = _get_obj_tags()

            return prop_obj

        elif isinstance(prop_class, tuple) and any(n in prop_class for n in [
                Tags, asgTags]):
            prop_obj = _get_obj_tags()

            return prop_obj

        elif (isinstance(prop_class, list) and
                isinstance(prop_class[0], type) and
                prop_class[0].__bases__[0].__name__ == 'AWSProperty'):
            prop_list = []
            prop_class = props[obj_propname][0][0]
            for o, v in key[obj_propname].items():
                if o == 'IBOXIF':
                    # element named IBOXIF must no be parsed
                    # is needed for wrapping whole returned obj in _populate
                    continue
                name_o = str(o)
                mapname_o = f'{mapname_obj}{name_o}'
                prop_obj = prop_class()

                _populate(prop_obj, key=v, mapname=mapname_o)

                # trick to wrapper single obj in If Condition
                try:
                    if_wrapper = v['IBOXIF']
                except Exception:
                    prop_list.append(prop_obj)
                else:
                    prop_list.append(_iboxif(if_wrapper, mapname, prop_obj))

            return prop_list

    def _populate(obj, key=None, mapname=None, rootdict=None):
        if not mapname:
            mapname = obj.title
        if rootdict:
            key = rootdict
            mapname = ''
        if not key:
            key = getattr(cfg, mapname)

        def _try_PCO_in_obj(key):
            def _parameter(k):
                for n, v in k.items():
                    n = n.replace('IBOXRESNAME', IBOXRESNAME)
                    parameter = Parameter(n)
                    _populate(parameter, rootdict=v)
                    add_obj(parameter)

            def _condition(k):
                # this is needed or eval do not find IBOXRESNAME??
                IBOXRESNAME
                IBOXMAPNAME
                for n, v in k.items():
                    n = n.replace('IBOXRESNAME', IBOXRESNAME)
                    if IBOXMAPNAME:
                        n = n.replace('IBOXMAPNAME', IBOXMAPNAME)
                    condition = {n: eval(v)}
                    add_obj(condition)

            def _output(k):
                for n, v in k.items():
                    n = n.replace('IBOXRESNAME', IBOXRESNAME)
                    output = Output(n)
                    _populate(output, rootdict=v)
                    add_obj(output)

            def _objoutput(k):
                for n, v in k.items():
                    n = n.replace('IBOXRESNAME', IBOXRESNAME)
                    output = Output(n)
                    _populate(output, rootdict=v)
                    # alter troposphere obj and add IBOX property
                    output.props['IBOX'] = (object, False)
                    output.propnames.append('IBOX')
                    # assign auto_get_props populated obj to IBOX property
                    output.IBOX = IBOXOBJ
                    add_obj(output)

            func_map = {
                'IBOXPARAMETER': _parameter,
                'IBOXCONDITION': _condition,
                'IBOXOUTPUT': _output,
                'IBOXOBJOUTPUT': _objoutput,
            }
            for pco in list(func_map.keys()):
                try:
                    k = key[pco]
                except Exception:
                    pass
                else:
                    func_map[pco](k)

        # Allowed object properties
        props = vars(obj)['propnames']
        props.extend(vars(obj)['attributes'])

        # Parameters, Conditions, Outpus in yaml cfg
        _try_PCO_in_obj(key)

        for propname in key:
            if propname not in props:
                # NO match between propname and one of obj props
                continue
            key_value = key[propname]

            # set value
            if isinstance(key_value, dict):
                # key value is a dict, get populated object
                value = _get_obj(obj, key, propname, mapname)
            elif (isinstance(key_value, str)
                    and key_value.startswith('IBOXRESNAME')):
                # replace IBOXRESNAME string with IBOXRESNAME value
                value = key_value.replace('IBOXRESNAME', IBOXRESNAME)
            elif rootdict:
                # rootdict is needed for lib/efs.py EFS_FileStorage SGIExtra,
                # is passed as a dictionary to parse for parameters
                value = get_endvalue(
                    f'{mapname}{propname}', fixedvalues=rootdict,
                    resname=IBOXRESNAME)
            elif (isinstance(key_value, str)
                    and key_value.startswith('get_endvalue(')):
                # Usefull to migrate code in yaml using auto_get_props
                # get_endvalue is used only when migrating code
                value = eval(key_value)
            else:
                value = get_endvalue(
                    f'{mapname}{propname}', resname=IBOXRESNAME)

            if key_value == 'IBOXIFCONDVALUE':
                # auto add condition and wrap value in AWS If Condition
                add_obj(get_condition(f'{mapname}{propname}',
                                      'not_equals', 'IBOXIFCONDVALUE'))
                value = If(
                    f'{mapname}{propname}',
                    value,
                    Ref('AWS::NoValue'))
            elif (isinstance(key_value, str)
                    and key_value.startswith('IBOXIF')):
                # trick to wrapper value in If Condition
                if_list = key_value.split()[1:4]
                value = _iboxif(if_list, mapname, value)

            # trick to wrapper recursed returned value in If Condition
            try:
                if_wrapper = key_value['IBOXIF']
            except Exception:
                pass
            else:
                value = _iboxif(if_wrapper, mapname, value)

            if propname == 'Condition' and not isinstance(value, str):
                # Avoid intercepting Template Condition as Resource Condition
                continue

            # Finally set obj property
            try:
                setattr(obj, propname, value)
            except TypeError:
                pass

        # title override
        try:
            obj.title = key['IBOXTITLE']
        except Exception:
            pass

    _populate(obj, key, mapname, rootdict)
    return obj


def auto_build_obj(obj, key, name=None):
    props = vars(obj)['propnames']
    classname = obj.__class__
    for resname, resvalue in key.items():
        final_obj = classname(resname)
        if not name:
            name = final_obj.__class__.__name__
        auto_get_props(final_obj, f'{name}{resname}')

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


def clf_compute_order(pattern):
    base_ord = 1

    for s, w in cfg.CLF_PATH_PATTERN_REPLACEMENT.items():
        pattern = pattern.replace(w, s)

    n_star = 0
    for n, v in enumerate(pattern):
        if v == '?':
            base_ord += 0.0001
        elif v == '*':
            if len(pattern) == n + 1 and n_star != 0:
                # v is last char but not the only star char
                base_ord += 0.0005
            elif n_star != 0:
                base_ord -= 0.000001*n
            else:
                base_ord += 1000/n
                n_star += 1
        elif n_star != 0:
            base_ord -= 0.001

    cfg.dbg_clf_compute_order[pattern] = base_ord

    return base_ord
