import os
import importlib
import random
import string
import copy
import json
import logging
from pprint import pprint, pformat
import troposphere.ssm as ssm

from troposphere import (
    And,
    AWSHelperFn,
    AWSObject,
    AWSProperty,
    Base64,
    BaseAWSObject,
    Condition,
    Equals,
    Export,
    FindInMap,
    GetAtt,
    GetAZs,
    If,
    ImportValue,
    Join,
    Not,
    Or,
    Output,
    Parameter,
    Ref,
    Select,
    Split,
    Sub,
    Tags,
    Template,
)

from cfg import (
    mappedvalue,
    RP_cmm,
    MAX_SECURITY_GROUPS,
    SECURITY_GROUPS_DEFAULT,
    PARAMETERS_SKIP_OVERRIDE_CONDITION,
)

import cfg

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
            condition = {
                name + 'Override': Not(Equals(Ref(name), '' if name != 'InstanceType' else 'default'))
            }
            cfg.Conditions.append(condition)
            cfg.Parameters_Override.append(v)
        # End
        cfg.template.add_parameter(v)
    del cfg.Parameters[:]

    for v in cfg.Conditions:
        for name in v:
            cfg.template.add_condition(name, v[name])
    del cfg.Conditions[:]

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


def import_modules(gbl):
    for module in cfg.IMPORT_MODULES:
        mod = importlib.import_module('.%s' % module, package='awsibox')
        gbl.update(mod.__dict__)


def import_modules_old():
    for module in cfg.IMPORT_MODULES:
        mod = importlib.import_module(module)
        globals().update(mod.__dict__)


def get_final_value(
        param,
        ssm=False,
        condition=False,
        nocondition=False,
        nolist=False,
        inlist=False,
        split=False,
        issub=False,
        strout=False,
        mappedvalue=mappedvalue
):
    v = ''
    parameters = []

    # if param in mappedvalue means its value do not changes based on Env/Region so hardcode the value in json, ...
    if param in mappedvalue:
        mapped_value = mappedvalue[param]
        # check if value start with method and use eval to run code ... in list too
        if isinstance(mapped_value, list):
            mapped_value = [eval(r) if r.startswith(cfg.EVAL_FUNCTIONS_IN_CFG) else r for r in mapped_value]
        if isinstance(mapped_value, str):
            mapped_value = eval(mapped_value.replace('\n', '')) if mapped_value.startswith(cfg.EVAL_FUNCTIONS_IN_CFG) else mapped_value
    # ... otherway use mapping
    else:
        mapped_value = FindInMap(Ref('EnvShort'), Ref("AWS::Region"), param)

    if strout is True and isinstance(mapped_value, int):
        mapped_value = str(mapped_value)

    if nolist is True and isinstance(mapped_value, list):
        mapped_value = ','.join(mapped_value)

    if issub is False:
        override_value = If(param + 'Override', Ref(param), mapped_value)
    else:
        override_value = If(param + 'Override', Ref(param), Sub(mapped_value))

    parameters = cfg.Parameters_Override + cfg.Parameters

    if cfg.no_override is False and any(param == p.title for p in parameters):
        v = override_value
    # elif param in mappings['dev']['eu-west-1'] or param in mappedvalue:
    else:
        v = mapped_value
        # using ssm - DISABLED FOR NOW
        # v = mapped_value if ssm is True else GetAtt('SSMParameter' + param, 'Value')

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


def get_exported_value(param, stack=False, prefix=''):
    v = ''
    if stack:
        v = ImportValue(
            Sub(param + '-${' + stack + '}', **{stack: get_final_value(stack)})
        )
    elif not isinstance(param, str):
        v = ImportValue(
            Sub(prefix + '${ImportName}', **{'ImportName': param})
        )
    else:
        v = ImportValue(param)
 
    return v


def get_sub_mapex(substring, subvar, stack=False):
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
                submap[listitem] = get_final_value(listitem)
            else:
                submap[listitem] = get_exported_value(listitem, stackitem)
            substring = substring.replace('${' + myindex + mytype + '}', '${' + listitem + '}')
        found = substring.find('${', posindex)

    v = Sub(substring, **submap)

    return v


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
                    
            #file_lines = [eval(x) if x.startswith(cfg.EVAL_FUNCTIONS_IN_CFG) else ''.join(x) for x in f.readlines()]
    
            return(file_lines)
    except IOError:
        logging.error('Lambda code %s not found' % name)
        exit(1)


def auto_get_props_recurse(obj, key, props, obj_propname, mapname, propname, root=None):
    prop_class = props[obj_propname][0]
    if isinstance(prop_class, type) and prop_class.__bases__[0].__name__ == 'AWSProperty':
        # If object already have that props, keep existing props
        if obj_propname in obj.properties:
            prop_obj = obj.properties[obj_propname]
        else:
            prop_obj = prop_class()
        auto_get_props(prop_obj, key=key[obj_propname], mapname=mapname + obj_propname, recurse=True, root=None if root is None else root[obj_propname])
        
        return prop_obj
    elif isinstance(prop_class, list) and isinstance(prop_class[0], type) and prop_class[0].__bases__[0].__name__ == 'AWSProperty':
        # If object props already is a list, keep existing list objects
        if obj_propname in obj.properties:
            prop_list = obj.properties[obj_propname]
        else:
            prop_list = []
        prop_class = props[obj_propname][0][0]
        for o, v in key[obj_propname].iteritems():
            prop_obj = prop_class()
            auto_get_props(prop_obj, key=v, mapname=mapname + obj_propname + str(o), recurse=True, root=None if root is None else root[obj_propname][o]) 
            prop_list.append(prop_obj)

            return prop_list

    return get_final_value(mapname + propname)


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

    return get_final_value(mapname + propname)


def auto_get_props(obj, key=RP_cmm, del_prefix='', mapname=None, recurse=False, rootkey=None, rootname=None, rootdict=None):
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
                value = get_final_value(mapname + propname, mappedvalue=rootdict)
            else:
                value = get_final_value(mapname + propname)
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
        gen_random_string.rng = random.SystemRandom() # Create a static variable
    secret_string = ''.join([ gen_random_string.rng.choice(char_set) for _ in xrange(length) ])

    return secret_string


# Need to stay as last lines
import_modules(globals())
