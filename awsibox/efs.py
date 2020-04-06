import troposphere.efs as efs

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
                     get_subvalue, auto_get_props, get_condition, add_obj)
from .route53 import R53RecordSetEFS
from .securitygroup import SecurityGroup, SecurityGroupIngress


class EFSFileSystem(efs.FileSystem):
    def __init__(self, title, key, **kwargs):
        super().__init__(title, **kwargs)
        self.Condition = self.title
        # by defualt do not encrypt and lower cost performaceMode
        self.Encrypted = False
        self.PerformanceMode = 'generalPurpose'
        auto_get_props(self, key, recurse=True)


class EFSMountTarget(efs.MountTarget):
    def __init__(self, title, index, sgname, efsresname, **kwargs):
        super().__init__(title, **kwargs)
        name = self.title
        self.Condition = name
        self.FileSystemId = Ref(efsresname)
        self.SecurityGroups = [
            Ref(sgname)
        ]
        self.SubnetId = Select(
            str(index), Split(',', get_expvalue('SubnetsPrivate')))


# #################################
# ### START STACK INFRA CLASSES ###
# #################################


class EFS_FileStorage(object):
    def __init__(self, key):
        for n, v in getattr(cfg, key).items():
            resname = f'{key}{n}'  # Ex. EFSFileSystemWordPress
            recordname = f'RecordSetEFS{n}'
            sgservername = f'SecurityGroupEFSServer{n}'
            sgclientname = f'SecurityGroupEFS{n}'
            sginame = f'SecurityGroupIngressEFS{n}'
            for i in range(cfg.AZones['MAX']):
                mountname = f'EFSMountTarget{n}{i}'
                # conditions
                add_obj(
                    {mountname: And(
                        Condition(resname),
                        Equals(
                            FindInMap(
                                'AvabilityZones',
                                Ref('AWS::Region'),
                                f'Zone{i}'),
                            'True')
                    )}
                )

                # resources
                r_Mount = EFSMountTarget(
                    mountname, index=i,
                    sgname=sgservername, efsresname=resname)

                add_obj(r_Mount)
            # conditions
            add_obj(get_condition(
                resname, 'not_equals', 'None', f'{resname}Enabled'))

            # resources
            r_File = EFSFileSystem(resname, key=v)

            if v['R53'] != 'None':
                r_Record = R53RecordSetEFS(recordname, efsname=n)

                add_obj(r_Record)

            r_SGServer = SecurityGroup(sgservername)
            r_SGServer.Condition = resname
            r_SGServer.GroupDescription = (
                f'Rule to access EFS FileSystem {n}')

            r_SGClient = SecurityGroup(sgclientname)
            r_SGClient.Condition = resname
            r_SGClient.GroupDescription = (
                f'Enable access to EFS FileSystem {n}')

            SGIExtra = {
                'Name': sginame,
                'Condition': resname,
                'FromPort': 2049,
                'GroupId': 'Sub(\'${%s.GroupId}\')' % sgservername,
                'SourceSecurityGroupId': 'Ref(\'%s\')' % sgclientname,
                'ToPort': 2049
            }

            r_SGI = SecurityGroupIngress(sginame)
            auto_get_props(r_SGI, SGIExtra, rootdict=SGIExtra,
                           mapname='', del_prefix=sginame)

            add_obj([
                r_File,
                r_SGServer,
                r_SGClient,
                r_SGI,
            ])

            # outputs

            o_SG = Output(sgclientname)
            o_SG.Condition = resname
            o_SG.Value = GetAtt(sgclientname, 'GroupId')
            o_SG.Export = Export(sgclientname)

            add_obj(o_SG)
