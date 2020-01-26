import troposphere.waf as waf
import troposphere.wafregional as wafr

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
                     get_subvalue, auto_get_props, get_condition, add_obj)


class WAFIPSet(waf.IPSet):
    def __init__(self, title, name, **kwargs):
        super().__init__(title, **kwargs)
        self.Condition = self.title  # Ex. WafIPSetAwsNat
        self.Name = name  # Ex. AwsNat


class WAFByteMatchSet(waf.ByteMatchSet):
    def __init__(self, title, name, **kwargs):
        super().__init__(title, **kwargs)
        self.Condition = self.title
        self.Name = name


class WAFRule(waf.Rule):
    def __init__(self, title, name, **kwargs):
        super().__init__(title, **kwargs)
        self.Condition = self.title  # Ex. WafRuleBlockIPsNotAllowed
        self.Name = name  # Ex. BlockIPsNotAllowed
        self.MetricName = self.Name


class WAFWebACL(waf.WebACL):
    def __init__(self, title, name, **kwargs):
        super().__init__(title, **kwargs)
        self.Condition = self.title
        self.Name = name
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
    def __init__(self, title, name, **kwargs):
        super().__init__(title, **kwargs)
        self.Type = 'IPV4'
        self.Value = Select(int(self.title), get_endvalue(f'{name}Ips'))


class WAFFieldToMatch(waf.FieldToMatch, wafr.FieldToMatch):
    def __init__(self, title, key, **kwargs):
        super().__init__(title, **kwargs)
        name = self.title
        auto_get_props(self, key, del_prefix='FieldToMatch')


class WAFByteMatchTuples(waf.ByteMatchTuples, wafr.ByteMatchTuples):
    def __init__(self, title, key, **kwargs):
        super().__init__(title, **kwargs)
        name = self.title  # Ex. WafByteMatchSets1Matches1
        auto_get_props(self, key)
        FieldToMatch = WAFFieldToMatch(self.title, key=key)
        self.FieldToMatch = FieldToMatch


class WAFPredicates(waf.Predicates, wafr.Predicates):
    def __init__(self, title, name, ptype, wtype, **kwargs):
        super().__init__(title, **kwargs)
        self.Negated = get_endvalue(f'{name}Negated')
        if ptype == 'ByteMatch':
            self.DataId = Ref(
                f'Waf{wtype}ByteMatchSet{self.title}')
            self.Type = 'ByteMatch'
        if ptype == 'IPMatch':
            self.DataId = Ref(
                f'Waf{wtype}IPSet{self.title}')
            self.Type = 'IPMatch'
        if ptype == 'SizeConstraint':
            self.DataId = Ref(
                f'Waf{wtype}SizeConstraintSet{self.title}')
            self.Type = 'SizeConstraint'
        if ptype == 'SqlInjectionMatch':
            self.DataId = Ref(
                f'Waf{wtype}SqlInjectionMatchSet{self.title}')
            self.Type = 'SqlInjectionMatch'
        if ptype == 'XssMatch':
            self.DataId = Ref(
                f'Waf{wtype}XssMatchSet{self.title}')
            self.Type = 'XssMatch'


class WAFAction(waf.Action, wafr.Action):
    pass


class WAFWebACLRule(waf.Rules, wafr.Rules):
    def __init__(self, title, name, index, wtype, **kwargs):
        super().__init__(title, **kwargs)
        self.Action = WAFAction(
            Type=get_endvalue(f'{name}Action')
        )
        self.Priority = index
        self.RuleId = Ref(f'Waf{wtype}Rule{self.title}')


def WAF_condition(condname, mapname, wtype):
    return {condname: And(
        get_condition('', 'not_equals', 'None', f'{mapname}Enabled'),
        Condition('Global') if wtype == 'Global' else Equals('1', '1'),
        Or(
            get_condition('', 'equals', wtype, f'{mapname}WafType'),
            get_condition('', 'equals', 'Common', f'{mapname}WafType')
        )
    )}

# ##########################################
# ### END STACK META CLASSES AND METHODS ###
# ##########################################


