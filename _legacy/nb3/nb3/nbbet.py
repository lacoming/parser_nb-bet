import json
import time
import requests
import xlsxwriter

from threading import Thread
from datetime import datetime, timedelta

from tkinter import *
from tkinter import ttk

from decode_key import decode_odds_key


# Функция для загрузки словаря (один раз при запуске)
def load_odds_keys_from_file():
    """Загружает словарь ключей из файла"""
    # Чтение из файла
    with open('sl_keys.json', 'r', encoding='utf-8') as file:
        loaded_data = json.load(file)
        
    return {int(k): v for k, v in loaded_data.items()}

ODDS_KEYS = load_odds_keys_from_file()


def zapis_v_exel_new_hockey(dannies, fname):
    #print(data_vigruzki)
    wb = xlsxwriter.Workbook(f"{fname}.xlsx", {'strings_to_urls': False})    
    ws1 = wb.add_worksheet('ИГРЫ')
    
        # Устанавливаем ширину колонок
    ws1.set_column('A:A', 12)   # Дата
    ws1.set_column('B:B', 10)   # Время
    ws1.set_column('C:C', 20)   # Лига
    ws1.set_column('D:D', 25)   # Команда 1
    ws1.set_column('E:E', 25)   # Команда 2
    ws1.set_column('F:F', 10)   # Общий счет - Команда 1
    ws1.set_column('G:G', 10)   # Общий счет - Команда 2
    ws1.set_column('H:H', 10)   # Счет 1 - Команда 1
    ws1.set_column('I:I', 10)   # Счет 1 - Команда 2
    ws1.set_column('J:J', 10)   # Счет 2 - Команда 1
    ws1.set_column('K:K', 10)   # Счет 2 - Команда 2
    ws1.set_column('L:L', 10)   # Счет 3 - Команда 1
    ws1.set_column('M:M', 10)   # Счет 3 - Команда 2
    ws1.set_column('N:N', 8)    # КФ - Команда 1 нач
    ws1.set_column('O:O', 8)    # КФ - Команда 1 кон
    ws1.set_column('P:P', 8)    # КФ - ничья нач
    ws1.set_column('Q:Q', 8)    # КФ - ничья кон
    ws1.set_column('R:R', 8)    # КФ - Команда 2 нач
    ws1.set_column('S:S', 8)    # КФ - Команда 2 кон
    ws1.set_column('T:T', 10)   # Точный счет - Команда 1
    ws1.set_column('U:U', 10)   # Точный счет - Команда 2
    ws1.set_column('V:V', 10)   # Точный счет - Кф нач
    ws1.set_column('W:W', 10)   # Точный счет - Кф кон
    ws1.set_column('X:X', 10)   # МП - Вид
    ws1.set_column('Y:Y', 10)   # МП - Кф нач
    ws1.set_column('Z:Z', 10)   # МП - Кф кон
    ws1.set_column('AA:AA', 10) # ПП - Вид
    ws1.set_column('AB:AB', 10) # ПП - Кф нач
    ws1.set_column('AC:AC', 10) # ПП - Кф кон
    
    style1 = wb.add_format({'bold': True,
                            'font_name':'Times New Roman',
                            'font_size':11,
                            'align': 'center',
                            'valign': 'vcenter',
                            'text_wrap':True,
                            'border':2})
    
    # Объединяем ячейки A1, A2, A3
    merge_format = wb.add_format({
        'bold': True,
        'font_name':'Times New Roman',
        'font_size':11,
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap':True,
        'border':2
        })    
    
    ws1.merge_range('A1:A3', 'Дата', merge_format)
    ws1.merge_range('B1:B3', 'Время', merge_format)
    ws1.merge_range('C1:C3', 'Лига', merge_format)
    ws1.merge_range('D1:D3', 'Команда 1', merge_format)
    ws1.merge_range('E1:E3', 'Команда 2', merge_format)
    
    ws1.merge_range('F1:G1', 'Общий счет', merge_format)
    ws1.merge_range('F2:F3', 'Команда 1', merge_format)
    ws1.merge_range('G2:G3', 'Команда 2', merge_format)
    
    ws1.merge_range('H1:I1', 'Счет 1', merge_format)
    ws1.merge_range('H2:H3', 'Команда 1', merge_format)
    ws1.merge_range('I2:I3', 'Команда 2', merge_format)
    
    ws1.merge_range('J1:K1', 'Счет 2', merge_format)
    ws1.merge_range('J2:J3', 'Команда 1', merge_format)
    ws1.merge_range('K2:K3', 'Команда 2', merge_format)
    
    ws1.merge_range('L1:M1', 'Счет 3', merge_format)
    ws1.merge_range('L2:L3', 'Команда 1', merge_format)
    ws1.merge_range('M2:M3', 'Команда 2', merge_format)
    
    ws1.merge_range('N1:S1', 'КФ', merge_format)
    ws1.merge_range('N2:O2', 'Команда 1', merge_format)
    ws1.write('N3', 'нач', merge_format)
    ws1.write('O3', 'кон', merge_format)
    ws1.merge_range('P2:Q2', 'ничья', merge_format)
    ws1.write('P3', 'нач', merge_format)
    ws1.write('Q3', 'кон', merge_format)
    ws1.merge_range('R2:S2', 'Команда 2', merge_format)
    ws1.write('R3', 'нач', merge_format)
    ws1.write('S3', 'кон', merge_format)
    
    ws1.merge_range('T1:W1', 'Точный счет', merge_format)
    ws1.merge_range('T2:T3', 'Команда 1', merge_format)
    ws1.merge_range('U2:U3', 'Команда 2', merge_format)
    ws1.merge_range('V2:V3', 'Кф нач', merge_format)
    ws1.merge_range('W2:W3', 'Кф кон', merge_format)
    
    ws1.merge_range('X1:Z1', 'МП', merge_format)
    ws1.merge_range('X2:X3', 'Вид', merge_format)
    ws1.merge_range('Y2:Y3', 'Кф нач', merge_format)
    ws1.merge_range('Z2:Z3', 'Кф кон', merge_format)
    
    ws1.merge_range('AA1:AC1', 'ПП', merge_format)
    ws1.merge_range('AA2:AA3', 'Вид', merge_format)
    ws1.merge_range('AB2:AB3', 'Кф нач', merge_format)
    ws1.merge_range('AC2:AC3', 'Кф кон', merge_format)
        
    
    
    ws1.add_table(f'A4:AC{len(dannies)+6}', {'data':dannies,
                                            'style': 'Table Style Medium 3',
                                            'name': 'SalesData'
                                            })
    #ws1.freeze_panes('J6')
    
    wb.close()
    
