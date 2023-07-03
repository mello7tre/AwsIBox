import troposphere.rds as rds

from ..common import *
from ..shared import (
    get_endvalue,
    auto_get_props,
    add_obj,
)


class RDSDBParameterGroup(rds.DBParameterGroup):
    def __init__(self, title, dbinstance, **kwargs):
        super().__init__(title, **kwargs)
        self.Description = Sub("MYSQL %s - ${AWS::StackName}" % self.title)
        self.Family = Sub(
            "${Engine}${EngineVersion}",
            **{
                "Engine": get_endvalue(f"{dbinstance}Engine"),
                "EngineVersion": Join(
                    ".",
                    [
                        Select(
                            0, Split(".", get_endvalue(f"{dbinstance}EngineVersion"))
                        ),
                        Select(
                            1, Split(".", get_endvalue(f"{dbinstance}EngineVersion"))
                        ),
                    ],
                ),
            },
        )


def RDS_DB(key):
    for n, v in getattr(cfg, key).items():
        mapname = f"{key}{n}"

        if not v["IBOX_ENABLED"]:
            continue

        # trick to keep current in use resname and obj.title
        resname = v.get("IBOX_RESNAME", mapname)

        # resources
        r_DB = rds.DBInstance(resname)
        auto_get_props(r_DB, mapname=mapname)
        # trick - when providing DBSnapshotIdentifier
        # or SourceDBInstanceIdentifier some props must not exists
        for m in ["DBName", "MasterUsername", "MasterUserPassword"]:
            setattr(
                r_DB,
                m,
                If(
                    f"{mapname}DBInstanceSkipProperties",
                    Ref("AWS::NoValue"),
                    getattr(r_DB, m),
                ),
            )
        for m in ["SourceDBInstanceIdentifier", "DBSnapshotIdentifier"]:
            setattr(r_DB, m, If(f"{mapname}{m}", getattr(r_DB, m), Ref("AWS::NoValue")))

        # trick fixed name to avoid reboot for now
        # best way should be to use a name like DBParameterGroup{Engine}
        #r_PG = RDSDBParameterGroup("DBParameterGroup1", mapname)
        #r_PG.Parameters = cfg.DBParameterGroup1

        add_obj([
            r_DB, 
            #r_PG
        ])
