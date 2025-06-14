import logging
from copy import deepcopy
from troposphere import Output, Ref

from .. import cfg
from ..RP import RP_to_cfg, merge_dict
from ..tropo_override import Parameter
from ..shared import (
    auto_get_props,
    add_obj,
    do_no_override,
    get_condition,
    parse_ibox_key,
    ibox_eval,
)


def Joker(key, module, cls):
    for n, v in getattr(cfg, key).items():
        if key == "Condition":
            # Condition are just dict, directly add them
            do_no_override(True)
            add_obj({n: ibox_eval(v)})
            do_no_override(False)
            continue

        # IBOX_ENABLED_IF have precedence over IBOX_ENABLED
        # if it does exist skip testing IBOX_ENABLED
        ibox_enabled_if = v.get("IBOX_ENABLED_IF")
        if ibox_enabled_if:
            if not ibox_eval(str(ibox_enabled_if)):
                continue
        elif not v.get("IBOX_ENABLED", True):
            continue

        parse_ibox_key_conf = {"IBOX_INDEXNAME": n}
        resname = f"{key}{n}"
        mapname = resname

        # change resource name using key IBOX_RESNAME
        ibox_resname = v.get("IBOX_RESNAME")
        if ibox_resname:
            resname = parse_ibox_key(ibox_resname, parse_ibox_key_conf)

        if cfg.debug:
            logging.error(f"Joker processing: {resname}")

        # get IBOX_LINKED_OBJ keys
        linked_obj_name = v.get("IBOX_LINKED_OBJ_NAME", "")
        linked_obj_index = v.get("IBOX_LINKED_OBJ_INDEX", "")

        if module:
            mod = __import__(f"troposphere.{module}")
            my_module = getattr(mod, module)
        else:
            # for classes in troposphere __init__
            my_module = __import__("troposphere")
        my_class = getattr(my_module, cls)

        obj = my_class(resname)

        # use IBOX_SOURCE_OBJ to prepopulate obj
        ibox_source_obj = v.get("IBOX_SOURCE_OBJ", [])
        if isinstance(ibox_source_obj, str):
            ibox_source_obj = [ibox_source_obj]
        for source_obj in ibox_source_obj:
            source_obj = parse_ibox_key(source_obj, parse_ibox_key_conf)
            source_obj_conf = deepcopy(getattr(cfg, source_obj))
            RP_to_cfg(
                source_obj_conf,
                prefix=mapname,
                overwrite=False,
                mappedvalues=cfg.mappedvalues,
                check_mapped=True,
            )
            v = merge_dict(v, source_obj_conf, keep=True)

            # Always enable obj, as source obj can have key IBOX_ENABLED False
            v["IBOX_ENABLED"] = True

            # Uncomment to use old method: auto_get_props
            # auto_get_props(obj, mapname=source_obj, indexname=n)
            # #reset obj title, if changed by IBOX_TITLE key
            # obj.title = resname

        # autocreate condition
        if v.get("Create"):
            add_obj(
                Parameter(
                    f"{resname}Create",
                    Description=f"Create {resname}",
                    AllowedValues=["", "yes", "no"],
                    Type="String",
                    Default="",
                )
            )
            if "Create.IBOX_AUTO_PO" not in v:
                add_obj(get_condition(resname, "equals", "yes", f"{resname}Create"))
                add_obj(
                    Output(
                        resname,
                        Condition=resname,
                        Value=Ref(v.get("IBOX_TITLE", resname)),
                    )
                )
                if not hasattr(obj, "Condition"):
                    obj.Condition = resname

        # populate obj
        auto_get_props(
            obj,
            mapname=mapname,
            indexname=n,
            linked_obj_name=linked_obj_name,
            linked_obj_index=linked_obj_index,
        )

        add_obj(obj)