def zapis_v_exel_new_soccer(dannies, fname):
    #print(data_vigruzki)
    wb = xlsxwriter.Workbook(f"{fname}.xlsx", {'strings_to_urls': False})    
    ws1 = wb.add_worksheet('ИГРЫ')
    
        # Устанавливаем ширину колонок
    ws1.set_column('A:A', 12)   # Дата
    ws1.set_column('B:B', 10)   # Время
    ws1.set_column('C:C', 20)   # Лига
    ws1.set_column('D:D', 25)   # Команда 1
    ws1.set_column('E:E', 25)   # Команда 2
    ws1.set_column('F:F', 10)   # Общий счет - Команда 1
    ws1.set_column('G:G', 10)   # Общий счет - Команда 2
    ws1.set_column('H:H', 10)   # Счет 1 - Команда 1
    ws1.set_column('I:I', 10)   # Счет 1 - Команда 2
    ws1.set_column('J:J', 10)   # Счет 2 - Команда 1
    ws1.set_column('K:K', 10)   # Счет 2 - Команда 2
    ws1.set_column('N:N', 8)    # КФ - Команда 1 нач
    ws1.set_column('O:O', 8)    # КФ - Команда 1 кон
    ws1.set_column('P:P', 8)    # КФ - ничья нач
    ws1.set_column('Q:Q', 8)    # КФ - ничья кон
    ws1.set_column('R:R', 8)    # КФ - Команда 2 нач
    ws1.set_column('S:S', 8)    # КФ - Команда 2 кон
    ws1.set_column('T:T', 10)   # Точный счет - Команда 1
    ws1.set_column('U:U', 10)   # Точный счет - Команда 2
    ws1.set_column('V:V', 10)   # Точный счет - Кф нач
    ws1.set_column('W:W', 10)   # Точный счет - Кф кон
    ws1.set_column('X:X', 10)   # МП - Вид
    ws1.set_column('Y:Y', 10)   # МП - Кф нач
    ws1.set_column('Z:Z', 10)   # МП - Кф кон
    ws1.set_column('AA:AA', 10) # ПП - Вид
    
    
    style1 = wb.add_format({'bold': True,
                            'font_name':'Times New Roman',
                            'font_size':11,
                            'align': 'center',
                            'valign': 'vcenter',
                            'text_wrap':True,
                            'border':2})
    
    # Объединяем ячейки A1, A2, A3
    merge_format = wb.add_format({
        'bold': True,
        'font_name':'Times New Roman',
        'font_size':11,
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap':True,
        'border':2
        })    
    
    ws1.merge_range('A1:A3', 'Дата', merge_format)
    ws1.merge_range('B1:B3', 'Время', merge_format)
    ws1.merge_range('C1:C3', 'Лига', merge_format)
    ws1.merge_range('D1:D3', 'Команда 1', merge_format)
    ws1.merge_range('E1:E3', 'Команда 2', merge_format)
    
    ws1.merge_range('F1:I1', 'Общий счет', merge_format)
    ws1.merge_range('F2:F3', 'Команда 1', merge_format)
    ws1.merge_range('G2:G3', 'Команда 2', merge_format)    
    ws1.merge_range('H2:H3', 'T', merge_format)
    ws1.merge_range('I2:I3', 'P', merge_format)
    
    ws1.merge_range('J1:M1', 'Счет 1', merge_format)
    ws1.merge_range('J2:J3', 'Команда 1', merge_format)
    ws1.merge_range('K2:K3', 'Команда 2', merge_format)
    ws1.merge_range('L2:L3', 'T', merge_format)
    ws1.merge_range('M2:M3', 'P', merge_format)
    
    ws1.merge_range('N1:Q1', 'Счет 2', merge_format)
    ws1.merge_range('N2:N3', 'Команда 1', merge_format)
    ws1.merge_range('O2:O3', 'Команда 2', merge_format)
    ws1.merge_range('P2:P3', 'T', merge_format)
    ws1.merge_range('Q2:Q3', 'P', merge_format)
    
    ws1.merge_range('R1:Y1', 'КФ', merge_format)
    ws1.merge_range('R2:S2', 'Команда 1', merge_format)
    ws1.write('R3', 'нач', merge_format)
    ws1.write('S3', 'кон', merge_format)
    ws1.merge_range('T2:T3', 'ДвижКф1', merge_format)
    
    ws1.merge_range('U2:V2', 'ничья', merge_format)
    ws1.write('U3', 'нач', merge_format)
    ws1.write('V3', 'кон', merge_format)
    ws1.merge_range('W2:X2', 'Команда 2', merge_format)
    ws1.write('W3', 'нач', merge_format)
    ws1.write('X3', 'кон', merge_format)
    ws1.merge_range('Y2:Y3', 'ДвижКф2', merge_format)
    
    ws1.merge_range('Z1:AC1', 'Точный счет', merge_format)
    ws1.merge_range('Z2:Z3', 'Команда 1', merge_format)
    ws1.merge_range('AA2:AA3', 'Команда 2', merge_format)
    ws1.merge_range('AB2:AB3', 'Кф нач', merge_format)
    ws1.merge_range('AC2:AC3', 'Кф кон', merge_format)
    
    ws1.merge_range('AD1:AG1', 'МП', merge_format)
    ws1.merge_range('AD2:AD3', 'Вид', merge_format)
    ws1.merge_range('AE2:AE3', 'Кф нач', merge_format)
    ws1.merge_range('AF2:AF3', 'Кф кон', merge_format)
    ws1.merge_range('AG2:AG3', 'КфОбр', merge_format)    
    
    ws1.add_table(f'A4:AG{len(dannies)+6}', {'data':dannies,
                                            'style': 'Table Style Medium 3',
                                            'name': 'SalesData'
                                            })
    #ws1.freeze_panes('J6')
    
    wb.close()



