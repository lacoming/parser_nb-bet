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
    ws1.set_column('AD:AD', 50) # ссылка
    
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
        
    
    
    ws1.add_table(f'A4:AD{len(dannies)+6}', {'data':dannies,
                                            'style': 'Table Style Medium 3',
                                            'name': 'SalesData'
                                            })
    #ws1.freeze_panes('J6')
    
    wb.close()
    
def zapis_v_exel_new_soccer(dannies, fname):
    #print(data_vigruzki)
    try:
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
        ws1.set_column('AB:AB', 50) # ссылка
        
        
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
        
        ws1.merge_range('L1:Q1', 'КФ', merge_format)
        ws1.merge_range('L2:M2', 'Команда 1', merge_format)
        ws1.write('L3', 'нач', merge_format)
        ws1.write('M3', 'кон', merge_format)
        ws1.merge_range('N2:O2', 'ничья', merge_format)
        ws1.write('N3', 'нач', merge_format)
        ws1.write('O3', 'кон', merge_format)
        ws1.merge_range('P2:Q2', 'Команда 2', merge_format)
        ws1.write('P3', 'нач', merge_format)
        ws1.write('Q3', 'кон', merge_format)
        
        ws1.merge_range('R1:U1', 'Точный счет', merge_format)
        ws1.merge_range('R2:R3', 'Команда 1', merge_format)
        ws1.merge_range('S2:S3', 'Команда 2', merge_format)
        ws1.merge_range('T2:T3', 'Кф нач', merge_format)
        ws1.merge_range('U2:U3', 'Кф кон', merge_format)
        
        ws1.merge_range('V1:X1', 'МП', merge_format)
        ws1.merge_range('V2:V3', 'Вид', merge_format)
        ws1.merge_range('W2:W3', 'Кф нач', merge_format)
        ws1.merge_range('X2:X3', 'Кф кон', merge_format)
        
        ws1.merge_range('Y1:AA1', 'ПП', merge_format)
        ws1.merge_range('Y2:Y3', 'Вид', merge_format)
        ws1.merge_range('Z2:Z3', 'Кф нач', merge_format)
        ws1.merge_range('AA2:AA3', 'Кф кон', merge_format)
            
        
        
        ws1.add_table(f'A4:AB{len(dannies)+6}', {'data':dannies,
                                                'style': 'Table Style Medium 3',
                                                'name': 'SalesData'
                                                })
        #ws1.freeze_panes('J6')
        
        wb.close()
        return True
    except:
        return None



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
                        sc1_1, sc2_1 = get_score(match,'11','19')
                        sc1_2, sc2_2 = get_score(match,'26','27')
                        sc1_3, sc2_3 = get_score(match,'28','29')
                        
                        try:
                            stp1, stpx, stp2 = get_kef_1x2(match['6'])
                        except:
                            stp1, stpx, stp2 = '','',''
                        
                        try:
                            ep1, epx, ep2 = get_kef_1x2(match['5'])
                        except:
                            ep1, epx, ep2 = '','',''
                        
                        ts1, ts2 = get_score(match,'46','47')
                        # ПС:
                        ps_name, ps_start_k, ps_end_k = get_kef(match['50'])
                        # МП:
                        mp_name, mp_start_k, mp_end_k = get_kef(match['48'])
                        # ПП:
                        pp_name, pp_start_k, pp_end_k = get_kef(match['49'])
                        
                        link = match['3']
                        
                        if selected_sport == 'Хоккей':
                            sp_matches.append([d_m,t_m,country,home,away,
                                               score1,score2,sc1_1,sc2_1,sc1_2,sc2_2,sc1_3,sc2_3,
                                               stp1,ep1, stpx, epx, stp2, ep2,
                                               ts1, ts2, ps_start_k, ps_end_k,
                                               mp_name, mp_start_k, mp_end_k,
                                               pp_name, pp_start_k, pp_end_k, link])
                        
                        if selected_sport == 'Футбол':
                            sp_matches.append([d_m,t_m,country,home,away,
                                               score1,score2,sc1_1,sc2_1,sc1_2,sc2_2,
                                               stp1,ep1, stpx, epx, stp2, ep2,
                                               ts1, ts2, ps_start_k, ps_end_k,
                                               mp_name, mp_start_k, mp_end_k,
                                               pp_name, pp_start_k, pp_end_k, link])
                        
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


def nbbet_start_parser(selected_sport, d1, d2):       
    sp_matches = []
    sp_dates = generate_date_range(d1,d2)
    for t in sp_dates:        
        sp_matches = get_matches(decode_date_parse(t), sp_matches, selected_sport)
        print(f"Получено игр: {len(sp_matches)} Получаю игры за {t}")
        
    if len(sp_matches) != 0:
        return sp_matches
        
    else:
        return None
