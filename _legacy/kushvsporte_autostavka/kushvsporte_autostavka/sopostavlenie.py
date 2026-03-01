import json
#from fuzzywuzzy import fuzz, process
from rapidfuzz import fuzz, process



def dict_zamen(s, sl_chemps_zamen):
    if len(sl_chemps_zamen) != 0:
        for k,v in sl_chemps_zamen.items():
            s = s.replace(k,v)
            
    s = s.replace('Чемпионат','').replace('-live','')
    return s

def match_leagues_fuzzy(sp1, sp2, sl_chemps_zamen):    
    # Сравнение лиг между собой    
    sum_ratio = 0
    sp2 = dict_zamen(sp2, sl_chemps_zamen)
    try:
        sum_ratio = fuzz.WRatio(sp1.replace('-live','').lower().strip(),
                                sp2.lower().strip())        
    except:
        pass    
    #print(sum_ratio, sp1, sp2)    
    return sum_ratio


def get_sopostavlenie(m, m2, param_ratio, sl_chemps_zamen):
    sl_sopostavleniy = {}
    m.sort()    
    for sp1 in m:
        sl_sopostavleniy[sp1] = ''
        m2_copy = m2.copy()        
        sp_val = []
        for sp2 in m2_copy:
            result = match_leagues_fuzzy(sp1, sp2, sl_chemps_zamen)
            if result>=param_ratio:
                sp_val.append([result,sp2])
        
        if len(sp_val) != 0:
            sp_val.sort()            
            #for s in sp_val:
            #    print(s)
            if sp_val[-1][0] == 100:
                m2.remove(sp_val[-1][1])
            sl_sopostavleniy[sp1] = sp_val[-1][1]

    return sl_sopostavleniy


if __name__ == "__main__":
    sl_sopostavleniy = {}
    
    with open('sl_chemps_zamen.json', 'r', encoding='utf-8') as file:
        sl_chemps_zamen = json.load(file)
    
    for k,v in sl_chemps_zamen.items():
        print(k,v)
    
    input()
    # Считываем лиги из списков
    with open('2.txt', 'r', encoding='utf-8') as f:
        m = [line.strip() for line in f if line.strip()]

    with open('3.txt', 'r', encoding='utf-8') as f:
        m2 = [line.strip() for line in f if line.strip()]
    
    #m = ['der-eto-kazincbarcika']
    #m2 = ['dyor-kazincbarcika']
    sl_sopostavleniy = get_sopostavlenie(m, m2, 87)


    for k,v in sl_sopostavleniy.items():
        #print([k,v])
        print(f"""s = s.replace('{v}','{k}')""")

    filename = 'sl_chemps_zamen.json'
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(sl_sopostavleniy, f, ensure_ascii=False, indent=2)
            
    