def get_d(d,nom):
    p1 = ''
    try:
        p1 = d[nom]
        if p1 == None:
            p1 = ''
    except:
        pass
    
    return p1

def get_score(dan, nom1, nom2):
    d1 = ''
    d2 = ''
    try:
        d1 = get_d(dan,nom1)
        d2 = get_d(dan,nom2)     
        return d1, d2                    
    except:
        return '',''

def get_kef(d):    
    if d != None:
        pname = decode_odds_key(d['1'], ODDS_KEYS)
        start_k = get_d(d,'3')        
        end_k = get_d(d,'2')    
        return pname, start_k, end_k
    else:
        return '', '', ''
    
'''
d = {'1': 159, '2': 1.74, '3': 1.88}
print(get_kef(d))
input()
'''

def get_kef_1x2(d):
    if d != None:
        p1 = get_d(d,'1')
        px = get_d(d,'3')
        p2 = get_d(d,'2')
        return p1,px,p2
    else:
        return '','',''
    

def get_matches(dt, sp_matches, selected_sport):    
    response = None
    if selected_sport == 'Хоккей':
        url = f'https://app.nb-bet.com/v1/hockey/math-analysis/page?timestamp={dt}'
    
    if selected_sport == 'Футбол':
        url = f'https://app.nb-bet.com/v1/soccer/math-analysis/page?timestamp={dt}'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'ru',
        'Accept-Encoding': 'gzip, deflate',
        #'window': '219080976602',
        'Origin': 'https://nb-bet.com',
        'Connection': 'keep-alive',
        'Referer': 'https://nb-bet.com/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        #'If-None-Match': 'W/"1e0ed-jVFFtEFAhaBqmVRrbbcyioxPRpc"',
        }
    
    for i in range(3):
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                break 
        except:
            pass
    
    if response:
        try:
            dannie_jsons = response.json()['data']            
            for dannie in dannie_jsons['leagues']:            
                country = f"{dannie['1']}. {dannie['3']}"
                matches = dannie['4']
                for match in matches:
                    try:
                        d_ms = datetime.fromtimestamp(int(f"{match['4']}"[:-3])).strftime('%d.%m.%Y %H.%M')
                        d_m = d_ms.split(' ')[0]
                        t_m = d_ms.split(' ')[1]
                        home = match['7']
                        away = match['15']                
                        score1,score2 = get_score(match,'10','18')
                        
                        try:
                            sum_sc = int(score1)+int(score2)
                            razn_sc = int(score1)-int(score2)
                        except:
                            sum_sc = ''
                            razn_sc = ''
                        
                        sc1_1, sc2_1 = get_score(match,'11','19')
                        
                        try:
                            sum_sc1 = int(sc1_1)+int(sc2_1)
                            razn_sc1 = int(sc1_1)-int(sc2_1)
                        except:
                            sum_sc1 = ''
                            razn_sc1 = ''
                        
                        sc1_2, sc2_2 = get_score(match,'26','27')
                        
                        try:
                            sum_sc2 = int(sc1_2)+int(sc2_2)
                            razn_sc2 = int(sc1_2)-int(sc2_2)
                        except:
                            sum_sc2 = ''
                            razn_sc2 = ''
                        
                        sc1_3, sc2_3 = get_score(match,'28','29')
                        
                        try:
                            stp1, stpx, stp2 = get_kef_1x2(match['6'])
                        except:
                            stp1, stpx, stp2 = '','',''
                        
                        try:
                            ep1, epx, ep2 = get_kef_1x2(match['5'])
                        except:
                            ep1, epx, ep2 = '','',''
                        
                        if ep1 == '' or ep2 == '':
                            continue
                        
                        
                        # =(Кфн-Кфк)/Кфн
                        dvizh1 = ''
                        try:
                            dvizh1 = round((float(stp1)-float(ep1))/float(stp1), 2)                           
                        except:
                            pass
                        
                        dvizh2 = ''
                        try:
                            dvizh2 = round((float(stp2)-float(ep2))/float(stp2), 2)                           
                        except:
                            pass
                        
                        
                        ts1, ts2 = get_score(match,'46','47')
                        # ПС:
                        ps_name, ps_start_k, ps_end_k = get_kef(match['50'])
                        # МП:
                        mp_name, mp_start_k, mp_end_k = get_kef(match['48'])
                        # ПП:
                        pp_name, pp_start_k, pp_end_k = get_kef(match['49'])
                        
                        
                        # =1/(1,065-(1/КфМП)
                        kefobr = ''
                        try:
                            kefobr = round(1/(1.065-(1/float(mp_end_k))), 2)                           
                        except:
                            pass
                        
                        
                        if selected_sport == 'Хоккей':
                            sp_matches.append([d_m,t_m,country,home,away,
                                               score1,score2,sc1_1,sc2_1,sc1_2,sc2_2,sc1_3,sc2_3,
                                               stp1,ep1, stpx, epx, stp2, ep2,
                                               ts1, ts2, ps_start_k, ps_end_k,
                                               mp_name, mp_start_k, mp_end_k,
                                               pp_name, pp_start_k, pp_end_k])
                        
                        if selected_sport == 'Футбол':
                            sp_matches.append([d_m,t_m,country,home,away,
                                               score1,score2,sum_sc,razn_sc,sc1_1,sc2_1,sum_sc1,razn_sc1,
                                               sc1_2,sc2_2,sum_sc2,razn_sc2,
                                               stp1,ep1,dvizh1, stpx, epx, stp2, ep2,dvizh2,
                                               ts1, ts2, ps_start_k, ps_end_k,
                                               mp_name, mp_start_k, mp_end_k,kefobr])
                        
                    except:                        
                        pass
        except:
            pass
                
    return sp_matches


