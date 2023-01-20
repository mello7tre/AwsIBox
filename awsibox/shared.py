import python_minifier
from troposphere import policies, ssm

from .common import *
from .RP import RP_to_cfg

IBOX_SPECIAL_KEYS = (
    "IBOX_RESNAME",
    "IBOX_MAPNAME",
    "IBOX_REMAPNAME",
    "IBOX_INDEXNAME",
    "IBOX_PROPNAME",
    "IBOX_CURNAME",
    "IBOX_REFNAME",
    "IBOX_TITLE",
    "IBOX_LINKED_OBJ_NAME",
    "IBOX_LINKED_OBJ_INDEX",
    "IBOX_LINKED_OBJ_FOR",
)


class IBOX_Custom_Obj(AWSProperty):
    props: PropsDictType = {
        "Value": (str, True),
    }


class Parameter(Parameter):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        if "Type" not in kwargs:
            self.Type = "String"
        if "Default" not in kwargs:
            self.Default = ""

        # Create SSM Parameter for EnvAppXVersion Params to have history of application versions
        if title.startswith("EnvApp") and title.endswith("Version"):
            add_obj(
                [
                    get_condition(title, "not_equals", "", nomap=True),
                    ssm.Parameter(
                        f"SSMParameter{title}",
                        Type="String",
                        Condition=title,
                        Name=Sub(
                            "/EnvAppVersions/${EnvRole}/${AWS::StackName}/%s" % title
                        ),
                        Value=Ref(title),
                    ),
                ]
            )


def stack_add_res():
    for n, v in cfg.Parameters.items():
        # Automatically create override conditions for parameters
        if n in list(cfg.fixedvalues) + cfg.mappedvalues:
            if n.endswith("InstanceType"):
                default = "default"
            elif n == "SecurityGroups":
                default = cfg.SECURITY_GROUPS_DEFAULT
            else:
                default = ""

            condition = (
                {f"{n}Override": Not(Equals(Select(0, Ref(n)), default))}
                if v.Type == "CommaDelimitedList"
                else {f"{n}Override": Not(Equals(Ref(n), default))}
            )

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
        title = obj.title
        if hasattr(obj, "resource_type"):
            # if AWSObject add obj to resources
            add_to = "Resources"
        else:
            # otherway add it to OBJS, usefull to include it later
            add_to = "OBJS"
            if hasattr(obj, "Condition"):
                # Condition is not supported on Resource properties, but use it
                # to wrap obj in an If Condition - needed for LambdaFunctionAssociation
                cond_name = parse_ibox_key(obj.Condition)
                del obj.properties["Condition"]
                obj = If(cond_name, obj, Ref("AWS::NoValue"))

        getattr(cfg, add_to)[title] = obj


def add_objoutput(res):
    try:
        iboxprops = res.IBOX_PROPS
    except Exception:
        pass
    else:
        mapname = iboxprops["MAP"][res.title]

        if isinstance(res.Value, str):
            join_list = []
            for n in res.Value.split():
                n = n.strip()
                if n.startswith("${"):
                    n = n.strip("${}")
                    obj = iboxprops[f"{mapname}{n}"][0]
                    propname = iboxprops[f"{mapname}{n}"][1]
                    n = getattr(obj, propname)
                elif n.startswith(cfg.EVAL_FUNCTIONS_IN_CFG):
                    n = eval(n, globals(), {"IBOX_MAPNAME": mapname})
                join_list.append(n)

            res.Value = Join("", join_list)
        else:
            # output use relative resource condition if do not have one
            # i do this only if Value is not a string
            # i need Condition only if using Ref for getting the resource
            try:
                condition = res.Condition
            except Exception:
                try:
                    cond = iboxprops[f"{mapname}Condition"][0].Condition
                except Exception:
                    pass
                else:
                    res.Condition = cond
            else:
                # Use a fake Condition wih value None in cfg to avoid creating a condition
                if condition == "None":
                    del res.properties["Condition"]

        del res.properties["IBOX_PROPS"]


