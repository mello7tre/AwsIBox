import troposphere.efs as efs

from shared import *


class EFSFileSystem(efs.FileSystem):
    def setup(self):
        self.Condition = self.title
        self.Encrypted = False
        self.PerformanceMode = 'generalPurpose'


class EFSMountTarget(efs.MountTarget):
    def setup(self, index, sgname, efsresname):
        name = self.title
        self.Condition = name
        self.FileSystemId = Ref(efsresname)
        self.SecurityGroups = [
            Ref(sgname)
        ]
        self.SubnetId = Select(str(index), Split(',', get_exported_value('SubnetsPrivate')))

# #################################
# ### START STACK INFRA CLASSES ###
# #################################

class EFS_FileStorage(object):
    def __init__(self, key):
        for n, v in RP_cmm[key].iteritems():
            resname =  key + n  # Ex. EFSFileSystemWordPress
            recordname = 'RecordSetEFS' + n  # Ex. RecordSetEFSWordPress
            sgservername = 'SecurityGroupEFSServer' + n  # Ex. SecurityGroupEFSServerWordPress
            sgclientname = 'SecurityGroupEFS' + n  # Ex. SecurityGroupEFSWordPress
            sginame = 'SecurityGroupIngressEFS' + n  # Ex. SecurityGroupIngressEFSWordPress
            for i in range(3):
                mountname = 'EFSMountTarget' + n + str(i)  # Ex. EFSMountTargetWordPress3
                # conditions
                do_no_override(True)
                c_FileZone = {mountname: And(
                    Condition(resname),
                    Equals(FindInMap('AvabilityZones', Ref('AWS::Region'), 'Zone' + str(i)), 'True')
                )}
                cfg.Conditions.append(c_FileZone)
                do_no_override(False)

                # resources
                r_Mount = EFSMountTarget(mountname)
                r_Mount.setup(index=i, sgname=sgservername, efsresname=resname)

                cfg.Resources.append(r_Mount)
            # conditions
            do_no_override(True)
            c_File = {resname: Not(
                Equals(get_final_value(resname + 'Enabled'), 'None')
            )}
            cfg.Conditions.append(c_File)
            do_no_override(False)

            # resources
            r_File = EFSFileSystem(resname)
            r_File.setup()

            r_Record = R53RecordSetEFS(recordname)
            r_Record.setup(n)

            r_SGServer = SecurityGroup(sgservername)
            r_SGServer.setup()
            r_SGServer.Condition = resname
            r_SGServer.GroupDescription = 'Rule to access EFS FileSystem ' + n

            r_SGClient = SecurityGroup(sgclientname)
            r_SGClient.setup()
            r_SGClient.Condition = resname
            r_SGClient.GroupDescription = 'Enable access to EFS FileSystem ' + n

            SGIExtra = {
                'Name': sginame,
                'Condition': resname,
                'FromPort': 2049,
                'GroupId': 'Sub(\'${' + sgservername  + '.GroupId}\')',
                'SourceSecurityGroupId': 'Ref(\'' + sgclientname + '\')',
                'ToPort': 2049
            }

            r_SGI = SecurityGroupIngress(sginame)
            auto_get_props(r_SGI, SGIExtra, rootdict=SGIExtra, mapname='', del_prefix=sginame)

            cfg.Resources.extend([
                r_File,
                r_Record,
                r_SGServer,
                r_SGClient,
                r_SGI,
            ])

            # outputs

            o_SG = Output(sgclientname)
            o_SG.Condition = resname
            o_SG.Value = GetAtt(sgclientname, 'GroupId')
            o_SG.Export = Export(sgclientname)

            cfg.Outputs.append(o_SG)

# Need to stay as last lines
import_modules(globals())