class WAF_IPSets(object):
    def __init__(self, key, wtype=''):
        for n, v in getattr(cfg, key).items():
            name = key.replace('Waf', wtype)  # Ex. RegionalIPSet
            resname = f'Waf{name}{n}'  # Ex. WafRegionalIPSetAwsNat
            mapname = f'{key}{n}'  # Ex. WafIPSetAwsNat

            # conditions
            add_obj(WAF_condition(resname, mapname, wtype))

            # resources
            IPSetDescriptors = []
            for i, j in enumerate(v['Ips']):
                IPSetDescriptor = WAFIPSetDescriptors(str(i), name=mapname)
                IPSetDescriptors.append(IPSetDescriptor)

            IPSet = globals()[f'WAF{name}'](resname, name=n)
            IPSet.IPSetDescriptors = IPSetDescriptors

            add_obj(IPSet)


class WAF_ByteMatchSets(object):
    def __init__(self, key, wtype=''):
        for n, v in getattr(cfg, key).items():
            name = key.replace('Waf', wtype)  # Ex. RegionalByteMatchSet
            resname = f'Waf{name}{n}'
            mapname = f'{key}{n}'

            # conditions
            add_obj(WAF_condition(resname, mapname, wtype))

            # resources
            ByteMatchTuples = []
            for m, w in v['Matches'].items():
                matchname = f'{mapname}Matches{m}'
                ByteMatchTuple = WAFByteMatchTuples(matchname, key=w)

                ByteMatchTuples.append(ByteMatchTuple)

            ByteMatchSet = globals()[f'WAF{name}'](resname, name=n)
            ByteMatchSet.ByteMatchTuples = ByteMatchTuples

            add_obj(ByteMatchSet)


class WAF_Rules(object):
    def __init__(self, key, wtype=''):
        for n, v in getattr(cfg, key).items():
            name = key.replace('Waf', wtype)  # Ex. RegionalIPSet
            resname = f'Waf{name}{n}'  # Ex. WafRegionalIPSetAwsNat
            mapname = f'{key}{n}'  # Ex. WafIPSetAwsNat

            # conditions
            add_obj(WAF_condition(resname, mapname, wtype))

            # resources
            Predicates = []
            O_Predicates = []
            for m in v['Predicates']:
                predmapname = f'{mapname}Predicates{m}'
                predresname = m
                ptype = v['Type']
                Predicate = WAFPredicates(
                    predresname, name=predmapname, ptype=ptype, wtype=wtype)

                Predicates.append(
                    If(
                        Predicate.DataId.data['Ref'],
                        Predicate,
                        Ref('AWS::NoValue')
                    )
                )

                O_Predicates.append(m)

            Rule = globals()[f'WAF{name}'](resname, name=n)
            Rule.Predicates = Predicates

            add_obj(Rule)

            # outputs
            O_Rule = Output(f'{mapname}{wtype}')
            O_Rule.Condition = resname
            O_Rule.Value = ','.join(O_Predicates)

            add_obj(O_Rule)


class WAF_WebAcls(object):
    def __init__(self, key, wtype=''):
        for n, v in getattr(cfg, key).items():
            name = key.replace('Waf', wtype)  # Ex. RegionalIPSet
            resname = f'Waf{name}{n}'  # Ex. WafRegionalIPSetAwsNat
            mapname = f'{key}{n}'  # Ex. WafIPSetAwsNat

            # conditions
            add_obj(WAF_condition(resname, mapname, wtype))

            # resources
            Rules = []
            O_Rules = []
            for w, m in enumerate(v['Rules'], start=1):
                rulemapname = f'{mapname}Rules{m}'
                ruleresname = m  # Ex. BlockIPsNotAllowed
                Rule = WAFWebACLRule(
                    ruleresname, name=rulemapname, index=w, wtype=wtype)

                Rules.append(Rule)

                O_Rules.append(m)

            WebACL = globals()[f'WAF{name}'](resname, name=n)
            WebACL.Rules = Rules
            WebACL.DefaultAction = WAFAction(Type=v['DefaultAction'])

            add_obj(WebACL)

            # outputs
            O_WebACL = Output(f'{mapname}{wtype}')
            O_WebACL.Condition = resname
            O_WebACL.Value = Sub('${%s} - %s' % (resname, ','.join(O_Rules)))

            add_obj(O_WebACL)


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