def decode_date_parse(t):
    const_t = '23:59:59'
    return f"{int(datetime.strptime(f'{t} {const_t}', '%d.%m.%Y %H:%M:%S').timestamp())}999"


def generate_date_range(start_date_str, end_date_str, date_format="%d.%m.%Y"):
    """
    Формирует список дат между двумя заданными датами
    
    Args:
        start_date_str (str): Начальная дата в формате строки
        end_date_str (str): Конечная дата в формате строки
        date_format (str): Формат даты (по умолчанию ДД.ММ.ГГГГ)
    
    Returns:
        list: Список строк с датами в заданном формате
    """
    try:
        # Преобразуем строки в объекты datetime
        start_date = datetime.strptime(start_date_str, date_format)
        end_date = datetime.strptime(end_date_str, date_format)
        
        # Проверяем, что начальная дата не больше конечной
        if start_date > end_date:
            raise ValueError("Начальная дата не может быть больше конечной")
        
        # Генерируем список дат
        date_list = []
        current_date = start_date
        
        while current_date <= end_date:
            date_list.append(current_date.strftime(date_format))
            current_date += timedelta(days=1)
        
        return date_list
        
    except ValueError as e:
        print(f"Ошибка: {e}")
        return []


# Функция для получения выбранного вида спорта
def get_selected_sport():
    if hockey_var.get():
        return "Хоккей"
    elif football_var.get():
        return "Футбол"
    else:
        return None


