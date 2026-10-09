"""Offline authored statistics examples. No empirical agent observations."""
import math
from statistics import NormalDist
from collections import Counter
import json
from fractions import Fraction
import sys


def count(x):
    if type(x) is not int or x < 0:
        raise ValueError('nonnegative exact integer required')
    return x


def probability(x, interior=False):
    if type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 1 or (interior and x in (0, 1)):
        raise ValueError('finite probability required')
    return x


def wilson(k, n, confidence=.95):
    count(k); count(n); probability(confidence, True)
    if not n or k > n:
        raise ValueError('require 0 <= successes <= positive n')
    # Use the lower tail: (1+c)/2 can round to 1 for interior c.
    z = -NormalDist().inv_cdf((1-confidence)/2)
    if z == 0 or n > sys.float_info.max:
        raise ValueError('confidence resolution or n exceeds binary64 Wilson support')
    p = k/n
    t = z/math.sqrt(n)
    d = 1+t*t
    centre = (p+t*t/2)/d
    radius = t*math.hypot(math.sqrt(p*(1-p)),t/2)/d
    return max(0, centre-radius), min(1, centre+radius)


def precision_n(p=.8, margin=.05, z=1.96):
    probability(p, True); probability(margin, True)
    if type(z) not in (float, int) or not math.isfinite(z) or z <= 0:
        raise ValueError('positive finite z required')
    # Exact rational arithmetic for the supplied binary floats; Python integers
    # can represent the count even when the float square would overflow.
    fp, fm, fz = Fraction(p), Fraction(margin), Fraction(z)
    return math.ceil(fz*fz*fp*(1-fp)/(fm*fm))


def design_effect(m, rho):
    count(m); probability(rho)
    if not m: raise ValueError('positive cluster size required')
    return 1+(m-1)*rho


def mcnemar(b, c):
    count(b); count(c)
    n=b+c
    if not n: return {'exact_p':1., 'corrected_chi2':0., 'asymptotic_p':1.}
    # Conditional two-sided binomial test for equal discordant probabilities.
    p=min(1., 2*sum(math.comb(n,i) for i in range(min(b,c)+1))/2**n)
    chi=max(0, abs(b-c)-1)**2/n
    return {'exact_p':p, 'corrected_chi2':chi, 'asymptotic_p':math.erfc(math.sqrt(chi/2))}


def kappa(table):
    if len(table)!=2 or any(len(row)!=2 for row in table): raise ValueError('2 by 2 table required')
    for row in table:
        for v in row: count(v)
    n=sum(map(sum,table))
    if not n: return None
    po=(table[0][0]+table[1][1])/n
    pe=sum(sum(table[i])*sum(row[i] for row in table) for i in range(2))/n**2
    return None if pe==1 else (po-pe)/(1-pe)


def nominal_alpha(items):
    """Items contain str labels or None. Singleton items supply no coincidences."""
    marg=Counter(); disagree=0.; n=0
    for item in items:
        if any(x is not None and type(x) is not str for x in item): raise ValueError('nominal str labels or None only')
        vals=[x for x in item if x is not None]
        m=len(vals)
        if m<2: continue
        counts=Counter(vals); marg.update(counts); n+=m
        disagree+=sum(a!=b for i,a in enumerate(vals) for j,b in enumerate(vals) if i!=j)/(m-1)
    if n<2: return None
    do=disagree/n
    de=(n*n-sum(v*v for v in marg.values()))/(n*(n-1))
    return None if de==0 else 1-do/de


def holm(ps, alpha=.05):
    probability(alpha, True)
    for p in ps: probability(p)
    order=sorted(range(len(ps)), key=lambda i: ps[i])
    adjusted=[0.]*len(ps); previous=0.
    for rank,i in enumerate(order):
        previous=max(previous, min(1., (len(ps)-rank)*ps[i]))
        adjusted[i]=previous
    return {'adjusted':adjusted, 'reject':[p<=alpha for p in adjusted]}


def e_path(xs, p0=.5, p1=.75):
    probability(p0, True); probability(p1, True)
    if p1<=p0: raise ValueError('upper alternative required')
    success_log=math.log(p1)-math.log(p0)
    failure_log=math.log1p(-p1)-math.log1p(-p0)
    successes=failures=0; maximum_log=0.; out=[]
    def represent(log_value):
        try: value=math.exp(log_value)
        except OverflowError: return None
        return value if value != 0 else None
    for x in xs:
        if type(x) is not int or x not in (0,1): raise ValueError('binary exact integers required')
        successes+=x; failures+=1-x
        try: log_value=math.fsum([successes*success_log,failures*failure_log])
        except (OverflowError, ValueError):
            raise ValueError('log wealth exceeds finite representation') from None
        if not math.isfinite(log_value): raise ValueError('log wealth exceeds finite representation')
        maximum_log=max(maximum_log,log_value)
        out.append({'e':represent(log_value),'always_valid_p':represent(-maximum_log),
                    'log_e':log_value,'log_always_valid_p':-maximum_log})
    return out


def cusum(zs, k=.5, h=3.):
    for v in (k,h):
        if type(v) not in (int,float) or not math.isfinite(v) or v<0: raise ValueError('finite nonnegative configuration required')
    if h==0: raise ValueError('positive threshold required')
    state=0.; result=[]
    for z in zs:
        if z is None:
            result.append({'pre_reset':state,'alarm':False,'missing':True}); continue
        if type(z) not in (int,float) or not math.isfinite(z): raise ValueError('finite score required')
        try:
            added=state+z
            derived=added-k
            finite=math.isfinite(added) and math.isfinite(derived)
        except OverflowError:
            finite=False
        if not finite: raise ValueError('CUSUM derived state exceeds finite representation')
        state=max(0.,derived); alarm=state>=h
        result.append({'pre_reset':state,'alarm':alarm,'missing':False})
        if alarm: state=0.
    return result


def paired_power(n, discordance=.2, repair_share=.75, alpha=.05):
    """Exact unconditional power, summing conditional exact McNemar rejection."""
    count(n); probability(discordance); probability(repair_share); probability(alpha,True)
    if n>400: raise ValueError('teaching calculation capped at 400 pairs')
    result=0.
    for d in range(n+1):
        pd=math.comb(n,d)*discordance**d*(1-discordance)**(n-d)
        for b in range(d+1):
            if mcnemar(b,d-b)['exact_p']<=alpha:
                result+=pd*math.comb(d,b)*repair_share**b*(1-repair_share)**(d-b)
    return result


def examples():
    return {'evidence':'authored teaching inputs, not empirical measurements',
      'wilson_18_20':wilson(18,20), 'precision_n':precision_n(),
      'design_effect':design_effect(10,.5),'effective_rows':100/design_effect(10,.5),
      'mcnemar_15_5':mcnemar(15,5),'mcnemar_30_10':mcnemar(30,10),
      'kappa':kappa([[45,5],[10,40]]),
      'nominal_alpha':nominal_alpha([['A','A','A'],['A','B',None],['B','B',None],['A',None,None]]),
      'holm':holm([.004,.012,.018,.04,.2]), 'e_path':e_path([1]*8+[0]),
      'cusum':cusum([0,1,1.5,None,2,0]), 'power_100':paired_power(100), 'power_200':paired_power(200)}

if __name__=='__main__':
    print(json.dumps(examples(), indent=2, allow_nan=False))