def do_no_override(action):
    if action is True:
        cfg.no_override = True
    else:
        cfg.no_override = False


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
    fixedvalues=None,
    mapinlist=False,
    no_check_for_mappedvalues=False,
):
    if not fixedvalues:
        # set default if not defined
        fixedvalues = cfg.fixedvalues

    def _get_overridevalue(param, value, condname=None):
        if param not in cfg.Parameters and condname in cfg.Parameters:
            param = condname
        if (
            cfg.no_override is False
            and param in cfg.Parameters
            and param in list(cfg.fixedvalues) + cfg.mappedvalues
        ):
            override_value = If(f"{param}Override", Ref(param), value)
        else:
            override_value = value

        return override_value

    def _get_value():
        # if param in fixedvalues means its value do not changes
        # based on Env/Region so hardcode the value.
        if param in fixedvalues:
            value = fixedvalues[param]
            # check if value start with method and use eval to run code
            if isinstance(value, list):
                value = [
                    eval(r) if str(r).startswith(cfg.EVAL_FUNCTIONS_IN_CFG) else r
                    for r in value
                ]
            if isinstance(value, str):
                value = (
                    eval(value.replace("\n", ""))
                    if value.startswith(cfg.EVAL_FUNCTIONS_IN_CFG)
                    else value
                )
        # ... otherway use mapping
        elif no_check_for_mappedvalues or param in cfg.mappedvalues:
            value = FindInMap(Ref("EnvShort"), Ref("AWS::Region"), param)
        # .. or return relative paramter
        elif param in cfg.Parameters:
            return Ref(param)
        else:
            raise ValueError(f"{param} not present in mappedvalues.")

        if strout is True and isinstance(value, int):
            value = str(value)

        if nolist is True and isinstance(value, list):
            value = ",".join(value)

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
            value if condition else Ref("AWS::NoValue"),
            Ref("AWS::NoValue") if condition else value,
        )
    else:
        value = _get_overridevalue(param, value)

    if split is not False:
        value = Select(split, Split(",", value))

    if inlist is not False:
        value = Select(inlist, value)

    return value


def get_expvalue(param, stack=False, prefix=""):
    v = ""
    if stack:
        v = ImportValue(
            Sub("%s-${%s}" % (param, stack), **{stack: get_endvalue(stack)})
        )
    elif not isinstance(param, str):
        v = ImportValue(Sub("%s${ImportName}" % prefix, **{"ImportName": param}))
    else:
        v = ImportValue(param)

    return v


def get_subvalue(substring, subvar, stack=False):
    submap = {}
    found = substring.find("${")

    while found != -1:
        posindex = found + 2
        myindex = substring[posindex]
        mytype = substring[posindex + 1]
        # M = Mapped, E = Exported
        if myindex.isdigit() and mytype in ["M", "E"]:
            listitem = subvar[int(myindex) - 1] if isinstance(subvar, list) else subvar
            stackitem = stack[int(myindex) - 1] if isinstance(stack, list) else stack
            if mytype == "M":
                submap[listitem] = get_endvalue(listitem)
            else:
                submap[listitem] = get_expvalue(listitem, stackitem)

            substring = substring.replace(
                "${%s%s}" % (myindex, mytype), "${%s}" % listitem
            )

        found = substring.find("${", posindex)

    v = Sub(substring, **submap)

    return v


def get_resvalue(resname, propname):
    res = cfg.Resources[resname]

    loc = propname.find(".")
    while loc > 0:
        prop = propname[0:loc]
        res = getattr(res, prop)
        propname = propname[loc + 1 :]
        loc = propname.find(".")

    return getattr(res, propname)


def iboxif(if_wrapper, mapname, value):
    condname = if_wrapper[0].replace("IBOX_MAPNAME", mapname)
    condname = parse_ibox_key(condname)
    condvalues = []
    for i in if_wrapper[1:3]:
        if isinstance(i, str) and i.startswith(cfg.EVAL_FUNCTIONS_IN_CFG):
            v = eval(i)
        else:
            v = i
        condvalues.append(v)

    if condvalues[0] == "IBOX_IFVALUE":
        value = If(condname, value, condvalues[1])
    else:
        value = If(condname, condvalues[0], value)

    return value


def get_dictvalue(key):
    if isinstance(key, list):
        value = [get_dictvalue(k) for k in key]
    elif isinstance(key, dict) and "IBOX_LIST" in key:
        # Usefull for KMS policy and other generic dict properties
        value = []
        for i, k in copy.deepcopy(key).items():
            if i == "IBOX_LIST":
                continue
            # parse IBOX_IF
            if_wrapper = k.pop("IBOX_IF", [])
            prop_obj = {j: get_dictvalue(w) for j, w in k.items()}
            if if_wrapper:
                value.append(iboxif(if_wrapper, "", prop_obj))
            else:
                value.append(prop_obj)
    elif isinstance(key, dict):
        value = {i: get_dictvalue(k) for i, k in key.items()}
    elif isinstance(key, str):
        value = eval(key) if key.startswith(cfg.EVAL_FUNCTIONS_IN_CFG) else key
    else:
        value = key

    return value