def start_parser():
    selected_sport = get_selected_sport()
    if not selected_sport:
        label_info['text'] = "Выберите вид спорта!"
        return
    
    d1 = d1_entry.get()
    d2 = d2_entry.get()
    
    sp_matches = []
    sp_dates = generate_date_range(d1,d2)
    for t in sp_dates:
        label_info['text'] = f"Получено игр: {len(sp_matches)} Получаю игры за {t}"
        sp_matches = get_matches(decode_date_parse(t), sp_matches, selected_sport)
        time.sleep(2)
        
    if len(sp_matches) != 0:
        label_info['text'] = f"Получено игр: {len(sp_matches)}"        
        if selected_sport == 'Хоккей':
            fname = f"выгрузка/Хоккей_c_{d1.replace('.','_')}_по_{d2.replace('.','_')}"
            zapis_v_exel_new_hockey(sp_matches, fname)
    
        if selected_sport == 'Футбол':
            fname = f"выгрузка/Футбол_c_{d1.replace('.','_')}_по_{d2.replace('.','_')}"
            zapis_v_exel_new_soccer(sp_matches, fname)        
        
        label_info['text'] = f"Данные записаны в {fname}"
    else:
        label_info['text'] = f"Данные не найдены"
        
        
        

# О разработчике
def about():
    root_about = Tk()
    root_about.title("О разработчике")
    #root.geometry("400x450")
    bg_color = '#48a870'
    root_about['bg']=bg_color
    #root.resizable(width=False, height=False)
    
    f_top0 = Frame(root_about, bg=bg_color)
    f_top0.pack(side=TOP, padx=5, pady=5)
    text = Text(f_top0, width=65, height=10, wrap=WORD)
    text.pack(side=LEFT, padx=10, pady=10)
    
    sp_text_mess = ['Не пишите об произведенной оплате в кворке, могут забанить!!!\n\n',
                    'Оплата сколько не жалко:\n',
                    '- карта СБЕРБАНКА по номеру телефона +79528665090 \n("Дмитрий Сергеевич Ф")\n',                    
                    'Мой WhatsApp +79528665090']
    
    for text_mess in sp_text_mess:
        text.insert(END, text_mess)
    
    root_about.mainloop()




