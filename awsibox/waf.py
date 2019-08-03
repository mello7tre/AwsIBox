import troposphere.waf as waf
import troposphere.wafregional as wafr

from shared import *


class WAFIPSet(waf.IPSet):
    def setup(self, name):
        self.Condition = self.title  # Ex. WafIPSetAwsNat
        self.Name = name  # Ex. AwsNat


class WAFByteMatchSet(waf.ByteMatchSet):
    def setup(self, name):
        self.Condition = self.title
        self.Name = name


class WAFRule(waf.Rule):
    def setup(self, name):
        self.Condition = self.title  # Ex. WafRuleBlockIPsNotAllowed
        self.Name = name  # Ex. BlockIPsNotAllowed
        self.MetricName = self.Name


class WAFWebACL(waf.WebACL):
    def setup(self, name):
        self.Condition = self.title  # Ex. WafWebAclApplicationLoadBalancerExternal
        self.Name = name  # Ex. ApplicationLoadBalancerExternal
        self.MetricName = self.Name


class WAFGlobalIPSet(WAFIPSet):
    pass


class WAFGlobalByteMatchSet(WAFByteMatchSet):
    pass


class WAFGlobalRule(WAFRule):
    pass


class WAFGlobalWebAcl(WAFWebACL):
    pass


class WAFRegionalIPSet(wafr.IPSet, WAFIPSet):
    pass


class WAFRegionalByteMatchSet(wafr.ByteMatchSet, WAFByteMatchSet):
    pass


class WAFRegionalRule(wafr.Rule, WAFRule):
    pass


class WAFRegionalWebAcl(wafr.WebACL, WAFWebACL):
    pass

# ############################################
# ### START STACK META CLASSES AND METHODS ###
# ############################################

class WAFIPSetDescriptors(waf.IPSetDescriptors, wafr.IPSetDescriptors):
    def setup(self, name):
        self.Type = 'IPV4'
        self.Value=Select(int(self.title), get_final_value(name + 'Ips'))


class WAFFieldToMatch(waf.FieldToMatch, wafr.FieldToMatch):
    def setup(self, key):
        name = self.title
        auto_get_props(self, key, del_prefix='FieldToMatch')


class WAFByteMatchTuples(waf.ByteMatchTuples, wafr.ByteMatchTuples):
    def setup(self, key):
        name = self.title  # Ex. WafByteMatchSets1Matches1
        auto_get_props(self, key)
        FieldToMatch = WAFFieldToMatch(self.title)
        FieldToMatch.setup(key=key)
        self.FieldToMatch = FieldToMatch


class WAFPredicates(waf.Predicates, wafr.Predicates):
    def setup(self, name, ptype, wtype):
        self.Negated = get_final_value(name + 'Negated')
        if ptype == 'ByteMatch':
            self.DataId = Ref('Waf' + wtype + 'ByteMatchSet' + self.title)
            self.Type = 'ByteMatch'
        if ptype == 'IPMatch':
            self.DataId = Ref('Waf' + wtype + 'IPSet' + self.title)
            self.Type = 'IPMatch'
        if ptype == 'SizeConstraint':
            self.DataId = Ref('Waf' + wtype + 'SizeConstraintSet' + self.title)
            self.Type = 'SizeConstraint'
        if ptype == 'SqlInjectionMatch':
            self.DataId = Ref('Waf' + wtype + 'SqlInjectionMatchSet' + self.title)
            self.Type = 'SqlInjectionMatch'
        if ptype == 'XssMatch':
            self.DataId = Ref('Waf' + wtype + 'XssMatchSet' + self.title)
            self.Type = 'XssMatch'


class WAFAction(waf.Action, wafr.Action):
    pass


class WAFWebACLRule(waf.Rules, wafr.Rules):
    def setup(self, name, index, wtype):
        self.Action = WAFAction(
            Type=get_final_value(name + 'Action')
        )
        self.Priority = index
        self.RuleId = Ref('Waf' + wtype + 'Rule' + self.title)

# ##########################################
# ### END STACK META CLASSES AND METHODS ###
# ##########################################


class WAF_IPSets(object):
    def __init__(self, key, wtype=''):
        for n, v in RP_cmm[key].iteritems():
            name = key.replace('Waf', wtype)  # Ex. RegionalIPSet
            resname = 'Waf' + name + n  # Ex. WafRegionalIPSetAwsNat 
            mapname = key + n  # Ex. WafIPSetAwsNat

            # conditions
            do_no_override(True)
            C_Waf = {resname: And(
                Not(Equals(get_final_value(mapname + 'Enabled'), 'None')),
                Condition('Global') if wtype == 'Global' else Equals('1', '1'),
                Or(
                    Equals(get_final_value(mapname + 'WafType'), wtype),
                    Equals(get_final_value(mapname + 'WafType'), 'Common'),
                )
            )}
            
            cfg.Conditions.append(C_Waf)
            do_no_override(False)

            # resources
            IPSetDescriptors = []
            for i, j in enumerate(v['Ips']):
                IPSetDescriptor = WAFIPSetDescriptors(str(i))
                IPSetDescriptor.setup(name=mapname)
                IPSetDescriptors.append(IPSetDescriptor)

            IPSet = globals()['WAF' + name](resname)
            IPSet.setup(name=n)
            IPSet.IPSetDescriptors = IPSetDescriptors

            cfg.Resources.append(IPSet)