def get_condition(
    cond_name, cond, value2, key=None, OrExtend=[], mapinlist=False, nomap=None
):
    # record current state
    override_state = cfg.no_override
    do_no_override(True)

    key_name = key if key else cond_name
    if isinstance(key, FindInMap):
        map_name = key.data["Fn::FindInMap"][0]
        key_name = key.data["Fn::FindInMap"][1]
        value_name = key.data["Fn::FindInMap"][2]
        if not value_name and cond_name:
            value_name = cond_name

        value1_param = FindInMap(map_name, Ref(key_name), value_name)
        value1_map = FindInMap(map_name, get_endvalue(key_name), value_name)
    elif isinstance(key, Select):
        select_index = key.data["Fn::Select"][0]
        select_list = key.data["Fn::Select"][1]

        if "Fn::Split" in select_list.data:
            split_sep = select_list.data["Fn::Split"][0]
            key_name = select_list.data["Fn::Split"][1]
            select_value_param = Split(split_sep, Ref(key_name))
            select_value_map = Split(split_sep, get_endvalue(key_name))
        else:
            select_value_param = select_list
            select_value_map = get_endvalue(select_list)

        value1_param = Select(select_index, select_value_param)
        value1_map = Select(select_index, select_value_map)
    else:
        value1_param = Ref(key_name)
        # Used new param "mapinlist" when you have a mapped value in a list
        # but multiple values as override parameters
        if mapinlist:
            value1_map = get_endvalue(mapinlist[0], mapinlist=mapinlist[1])
        elif nomap:
            # if nomap need to avoid checking that value does exist in mappedvalues
            value1_map = get_endvalue(key_name, no_check_for_mappedvalues=True)
        else:
            value1_map = get_endvalue(key_name)

    # if beginning state was False set it back
    if not override_state:
        do_no_override(False)

    eq_param = Equals(value1_param, value2)
    eq_map = Equals(value1_map, value2)

    if cond == "equals":
        cond_param = eq_param
        cond_map = eq_map
    elif cond == "not_equals":
        cond_param = Not(eq_param)
        cond_map = Not(eq_map)

    if (
        key_name in cfg.Parameters
        and key_name in list(cfg.fixedvalues) + cfg.mappedvalues
        and not nomap
    ):
        key_override = f"{key_name}Override"
        condition = Or(
            And(
                Condition(key_override),
                cond_param,
            ),
            And(
                Not(Condition(key_override)),
                cond_map,
            ),
        )
        if OrExtend:
            condition.data["Fn::Or"].extend(OrExtend)
    elif nomap:
        condition = cond_param
    else:
        condition = cond_map

    if cond_name:
        condition = {cond_name: condition}

    return condition


def import_user_data(name):
    TK_IN_UDATA = "_IBOX_CODE_"
    parent_dir_name = os.path.dirname(os.path.realpath(__file__))

    udata_file_main = os.path.join(parent_dir_name, f"user-data/{name}.sh")
    udata_file_ext = os.path.join(os.getcwd(), f"lib/user-data/{name}.sh")

    if os.path.basename(name).islower() and os.path.exists(udata_file_ext):
        # for envrole external script
        udata_file = udata_file_ext
    else:
        udata_file = udata_file_main

    if not os.path.exists(udata_file):
        return []

    try:
        with open(udata_file, "r") as f:
            code_lines = f.read().splitlines(keepends=True)

            file_lines = []
            # parse code for Token IBOX CODE
            for x in code_lines:
                if x.startswith(cfg.EVAL_FUNCTIONS_IN_CFG):
                    value = eval(x)
                elif x.startswith(TK_IN_UDATA):
                    value = '"'
                elif TK_IN_UDATA in x:
                    # parse Token in string
                    tks = x.split(TK_IN_UDATA)
                    file_lines.extend([f"{tks[0]}", eval(tks[1]), tks[2]])
                    continue
                else:
                    value = "".join(x)

                file_lines.append(value)

            return file_lines

    except IOError:
        raise
    except Exception as e:
        logging.error(f"Error importing user-data {name}: {e}")
        exit(1)


def import_lambda(name):
    TK_IN_LBD = "IBOX_CODE_IN_LAMBDA"
    parent_dir_name = os.path.dirname(os.path.realpath(__file__))
    lambda_file = os.path.join(os.getcwd(), "lib/lambdas/%s.code" % name)
    if not os.path.exists(lambda_file):
        lambda_file = os.path.join(parent_dir_name, "lambdas/%s.code" % name)
    try:
        lambda_file_trunk = os.path.join(*PurePath(lambda_file).parts[-3:])
        with open(lambda_file, "r") as f:
            fdata = f.read()

            try:
                # try to minify using python_minifier
                code = python_minifier.minify(fdata)
                if len(code) > 4096:
                    logging.warning(
                        f"{lambda_file_trunk} > 4096, trying to minify it using a more aggressive option [rename_globals=True]"
                    )
                    code = python_minifier.minify(
                        fdata, rename_globals=True, preserve_globals=["lambda_handler"]
                    )
            except Exception as e:
                # logging.error(f"Failed minifying: {e}")
                code = fdata

            if len(code) > 4096:
                logging.warning(f"Inline lambda {lambda_file_trunk} {len(code)} > 4096")

            code_lines = code.splitlines(keepends=True)

            file_lines = []
            # parse lambda code for Token IBOX CODE
            for x in code_lines:
                if x.startswith(cfg.EVAL_FUNCTIONS_IN_CFG):
                    value = eval(x)
                elif x.startswith(TK_IN_LBD):
                    value = '"'
                elif TK_IN_LBD in x:
                    # parse minified code
                    tks = x.split(TK_IN_LBD)
                    file_lines.extend([f"{tks[0]}", eval(tks[1]), tks[2]])
                    continue
                else:
                    value = "".join(x)

                file_lines.append(value)

            return file_lines

    except IOError:
        logging.warning(f"Lambda code {name} not found")
        exit(1)
    except Exception as e:
        logging.error(e)


