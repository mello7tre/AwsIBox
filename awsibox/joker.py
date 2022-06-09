from .common import *
from .shared import auto_get_props, add_obj, Parameter, get_condition


def Joker(key, module, cls):
    for n, v in getattr(cfg, key).items():
        if not v.get("IBOX_ENABLED", True):
            continue

        mapname = None
        resname = f"{key}{n}"

        # change resource name using key IBOX_RESNAME
        ibox_resname = v.get("IBOX_RESNAME")
        if ibox_resname:
            mapname = resname
            resname = ibox_resname

        mod = __import__(f"troposphere.{module}")
        my_module = getattr(mod, module)
        my_class = getattr(my_module, cls)

        obj = my_class(resname)

        # use IBOX_SOURCE_OBJ to prepopulate obj
        ibox_source_obj = v.get("IBOX_SOURCE_OBJ")
        if ibox_source_obj:
            ibox_source_obj = ibox_source_obj.replace("{IBOX_INDEXNAME}", n)
            auto_get_props(obj, mapname=ibox_source_obj, indexname=n)
            # reset obj title, if changed by IBOX_TITLE key
            obj.title = resname

        # populate obj
        auto_get_props(obj, mapname=mapname, indexname=n)

        if v.get("Create"):
            add_obj(
                Parameter(
                    f"{resname}Create",
                    Description=f"Create {resname}",
                    AllowedValues=["", "yes", "no"],
                )
            )
            add_obj(get_condition(resname, "equals", "yes", f"{resname}Create"))
            add_obj(Output(resname, Condition=resname, Value=Ref(resname)))
            obj.Condition = resname

        add_obj(obj)