class WAF_ByteMatchSets(object):
    def __init__(self, key, wtype=''):
        for n, v in RP_cmm[key].iteritems():
            name = key.replace('Waf', wtype)  # Ex. RegionalByteMatchSet
            resname = 'Waf' + name + n
            mapname = key + n

            # conditions
            do_no_override(True)
            C_Waf = {resname: And(
                Not(Equals(get_final_value(mapname + 'Enabled'), 'None')),
                Condition('Global') if wtype == 'Global' else Equals('1', '1'),
                Or(
                    Equals(get_final_value(mapname + 'WafType'), wtype),
                    Equals(get_final_value(mapname + 'WafType'), 'Common'),
                )
            )}
            
            cfg.Conditions.append(C_Waf)
            do_no_override(False)


            # resources
            ByteMatchTuples = []
            for m, w in v['Matches'].iteritems():
                matchname = mapname + 'Matches' + str(m)  # Ex. WafByteMatchSets1Matches1
                ByteMatchTuple = WAFByteMatchTuples(matchname)
                ByteMatchTuple.setup(key=w)

                ByteMatchTuples.append(ByteMatchTuple)

            ByteMatchSet = globals()['WAF' + name](resname)
            ByteMatchSet.setup(name=n)
            ByteMatchSet.ByteMatchTuples = ByteMatchTuples

            cfg.Resources.append(ByteMatchSet)


class WAF_Rules(object):
    def __init__(self, key, wtype=''):
        for n, v in RP_cmm[key].iteritems():
            name = key.replace('Waf', wtype)  # Ex. RegionalIPSet
            resname = 'Waf' + name + n  # Ex. WafRegionalIPSetAwsNat 
            mapname = key + n  # Ex. WafIPSetAwsNat

            # conditions
            do_no_override(True)
            C_Waf = {resname: And(
                Not(Equals(get_final_value(mapname + 'Enabled'), 'None')),
                Condition('Global') if wtype == 'Global' else Equals('1', '1'),
                Or(
                    Equals(get_final_value(mapname + 'WafType'), wtype),
                    Equals(get_final_value(mapname + 'WafType'), 'Common'),
                )
            )}
            
            cfg.Conditions.append(C_Waf)
            do_no_override(False)


            # resources
            Predicates = []
            O_Predicates = []
            for m in v['Predicates']:
                predmapname = mapname + 'Predicates' + m  # Ex. WafByteMatchSetWafRules2Rules1
                predresname = m
                ptype = v['Type']
                Predicate = WAFPredicates(predresname)
                Predicate.setup(name=predmapname, ptype=ptype, wtype=wtype)

                Predicates.append(
                    If(
                        Predicate.DataId.data['Ref'],
                        Predicate,
                        Ref('AWS::NoValue')
                    )
                )

                O_Predicates.append(m)

            Rule = globals()['WAF' + name](resname)
            Rule.setup(name=n)
            Rule.Predicates = Predicates

            cfg.Resources.append(Rule)

            # outputs
            O_Rule = Output(mapname + wtype)
            O_Rule.Condition = resname
            O_Rule.Value = ','.join(O_Predicates)

            cfg.Outputs.append(O_Rule)


class WAF_WebAcls(object):
    def __init__(self, key, wtype=''):
        for n, v in RP_cmm[key].iteritems():
            name = key.replace('Waf', wtype)  # Ex. RegionalIPSet
            resname = 'Waf' + name + n  # Ex. WafRegionalIPSetAwsNat 
            mapname = key + n  # Ex. WafIPSetAwsNat

            # conditions
            do_no_override(True)
            C_Waf = {resname: And(
                Not(Equals(get_final_value(mapname + 'Enabled'), 'None')),
                Condition('Global') if wtype == 'Global' else Equals('1', '1'),
                Or(
                    Equals(get_final_value(mapname + 'WafType'), wtype),
                    Equals(get_final_value(mapname + 'WafType'), 'Common'),
                )
            )}
            
            cfg.Conditions.append(C_Waf)
            do_no_override(False)


            # resources
            Rules = []
            O_Rules = []
            for w, m in enumerate(v['Rules'], start=1):
                rulemapname = mapname + 'Rules' + str(m)
                ruleresname = m  # Ex. BlockIPsNotAllowed
                Rule = WAFWebACLRule(ruleresname)
                Rule.setup(name=rulemapname, index=w, wtype=wtype)

                Rules.append(Rule)

                O_Rules.append(m)

            WebACL = globals()['WAF' + name](resname)
            WebACL.setup(name=n)
            WebACL.Rules = Rules
            WebACL.DefaultAction = WAFAction(Type=v['DefaultAction'])

            cfg.Resources.append(WebACL)

            # outputs
            O_WebACL = Output(mapname + wtype)
            O_WebACL.Condition = resname
            O_WebACL.Value = Sub('${' + resname + '} - ' + ','.join(O_Rules))

            cfg.Outputs.append(O_WebACL)

class WAF_GlobalByteMatchSets(object):
    def __init__(self, key):
        WAF_ByteMatchSets(key, wtype='Global')


class WAF_GlobalIPSets(object):
    def __init__(self, key):
        WAF_IPSets(key, wtype='Global')


class WAF_GlobalRules(WAF_Rules):
    def __init__(self, key):
        WAF_Rules(key, wtype='Global')


class WAF_GlobalWebAcls(WAF_WebAcls):
    def __init__(self, key):
        WAF_WebAcls(key, wtype='Global')


class WAF_RegionalByteMatchSets(object):
    def __init__(self, key):
        WAF_ByteMatchSets(key, wtype='Regional')


class WAF_RegionalIPSets(object):
    def __init__(self, key):
        WAF_IPSets(key, wtype='Regional')


class WAF_RegionalRules(WAF_Rules):
    def __init__(self, key):
        WAF_Rules(key, wtype='Regional')


class WAF_RegionalWebAcls(WAF_WebAcls):
    def __init__(self, key):
        WAF_WebAcls(key, wtype='Regional')

# Need to stay as last lines
import_modules(globals())