def auto_get_props(
    obj,
    mapname="",
    key=None,
    rootdict=None,
    indexname="",
    remapname="",
    linked_obj_name="",
    linked_obj_index="",
    res_obj_type=None,
):
    # IBOX_RESNAME can be used in yaml and resolved inside get_endvalue
    global IBOX_RESNAME, IBOX_MAPNAME, IBOX_INDEXNAME, IBOX_REMAPNAME, IBOX_PROPNAME
    global IBOX_LINKED_OBJ_NAME, IBOX_LINKED_OBJ_INDEX
    IBOX_RESNAME = obj.title
    IBOX_PROPNAME = ""
    if not "IBOX_MAPNAME" in globals() or mapname:
        IBOX_MAPNAME = mapname
    if not "IBOX_REMAPNAME" in globals() or remapname:
        IBOX_REMAPNAME = remapname
    if not "IBOX_INDEXNAME" in globals() or indexname:
        IBOX_INDEXNAME = indexname
    if not "IBOX_LINKED_OBJ_NAME" in globals() or linked_obj_name:
        IBOX_LINKED_OBJ_NAME = linked_obj_name
    if not "IBOX_LINKED_OBJ_INDEX" in globals() or linked_obj_index:
        IBOX_LINKED_OBJ_INDEX = linked_obj_index

    # create a dict where i will put all property with a flat hierarchy
    # with the name equals to the mapname and the relative value.
    # Later i will assign this dict to the relative output object using
    # IBOX_OUTPUT
    IBOX_PROPS = {"MAP": {}}

    res_obj_type = getattr(obj, "resource_type", res_obj_type)

    def _get_obj(obj, key, obj_propname, mapname):
        props = obj.props
        mapname_obj = f"{mapname}{obj_propname}"
        global IBOX_PROPNAME, IBOX_REFNAME

        def _get_obj_tags():
            prop_list = []
            for k, v in key[obj_propname].items():
                try:
                    v["Value"]
                except Exception:
                    pass
                else:
                    v["Value"] = get_endvalue(f"{mapname_obj}{k}Value")

                try:
                    if_wrapper = v["IBOX_IF"]
                except Exception:
                    pass
                else:
                    del v["IBOX_IF"]
                    v = iboxif(if_wrapper, mapname, v)

                prop_list.append(v)

            obj_tags = Tags()
            obj_tags.tags = prop_list

            return obj_tags

        obj_class = obj.__class__.__name__
        obj_mod_name = obj.__module__
        prop_class = props.get(obj_propname, [None])[0]
        # print(f"TYPE: {res_obj_type}, CLASS: {obj_class}, PROP: {obj_propname}")

        # detect attributes as CreationPolicy not included in obj properties
        if obj_propname in ["CreationPolicy", "UpdatePolicy"]:
            prop_class = getattr(policies, obj_propname)
        elif callable(prop_class) and prop_class.__name__ not in [
            "validate_variables_name",
            "policytypes",
        ]:
            # prop_class is a method fallback and try to use CloudFormationResourceSpecification
            if res_obj_type in cfg.TROPO_CLASS_TO_CFM:
                obj_class = cfg.TROPO_CLASS_TO_CFM[res_obj_type].get(
                    obj_class, obj_class
                )
            try:
                res_obj_propname = cfg.cfm_res_spec["PropertyTypes"][
                    f"{res_obj_type}.{obj_class}"
                ]["Properties"][obj_propname]
            except Exception:
                try:
                    res_obj_propname = cfg.cfm_res_spec["ResourceTypes"][res_obj_type][
                        "Properties"
                    ][obj_propname]
                except Exception:
                    res_obj_propname = None

            if res_obj_propname:
                obj_prop_type = res_obj_propname.get("Type")
                prop_class_type = res_obj_propname.get("ItemType")
                if not prop_class_type:
                    prop_class_type = obj_prop_type
                if not prop_class_type:
                    prop_class_type = res_obj_propname.get("PrimitiveType")

                # print(f"PROP_CLASS_TYPE: {prop_class_type}")
                try:
                    prop_class = getattr(sys.modules[obj_mod_name], prop_class_type)
                except Exception:
                    pass
                else:
                    if obj_prop_type == "List":
                        prop_class = [prop_class]

        # print(f"PROP_CLASS: {prop_class}")

        # obj_propname is a class, usually Tropo AWSProperty
        if isinstance(prop_class, type):
            # If object already have that props, object class is
            # the existing already defined object,
            # so extend its property with auto_get_props
            if obj_propname in obj.properties:
                prop_obj = obj.properties[obj_propname]
            else:
                prop_obj = prop_class()

            if prop_class.__bases__[0].__name__ in ["AWSProperty", "AWSAttribute"]:
                _populate(
                    prop_obj,
                    key=key[obj_propname],
                    mapname=mapname_obj,
                )
                # Check for incomplete AWSProperty object and set obj to None to skip it
                try:
                    prop_obj.to_dict()
                except Exception as e:
                    # logging.warning(f"Resource with missing properties: {obj_propname}\n\t\t{e}")
                    prop_obj = None
            elif prop_class.__name__ == "dict":
                prop_obj = get_dictvalue(key[obj_propname])
            elif prop_class.__name__ == "Tags":
                prop_obj = _get_obj_tags()
            elif prop_class.__name__ == "str" and obj_propname == "LifecyclePolicyText":
                # str but can be represented as dict Ex. ECR LifecyclePolicyText
                prop_obj = json.dumps(get_dictvalue(key[obj_propname]))

            return prop_obj

        # obj_propname is are Tropo Tags
        elif (
            isinstance(prop_class, tuple)
            and any(n in prop_class for n in [Tags, asgTags])
        ) or (
            callable(prop_class) and prop_class.__name__ in ["validate_tags_or_list"]
        ):
            prop_obj = _get_obj_tags()

            return prop_obj

        # obj_propname is List of Tropo AWSProperty
        elif (
            isinstance(prop_class, list)
            and isinstance(prop_class[0], type)
            and prop_class[0].__bases__[0].__name__ == "AWSProperty"
        ):
            prop_list = []
            prop_class = prop_class[0]

            # save IBOX_REFNAME
            if "IBOX_REFNAME" in globals():
                globals()[f"IBOX_REFNAME@{mapname}"] = globals()["IBOX_REFNAME"]

            for o, v in key[obj_propname].items():
                # for a list of properties set IBOX_PROPNAME to the name of property
                IBOX_PROPNAME = o

                if o == "IBOX_IF":
                    # element named IBOX_IF must no be parsed
                    # is needed for wrapping whole returned obj in _populate
                    continue
                name_o = str(o)
                mapname_o = f"{mapname_obj}{name_o}"
                prop_obj = prop_class()

                _populate(prop_obj, key=v, mapname=mapname_o)

                # trick to wrapper single obj in If Condition
                try:
                    if_wrapper = v["IBOX_IF"]
                except Exception:
                    prop_list.append(prop_obj)
                else:
                    prop_list.append(iboxif(if_wrapper, mapname, prop_obj))

            # restore IBOX_REFNAME
            if f"IBOX_REFNAME@{mapname}" in globals():
                IBOX_REFNAME = globals()[f"IBOX_REFNAME@{mapname}"]

            if prop_list:
                return prop_list

        # obj_propname is a dict as KSM Key KeyPolicy
        elif (
            isinstance(prop_class, tuple)
            and isinstance(prop_class[0], type)
            and prop_class[0].__name__ == "dict"
        ) or (
            callable(prop_class)
            and prop_class.__name__ in ["policytypes", "validate_variables_name"]
        ):
            return get_dictvalue(key[obj_propname])

    def _populate(obj, key=None, mapname=None, rootdict=None):
        global IBOX_RESNAME, IBOX_CURNAME, IBOX_REFNAME, IBOX_TITLE

        if not mapname:
            mapname = obj.title
        if rootdict:
            key = rootdict
            mapname = ""
        if not key:
            key = getattr(cfg, mapname)

        if key.get("IBOX_TITLE"):
            IBOX_TITLE = parse_ibox_key(key["IBOX_TITLE"])

        def _try_PCO_in_obj(key):
            def _parameter(k):
                for n, v in k.items():
                    n = parse_ibox_key(n)
                    parameter = Parameter(n)
                    _populate(parameter, rootdict=v)
                    add_obj(parameter)

            def _condition(k):
                for n, v in k.items():
                    n = parse_ibox_key(n)
                    condition = {n: eval(v)}
                    add_obj(condition)

            def _output(k):
                for n, v in k.items():
                    n = parse_ibox_key(n)
                    if not eval(v.get("IBOX_ENABLED_IF", "True")):
                        continue
                    output = Output(n)
                    _populate(output, rootdict=v)
                    # alter troposphere obj and add IBOX property
                    output.props["IBOX_PROPS"] = (dict, False)
                    # starting from troposphere 3.0 propnames is a set
                    output.propnames = list(output.propnames) + ["IBOX_PROPS"]
                    # assign auto_get_props populated obj to IBOX property
                    output.IBOX_PROPS = IBOX_PROPS
                    output.IBOX_PROPS["MAP"][n] = mapname
                    add_obj(output)

            func_map = {
                "IBOX_PARAMETER": _parameter,
                "IBOX_CONDITION": _condition,
                "IBOX_OUTPUT": _output,
            }
            for pco in list(func_map.keys()):
                try:
                    k = key[pco]
                except Exception:
                    pass
                else:
                    func_map[pco](k)

        def _auto_PO(name, conf, mode, value=""):
            conf = dict(conf)
            if "p" in mode:
                parameter_base = {"Description": "Empty for mapped value"}
                parameter_base.update(conf)
                # avoid including Output Condition in Parameter
                parameter_base.pop("Condition", "")
                pco_conf = {"IBOX_PARAMETER": {f"{mapname}{name}": parameter_base}}
                # look for CONDITION key and if found update pco_conf
                condition = conf.get("CONDITION")
                if condition:
                    pco_conf.update({"IBOX_CONDITION": {f"{mapname}{name}": condition}})
                _try_PCO_in_obj(pco_conf)
            if "o" in mode:
                # avoid parsing Parameter Descrption as output one
                conf.pop("Description", "")
                if isinstance(value, int):
                    # Output value must be a string
                    value = str(value)
                elif isinstance(value, str) and value.startswith("get_endvalue"):
                    value = eval(value)
                output_base = {"Value": value}
                output_base.update(conf)
                if output_base["Value"] != "IBOX_SKIP":
                    output = {"IBOX_OUTPUT": {f"{mapname}{name}": output_base}}
                    _try_PCO_in_obj(output)

        def _process_ibox_auto_pco_key(propname):
            ibox_auto_p = f"{propname}.IBOX_AUTO_P"
            ibox_auto_po = f"{propname}.IBOX_AUTO_PO"
            ibox_pco = f"{propname}.IBOX_PCO"

            # IBOX_AUTO_PO
            for n in [ibox_auto_po, ibox_auto_p]:
                if n in key:
                    # Automatically create parameter
                    _auto_PO(propname, key[n], "p")

            # IBOX_PCO
            if ibox_pco in key:
                # If there is a key ending with {propname}.IBOX_PCO process it
                _try_PCO_in_obj(key[ibox_pco])

        def _proc_custom_obj(base_rootdict, key_value, mapname, propname):
            values = []
            if not base_rootdict:
                base_rootdict = getattr(cfg, f"{mapname}IBOX_CUSTOM_OBJ{propname}")
            if isinstance(key_value, dict):
                my_iter = iter(key_value.items())
                is_dict = True
            else:
                my_iter = enumerate(key_value)
                is_dict = False

            for n, v in my_iter:
                rootdict = {"Value": v}
                obj_title = n if is_dict else v
                if isinstance(v, dict):
                    rootdict.update(v.get("Conf", {}))
                    v = v.get("Value", v)
                    obj_title = f"{n}Value"
                rootdict.update(base_rootdict)
                obj = IBOX_Custom_Obj(obj_title)
                auto_get_props(obj, rootdict=rootdict, mapname=f"{mapname}{propname}")
                value = getattr(obj, "Value")
                if v == "IBOX_IFCONDVALUE":
                    condname = f"{mapname}{propname}{n}"
                    add_obj(get_condition(condname, "not_equals", "IBOX_IFCONDVALUE"))
                    values.append(If(condname, value, Ref("AWS::NoValue")))
                else:
                    values.append(value)
            return values

        def _linked_obj(linked_obj_data):
            # need to parse them here to have the right values
            lo_name = parse_ibox_key(linked_obj_data.get("Name", IBOX_RESNAME))
            lo_key = parse_ibox_key(linked_obj_data.get("Key", ""))
            lo_type = parse_ibox_key(linked_obj_data.get("Type", ""))
            # this way even if without key "For", for cycle will run at least one time
            lo_for_cycle = linked_obj_data.get("For", [""])

            louc_cfg = {}
            for lo_for_index in lo_for_cycle:
                # need to copy it because it's updated
                lo_conf = copy.deepcopy(
                    linked_obj_data.get("Conf", {"IBOX_LINKED_OBJ_NAME": IBOX_RESNAME})
                )
                lo_conf["IBOX_ENABLED"] = True
                # for all lo_conf entries, if their value is a string parse it using parse_ibox_key
                for loc_entry_key, loc_entry_value in lo_conf.items():
                    lo_conf[loc_entry_key] = parse_ibox_key(loc_entry_value)
                    lo_conf[loc_entry_key] = parse_ibox_key(
                        loc_entry_value, conf={"IBOX_LINKED_OBJ_FOR": lo_for_index}
                    )

                linked_obj_key_name = f"{lo_key}{lo_type}{lo_for_index}"
                target_name = f"{lo_name}{lo_for_index}"

                # get existing object
                if f"{lo_key}{target_name}" == linked_obj_key_name:
                    # source and target are the same, so update the object in place
                    linked_obj = getattr(cfg, linked_obj_key_name)
                else:
                    # copy it, first search for the full name including for index
                    linked_obj = copy.deepcopy(
                        getattr(
                            cfg,
                            linked_obj_key_name,
                            getattr(cfg, f"{lo_key}{lo_type}", None),
                        )
                    )

                # update it with config from IBOX_LINKED_OBJ Conf
                linked_obj.update(lo_conf)

                lo_resname = lo_conf.get("IBOX_RESNAME", f"{lo_key}{lo_name}")
                linked_obj["IBOX_RESNAME"] = f"{lo_resname}{lo_for_index}"

                condition = key.get("Condition", getattr(obj, "Condition", None))
                if condition and not "Condition" in linked_obj:
                    # automatically add Condition if source obj have it and target not
                    linked_obj["Condition"] = parse_ibox_key(condition)

                # assign to louc_cfg lo_key
                louc_cfg[target_name] = linked_obj

            if cfg.debug:
                pprint(louc_cfg)
            # update cfg and fixedvalues, need to do it this way to avoid overwriting the lo_key and removing all objects
            RP_to_cfg(louc_cfg, prefix=lo_key, mappedvalues=cfg.mappedvalues)
            # finally update cfg object base key with configuration including mutiple objects
            getattr(cfg, lo_key).update(louc_cfg)

        # Allowed object properties
        props = list(vars(obj)["propnames"])
        props.extend(vars(obj)["attributes"])

        # needed by IBOX_BASE used on Resource Properties
        if key.get("IBOX_BASE_REF"):
            IBOX_REFNAME = mapname

        # Parameters, Conditions, Outpus in yaml cfg
        _try_PCO_in_obj(key)

        # For linked resources as r53recordset, update their keys conf.
        # This way they can be enabled or their name can be changed, or so on...
        ibox_linked_obj = key.get("IBOX_LINKED_OBJ")
        if ibox_linked_obj:
            # bad hack to use a dict for ibox_linked_obj, so that i can modify it if needed using the index name
            # but avoid intercepting the "normal" conf that is a dict too (a key named Type must not exist)
            if isinstance(ibox_linked_obj, dict) and "Type" not in ibox_linked_obj:
                for linked_obj in ibox_linked_obj.values():
                    if linked_obj:
                        _linked_obj(linked_obj)
            else:
                _linked_obj(ibox_linked_obj)

        # iterate over both obj props and key - using key order
        for propname in dict(
            list(key.items()) + list(dict.fromkeys(props, None).items())
        ).keys():
            if key.get(propname) == "IBOX_SKIP":
                continue

            # IBOX KEY TO LOOK FOR
            ibox_auto_p = f"{propname}.IBOX_AUTO_P"
            ibox_auto_po = f"{propname}.IBOX_AUTO_PO"
            ibox_pco = f"{propname}.IBOX_PCO"
            ibox_code = f"{propname}.IBOX_CODE"
            ibox_code_key = f"{propname}.IBOX_CODE_KEY"
            ibox_custom_obj = f"{propname}.IBOX_CUSTOM_OBJ"

            custom_key_only = propname.replace(".IBOX_AUTO_PO", "")

            if not isinstance(obj, (Output, Parameter, Condition)):
                IBOX_CURNAME = f"{mapname}{propname}"

            # IBOX_PCO and IBOX_AUTO_PO for Custom Key ONLY
            if (
                ibox_pco in key
                and propname in key
                and propname not in props
                and all(n not in key for n in [ibox_auto_p, ibox_auto_po, ibox_code])
            ):
                # process ibox_pco for custom key not present in obj props
                # but only if there is not a relative ibox_auto_p/o or ibox_code key
                _try_PCO_in_obj(key[ibox_pco])
            elif propname.endswith("IBOX_AUTO_PO") and custom_key_only not in props:
                # process IBOX_AUTO_PO custom key if the relative propname do not exist in resource props
                _auto_PO(
                    custom_key_only,
                    key[propname],
                    "po",
                    f"get_endvalue('{mapname}{custom_key_only}')",
                )

            # IBOX_CODE
            if ibox_code in key and propname in props:
                # If there is a key ending with {prop}.IBOX_CODE  eval it and use it as prop value.
                # First process IBOX_AUTO_PO and IBOX_PCO keys
                _process_ibox_auto_pco_key(propname)
                value = eval(key[ibox_code])
            elif (
                propname in key
                and propname in props
                or (propname in key and ibox_custom_obj in key)
            ):
                # there is match between obj prop and a dict key or there is a custom obj
                key_value = key[propname]

                # Process IBOX_AUTO_PO and IBOX_PCO keys
                _process_ibox_auto_pco_key(propname)

                # IBOX_CODE_KEY - like IBOX_CODE but only if propname is in key too
                if ibox_code_key in key:
                    value = eval(key[ibox_code_key])
                # set value
                elif isinstance(key_value, (list, dict)) and ibox_custom_obj in key:
                    # to process a list like a custom obj
                    save_ibox_resname = IBOX_RESNAME
                    value = _proc_custom_obj(
                        key[ibox_custom_obj], key_value, mapname, propname
                    )
                    # need to save and restore IBOX_RESNAME because during processing _proc_custom_obj it change
                    IBOX_RESNAME = save_ibox_resname
                elif isinstance(key_value, dict):
                    # key value is a dict, get populated object
                    value = _get_obj(obj, key, propname, mapname)
                    if value is None:
                        continue
                elif isinstance(key_value, str) and key_value.startswith(
                    IBOX_SPECIAL_KEYS
                ):
                    # parse value for IBOX special keys
                    value = parse_ibox_key(key_value)
                elif rootdict:
                    # rootdict is needed by lib/efs.py EFS_FileStorage SGIExtra
                    # where is passed as a dictionary to parse for parameters
                    value = get_endvalue(f"{mapname}{propname}", fixedvalues=rootdict)
                elif isinstance(key_value, str) and key_value.startswith(
                    "get_endvalue("
                ):
                    # Usefull to migrate code in yaml using auto_get_props
                    # get_endvalue is used only when migrating code
                    value = eval(key_value)
                else:
                    value = get_endvalue(f"{mapname}{propname}")

                if key_value == "IBOX_IFCONDVALUE":
                    # auto add condition and wrap value in AWS If Condition
                    add_obj(
                        get_condition(
                            f"{mapname}{propname}", "not_equals", "IBOX_IFCONDVALUE"
                        )
                    )
                    value = If(f"{mapname}{propname}", value, Ref("AWS::NoValue"))

                # trick to wrapper recursed returned value in If Condition
                try:
                    if_wrapper = key_value["IBOX_IF"]
                except Exception:
                    pass
                else:
                    value = iboxif(if_wrapper, mapname, value)

                if propname == "Condition" and not isinstance(value, str):
                    # Avoid intercepting a Template Condition
                    # as a Resource Condition
                    continue
            else:
                # NO match between propname and cfg keys
                continue

            # Finally set obj property
            try:
                setattr(obj, propname, value)
            except AttributeError:
                setattr(cfg, f"{mapname}{propname}", value)
                pass
            except TypeError:
                pass
            else:
                # populate IBOX_PROPS dict
                IBOX_PROPS[f"{mapname}{propname}"] = (obj, propname)

                # Automatically create output
                if ibox_auto_po in key:
                    ibox_auto_po_value = key[ibox_auto_po]
                    _auto_PO(propname, ibox_auto_po_value, "o", value)

        # need to redefine it here because it's has been changed by nested supprop
        if not isinstance(obj, (Output, Parameter, Condition)):
            IBOX_CURNAME = mapname

        # title override
        try:
            obj.title = parse_ibox_key(key["IBOX_TITLE"])
        except Exception:
            pass

    _populate(obj, key, mapname, rootdict)
    return obj