d_now = datetime.now().strftime('%d.%m.%Y')


#=================== создание окна программы ==========================================
root = Tk()
root.title("Хоккей ПАРСЕР ver.1")
bg_color = '#8793ad'
fg_color = '#33333b'
root['bg']=bg_color


# Переменные для чекбоксов
hockey_var = BooleanVar(value=True)  # Хоккей выбран по умолчанию
football_var = BooleanVar(value=False)

# Функции для взаимоисключающего выбора
def hockey_selected():
    if hockey_var.get():
        football_var.set(False)

def football_selected():
    if football_var.get():
        hockey_var.set(False)


# ======================================================================
f_top0 = Frame(root, bg=bg_color)
f_top0.pack(side=TOP, pady=2)
labe_f_top0 = Label(f_top0, text="Введите дату для сбора:  ", font="Arial 12 bold", justify=LEFT, bg=bg_color, fg=fg_color)
labe_f_top0.pack(side=TOP,padx=5)

f_top01 = Frame(root, bg=bg_color)
f_top01.pack(side=TOP, pady=2)
labe_f_top01 = Label(f_top01, text="C:  ", font="Arial 12 bold", width=5, justify=LEFT, bg=bg_color, fg=fg_color)
labe_f_top01.pack(side=LEFT,padx=5)
d1_entry = Entry(f_top01, width=10, justify=CENTER, font="Arial 12")
d1_entry.pack(side=LEFT, padx=5, pady=2)
d1_entry.insert(0, d_now)

f_top02 = Frame(root, bg=bg_color)
f_top02.pack(side=TOP, pady=2)
labe_f_top01 = Label(f_top02, text="ПО:  ", font="Arial 12 bold", width=5, justify=LEFT, bg=bg_color, fg=fg_color)
labe_f_top01.pack(side=LEFT,padx=5)
d2_entry = Entry(f_top02, width=10, justify=CENTER, font="Arial 12")
d2_entry.pack(side=LEFT, padx=5, pady=2)
d2_entry.insert(0, d_now)
# =================== ЧЕКБОКСЫ ДЛЯ ВЫБОРА ВИДА СПОРТА ================================
f_top_sport = Frame(root, bg=bg_color)
f_top_sport.pack(side=TOP, pady=10)

# Чекбокс для Хоккея
hockey_check = Checkbutton(f_top_sport, text="Хоккей", font="Arial 12 bold", 
                          variable=hockey_var, bg=bg_color, fg=fg_color,
                          selectcolor=bg_color, activebackground=bg_color,
                          activeforeground=fg_color, command=hockey_selected)
hockey_check.pack(side=LEFT, padx=20)

# Чекбокс для Футбола
football_check = Checkbutton(f_top_sport, text="Футбол", font="Arial 12 bold", 
                           variable=football_var, bg=bg_color, fg=fg_color,
                           selectcolor=bg_color, activebackground=bg_color,
                           activeforeground=fg_color, command=football_selected)
football_check.pack(side=LEFT, padx=20)

# ======================================================================
f_top10 = Frame(root, bg=bg_color)
f_top10.pack(side=TOP, padx=10, pady=10)
btn = Button(f_top10, text="СТАРТ", font="Arial 16 bold", width=25, fg=fg_color,
             pady=0, padx=0, justify=CENTER, background='#e3b398',
             activebackground='#0d6acd', command=lambda: Thread(target = start_parser).start())
btn.pack(side=LEFT, padx=10)

# ======================================================================
f_top3 = Frame(root, bg=bg_color)
f_top3.pack(side=TOP)
label_info = Label(f_top3, text="Введите дату и нажмите СТАРТ", font="Arial 12", width=70, justify=LEFT, bg=bg_color, fg=fg_color)
label_info.pack(side=TOP, padx=10, pady=10)

f_top_3 = Frame(root, bg=bg_color)
f_top_3.pack(side=TOP, padx=10, pady=5)
f_top4 = Frame(f_top_3, bg=bg_color)
f_top4.pack(side=TOP, padx=10, pady=10)
btn = Button(f_top4, text="Нажми чтобы не забыть!", font="Arial 10",
             pady=0, padx=0, justify=CENTER, background='#d3e7fd',
             activebackground='#0d6acd',cursor="hand2", command=lambda: Thread(target = about).start())
btn.pack(side=LEFT, padx=10)

root.mainloop()