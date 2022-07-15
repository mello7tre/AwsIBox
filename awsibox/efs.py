import troposphere.efs as efs

from .common import *
from .shared import (
    Parameter,
    get_endvalue,
    get_expvalue,
    get_subvalue,
    auto_get_props,
    get_condition,
    add_obj,
)
from .ec2 import SecurityGroup, SecurityGroupIngress


class EFSMountTarget(efs.MountTarget):
    def __init__(self, title, index, sgname, efsresname, **kwargs):
        super().__init__(title, **kwargs)
        name = self.title
        self.Condition = name
        self.FileSystemId = Ref(efsresname)
        self.SecurityGroups = [Ref(sgname)]
        self.SubnetId = Select(str(index), Split(",", get_expvalue("SubnetsPrivate")))


# #################################
# ### START STACK INFRA CLASSES ###
# #################################


def EFS_FileStorage(key):
    for n, v in getattr(cfg, key).items():
        resname = f"{key}{n}"  # Ex. EFSFileSystemWordPress
        sgservername = f"SecurityGroupEFSServer{n}"
        sgclientname = f"SecurityGroupEFS{n}"
        sginame = f"SecurityGroupIngressEFS{n}"
        for i in range(cfg.AZones["MAX"]):
            mountname = f"EFSMountTarget{n}{i}"
            # conditions
            add_obj(
                {
                    mountname: And(
                        Condition(resname),
                        Equals(
                            FindInMap("AvabilityZones", Ref("AWS::Region"), f"Zone{i}"),
                            "True",
                        ),
                    )
                }
            )

            # resources
            r_Mount = EFSMountTarget(
                mountname, index=i, sgname=sgservername, efsresname=resname
            )

            add_obj(r_Mount)
        # conditions
        add_obj(get_condition(resname, "equals", "yes", f"{resname}Enabled"))

        # resources
        r_File = efs.FileSystem(resname)
        auto_get_props(r_File, indexname=n)

        r_SGServer = SecurityGroup(
            sgservername,
            Condition=resname,
            GroupDescription=f"Rule to access EFS FileSystem {n}",
        )

        r_SGClient = SecurityGroup(
            sgclientname,
            Condition=resname,
            GroupDescription=f"Enable access to EFS FileSystem {n}",
        )

        SGIExtra = {
            "Name": sginame,
            "Condition": resname,
            "FromPort": 2049,
            "GroupId": "Sub('${%s.GroupId}')" % sgservername,
            "SourceSecurityGroupId": "Ref('%s')" % sgclientname,
            "ToPort": 2049,
        }

        r_SGI = SecurityGroupIngress(sginame)
        auto_get_props(r_SGI, rootdict=SGIExtra)

        # outputs
        o_SGClient = Output(
            sgclientname,
            Condition=resname,
            Value=GetAtt(sgclientname, "GroupId"),
            Export=Export(sgclientname),
        )

        add_obj([r_File, r_SGServer, r_SGClient, r_SGI, o_SGClient])