def auto_build_obj(obj, key, name=None):
    props = vars(obj)["propnames"]
    classname = obj.__class__
    for resname, resvalue in key.items():
        final_obj = classname(resname)
        if not name:
            name = final_obj.__class__.__name__
        auto_get_props(final_obj, f"{name}{resname}")

        add_obj(final_obj)


def change_obj_data(obj, find, value):
    if isinstance(obj, list):
        for n, v in enumerate(obj):
            change_obj_data(obj[n], find, value)
    elif isinstance(obj, If):
        obj_if = obj.data["Fn::If"]
        for n, v in enumerate(obj_if):
            if isinstance(v, Ref) and v.data["Ref"] == find:
                obj_if[n] = value


def gen_random_string():
    length = 16
    char_set = f"{string.ascii_letters}{string.digits}"
    if not hasattr(gen_random_string, "rng"):
        # Create a static variable
        gen_random_string.rng = random.SystemRandom()
    secret_string = "".join(
        [gen_random_string.rng.choice(char_set) for _ in range(length)]
    )

    return secret_string


def clf_compute_order(pattern):
    base_ord = 1

    for s, w in cfg.CLF_PATH_PATTERN_REPLACEMENT.items():
        pattern = pattern.replace(w, s)

    n_star = 0
    for n, v in enumerate(pattern):
        if v == "?":
            base_ord += 0.0001
        elif v == "*":
            if len(pattern) == n + 1 and n_star != 0:
                # v is last char but not the only star char
                base_ord += 0.0005
            elif n_star != 0:
                base_ord -= 0.000001 * n
            else:
                base_ord += 1000 / n
                n_star += 1
        elif n_star != 0:
            base_ord -= 0.001

    cfg.dbg_clf_compute_order[pattern] = base_ord

    return base_ord


def parse_ibox_key(value, conf={}):
    if not isinstance(value, str):
        return value
    if value.startswith(cfg.EVAL_PYTHON_FUNCTIONS_IN_CFG):
        return eval(value)
    for key in IBOX_SPECIAL_KEYS:
        if key in value:
            if key in conf:
                value = value.replace(key, conf[key])
            else:
                value = value.replace(key, globals().get(key, ""))
    value = value.replace("_", IBOX_RESNAME)
    value = value.replace(".", "")

    return value


def camel_to_snake(data):
    out = ""
    skip_next = False
    for n, v in enumerate(data):
        if skip_next:
            skip_next = False
            continue
        if v.isupper() and data[n + 1].isupper():
            out += f"_{v}{data[n+1]}"
            skip_next = True
        elif v.isupper():
            out += f"_{v}" if out else v
        else:
            out += v

    return out.upper()
