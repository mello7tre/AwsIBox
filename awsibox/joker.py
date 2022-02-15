from .common import *
from .shared import auto_get_props, add_obj, Parameter, get_condition


def Joker(key, module, cls):
    for n, v in getattr(cfg, key).items():
        if not v.get("IBOX_ENABLED", True):
            continue

        resname = f"{key}{n}"

        mod = __import__(f"troposphere.{module}")
        my_module = getattr(mod, module)
        my_class = getattr(my_module, cls)

        res = my_class(resname)
        auto_get_props(res, indexname=n)

        if v.get("Create"):
            add_obj(
                Parameter(
                    f"{resname}Create",
                    Description=f"Create {resname}",
                    AllowedValues=["", "yes", "no"],
                )
            )
            add_obj(get_condition(resname, "equals", "yes", f"{resname}Create"))
            add_obj(Output(resname, Value=Ref(resname)))
            res.Condition = resname

        add_obj(res)
