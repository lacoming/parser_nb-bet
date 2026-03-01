import os
import time
import json
from datetime import datetime, timedelta
import requests

from nbbet import nbbet_start_parser, zapis_v_exel_new_soccer
from kushvsporte import get_all_leagas, get_matches_leagas, get_all_variants_po_stavkam, start_avtostavka
from read_xlsx_settings import find_excel_files, read_excel_with_openpyxl
from sopostavlenie import get_sopostavlenie



SP_BED_MATCHES = []
sl_matches_stavka_do_igri = {} # Словарь игр, которые проставляем до игры

sl_count_bed_response = {} # словарь неудачных попыток отправки игр
COUNT_LIMIT_STAVKA = 0



def table_message(fname):
    # Отправляем таблицу с играми в ТГ
    fname = f"{fname}.xlsx"
    # Проверяем существование файла
    if not os.path.exists(fname):
        print(f"Файл не найден: {fname}")
        return None
    
    fl_otpr = False
    
    # Считываем настройки
    with open('settings.json', 'r', encoding='utf-8') as file:
        settings = json.load(file)
        
    TOKEN = settings['TOKEN_API']
    CHAT_IDS = settings['CHAT_IDS']
    
    try:
        url = f'https://api.telegram.org/bot{TOKEN}/sendDocument'
        filename = os.path.basename(fname)
        
        for CHAT_ID in CHAT_IDS:
            # Открываем файл заново для каждого чата
            with open(fname, 'rb') as file:
                files = {'document': (filename, file)}
                data = {'chat_id': CHAT_ID}
                
                for i in range(3):
                    try:
                        response = requests.post(url, data=data, files=files)
                        response_json = response.json()
                        
                        if response.status_code == 200:
                            print(f'Таблица отправлена в чат {CHAT_ID}')
                            fl_otpr = True
                            break
                        else:
                            # Если API вернуло ошибку
                            error_msg = response_json.get('description', 'Неизвестная ошибка')
                            print(f'Ошибка отправки в чат {CHAT_ID}: {error_msg}')
                            
                    except Exception as e:
                        vremya_oshibki = datetime.now().strftime("%d_%m_%Y %H:%M:%S")
                        print(f'[{vremya_oshibki}]: Ошибка отправки сообщения в чат {CHAT_ID}: {e}')
                        time.sleep(1.3)
                        continue
                    
    except Exception as ex:
        print(f'Ошибка отправки таблицы: {ex}')
        
    return fl_otpr


def write_new_chemps(fname, sp_ch):
    # функция пишет новые чемпионаты в файл
    # Если нашлись лиги, то пытаемся записать новые в список
    if len(sp_ch) != 0:
        sp_chemps = []
        
        # проверяем имеется ли файл fname
        if os.path.exists(fname):
            pass
        else:
            with open(fname, 'w', encoding='utf-8') as f:
                pass
            
        try:
            # считываем чемпионаты с файла
            with open(fname, 'r', encoding='utf-8') as f:        
                for line in f.readlines():
                    line = line.strip()
                    if line != '':
                        if line not in sp_chemps:
                            sp_chemps.append(line)
        
            count_new_ch = None
            for l in sp_ch:
                if l not in sp_chemps:
                    sp_chemps.append(l)
                    count_new_ch = True
            
            if count_new_ch:
                # Пишем обновленный список
                with open(fname, 'w', encoding='utf-8') as f:
                    sp_chemps.sort()
                    for l in sp_chemps:
                        f.write(f"{l}\n")            
        except:
            pass


def get_settings():
    # Получаем настройки стратегий
    settings = {}
    sp_chemps_strategy = []
    sp_stavok = []
    
    sp_files = find_excel_files()
    for file_path in sp_files:
        settings = read_excel_with_openpyxl(file_path)

    print('Настройки:')
    print('*'*30)
    for k,v in settings.items():
        print(f'Стратегия {k}')
        print(v)
        sp_chemps_strategy = list(set(sp_chemps_strategy + v['страны']))
        if v['ставка_НБ'] not in sp_stavok:
            sp_stavok.append(v['ставка_НБ'])
    
    #print(sp_chemps_strategy)
    #for s in sp_chemps_strategy:
    #    print(s)
    #print(sp_stavok)
    #input()
    return settings, sp_chemps_strategy, sp_stavok


def get_nbbet_games(sp_otobrs_matches_nbbet, selected_sport, d_start, d_end, sp_stavok, sp_chemps_strategy_nbbet):
    # Получаем игры с сайта https://nbbet
    
    sp_countrys = []
    sp_ch = []
    d_now = datetime.now()
    sp_nbbet = nbbet_start_parser(selected_sport, d_start, d_end)
    for m in sp_nbbet:        
        sp_ch.append(m[2])
        if datetime.strptime(f"{m[0]} {m[1]}","%d.%m.%Y %H.%M")<d_now:
            continue        
        
        #if m[21] in sp_stavok:
        #    print(m)
        #if m[2] not in sp_countrys:
        #    sp_countrys.append(m[2])
        if m[2] in sp_chemps_strategy_nbbet and m[21] in sp_stavok:
            print('отобрано', m)
            sp_otobrs_matches_nbbet.append(m)
            if m[2] not in sp_countrys:
                sp_countrys.append(m[2])
    
    # Пишем лиги в файл
    write_new_chemps('nbbet_chemps.txt', sp_ch)
    
    return sp_countrys, sp_otobrs_matches_nbbet


def get_dict_otobrs_matches_nbbet(sp_otobrs_matches_nbbet, settings, d_start, d_end):
    # Формируем словарь с отобранными играми
    sp_zap_nbbet = []
    sl_otobrs_matches_nbbet = {}
    for m in sp_otobrs_matches_nbbet:        
        # Проверяем выполнения условий по названию ставки и лиге
        for k,v in settings.items():
            if m[2] in v['страны'] and m[21].strip().lower() == v['ставка_НБ'].strip().lower():        
                link_m = '-'.join(m[-1].split('-')[1:]).split('-prognoz-na-match')[0]
                sl_otobrs_matches_nbbet[link_m] = m
                sp_zap_nbbet.append(m)
                break
    
    for i in range(3):
        # Пишем игры в таблицу
        fname = f'выгрузка/игры_nbbet_{d_start.replace(".","_")}_{d_end.replace(".","_")}'
        if zapis_v_exel_new_soccer(sp_zap_nbbet, fname) == True:
            time.sleep(2)
            # Отправляем таблицу в ТГ
            table_message(fname)    
            break
        time.sleep(1)

    return sl_otobrs_matches_nbbet


def get_find_countries_kushvsporte(sl_country, sp_countrys, param_ratio):
    # Оставляем только найденные страны в списке https://kushvsporte.ru    
    sp_countrys_kushvsporte = []
    for k,v in sl_country.items():
        if v not in sp_countrys_kushvsporte:
            sp_countrys_kushvsporte.append(v)            
            #print(v)
            
    # Нужно отсеять только те лиги, которых нет в списке стратегий
    # Проводим соответствие
    
    sl_chemps_zamen = {}
    # Считываем словарь замен
    try:
        with open('sl_chemps_zamen.json', 'r', encoding='utf-8') as file:
            sl_chemps_zamen = json.load(file)
    except Exception as ex:
        print(f'Ошибка в словаре замен чемпионатов: {ex}')
    
    sp_sops = []
    sl_sopostavleniy = get_sopostavlenie(sp_countrys, sp_countrys_kushvsporte, param_ratio, sl_chemps_zamen)    
    for k,v in sl_sopostavleniy.items():
        #print([k,v])
        sp_sops.append(v)
    
    # Оставляем только найденные страны в списке https://kushvsporte.ru
    sl_country_copy = sl_country.copy()
    for k,v in sl_country_copy.items():
        if v not in sp_sops:
            sl_country.pop(k)
    
    # Пишем лиги в файл
    write_new_chemps('kushvsporte_chemps.txt', sp_countrys_kushvsporte)
    
    return sl_country, sl_sopostavleniy

def get_matches_kushvsporte(sl_country, sl_otobrs_matches_nbbet, sl_sopostavleniy, day, csrf_token, PHPSESSID, _csrf):
    # Нужно отсеять только те лиги, которые есть в списке стратегий
    # Получаем все игры с сайта https://kushvsporte.ru
    sl_matches_cappers = {} # Финальный словарь игр для ставок
    
    print('Получаем все игры с сайта https://kushvsporte.ru')
    x1 = 1
    sp_all_matches_kushvsporte = [] # Список игр kushvsporte
    for k,v in sl_country.items():
        print(k,v)
        sp_matches = get_matches_leagas(k, day, csrf_token, PHPSESSID, _csrf, v)
        sp_all_matches_kushvsporte+=sp_matches
        print(f'{x1}/{len(sl_country)}  Игр {len(sp_all_matches_kushvsporte)}')
        time.sleep(1.5)
        x1+=1

    print(f'Всего игр {len(sp_all_matches_kushvsporte)}')
    
    sl_chemps_zamen = {}
    
    # Находим игры для ставки
    for m in sp_all_matches_kushvsporte:
        print(m)
        link_m = '-'.join(m[-1].split('-')[1:]).split('-prognoz-na-match')[0]
        if link_m in sl_otobrs_matches_nbbet:
            print('Нашел', sl_otobrs_matches_nbbet[link_m])
            sl_matches_cappers[link_m] = [sl_otobrs_matches_nbbet[link_m], m]
        else:
            for k,v in sl_otobrs_matches_nbbet.items():
                if sl_sopostavleniy[v[2]] == m[2]:
                    sop_val = get_sopostavlenie([k], [link_m], 81, sl_chemps_zamen)
                    for key, value in sop_val.items():
                        if value != '':
                            print('Нашел', sl_otobrs_matches_nbbet[key])
                            sl_matches_cappers[key] = [sl_otobrs_matches_nbbet[key], m]
                            break
    
    return sl_matches_cappers



def get_stavka_matches(sl_matches_stavka_do_igri, day, d_start, d_end):
    global COUNT_LIMIT_STAVKA
    
    settings = None
    sp_chemps_strategy_nbbet = [] # Общий список лиг из файла настроек для проставления
    sp_otobrs_matches_nbbet = [] # Список отобранных игр в nbbet

    selected_sport = 'Футбол'    
    param_ratio = 87 # точность сопоставления

    # загружаем словарь ставок
    with open('sl_stavok.json', 'r', encoding='utf-8') as file:
        sl_stavok_data = json.load(file)

    # Получаем настройки стратегий
    settings, sp_chemps_strategy_nbbet, sp_stavok = get_settings()

    # Получаем игры с сайта https://nbbet
    sp_countrys, sp_otobrs_matches_nbbet = get_nbbet_games(sp_otobrs_matches_nbbet, selected_sport, d_start, d_end, sp_stavok, sp_chemps_strategy_nbbet)
    print(f'Отобрано игр: {len(sp_otobrs_matches_nbbet)}')

    # Формируем словарь с отобранными играми
    sl_otobrs_matches_nbbet = get_dict_otobrs_matches_nbbet(sp_otobrs_matches_nbbet, settings, d_start, d_end)

    # Получаем страны с сайта https://kushvsporte.ru
    sl_country,  csrf_token, PHPSESSID, _csrf = get_all_leagas(day)
    if len(sl_country) != 0:
        # Оставляем только найденные страны в списке https://kushvsporte.ru
        sl_country, sl_sopostavleniy = get_find_countries_kushvsporte(sl_country, sp_countrys, param_ratio)
        print(sl_country)
        
        # Находим игры для ставки
        sl_matches_cappers = get_matches_kushvsporte(sl_country, sl_otobrs_matches_nbbet, sl_sopostavleniy, day, csrf_token, PHPSESSID, _csrf)
        
        # Если игры найдены, то проверяем условия и делаем ставки
        if len(sl_matches_cappers) != 0:
            # Нужно определить какие ставим сразу, а какие за час до игры
            print('*'*30)
            
            sl_matches_stavka_now = {} # Словарь игр, которые проставляем сразу            
            
            for k,v in sl_matches_cappers.items():
                if COUNT_LIMIT_STAVKA>=30:
                    break
                
                if k not in SP_BED_MATCHES:                    
                    link = v[1][-1]
                    eid = link.split('/event/')[1].split('-')[0]
                    stavka = sl_stavok_data[v[0][21]][0]
                    
                    
                    fl_stavki = False
                    
                    kef_diap = [0,100]
                    for k2,v2 in settings.items():
                        if v[0][2] in v2['страны'] and v[0][21].strip().lower() == v2['ставка_НБ'].strip().lower():
                            # Определяем какая ставка (прямая или обратная)
                            if v2['ставка_НБ'].strip().lower() != v2['ставка_куш'].strip().lower():
                                print('обратная')
                                fl_stavki = True
                                stavka = sl_stavok_data[v[0][21]][1]
                            
                            if v2['диапазон_мин'] != '':
                                kef_diap[0] = float(f"{v2['диапазон_мин']}".replace(',','.'))
                            if v2['диапазон_макс'] != '':
                                kef_diap[1] = float(f"{v2['диапазон_макс']}".replace(',','.'))
                    
                    print(kef_diap)
                    tabl = get_all_variants_po_stavkam(csrf_token, PHPSESSID, _csrf, eid, stavka, kef_diap,link)
                    print(tabl)
                    if tabl:
                        if fl_stavki == False:
                            if v[0][22]>=v[0][23]:
                                print(f'Ставка падает, проставляем сразу')
                                print(k,v[0])
                                # дата, время, чемпионат, дома, гости, ссылка, url, ставка, кэф
                                sl_matches_stavka_now[k] = [v[0][0],v[0][1],v[1][2],v[1][3],v[1][4],v[1][5], tabl[0], stavka, tabl[1]]
                                COUNT_LIMIT_STAVKA+=1
                                
                            if v[0][22]<v[0][23]:
                                print(f'Ставка растет, проставляем за час до игры')
                                print(k,v[0])
                                sl_matches_stavka_do_igri[k] = [v[0][0],v[0][1],v[1][2],v[1][3],v[1][4],v[1][5], eid, stavka, link]
                                COUNT_LIMIT_STAVKA+=1
                        
                        if fl_stavki == True:
                            # Обратная ставка
                            if v[0][22]<=v[0][23]:
                                print(f'Ставка растет, проставляем сразу')
                                print(k,v[0])
                                # дата, время, чемпионат, дома, гости, ссылка, url, ставка, кэф
                                sl_matches_stavka_now[k] = [v[0][0],v[0][1],v[1][2],v[1][3],v[1][4],v[1][5], tabl[0], stavka, tabl[1]]
                                COUNT_LIMIT_STAVKA+=1
                                
                            if v[0][22]>v[0][23]:
                                print(f'Ставка падает, проставляем за час до игры')
                                print(k,v[0])
                                sl_matches_stavka_do_igri[k] = [v[0][0],v[0][1],v[1][2],v[1][3],v[1][4],v[1][5], eid, stavka, link]
                                COUNT_LIMIT_STAVKA+=1
                        
                    # Добавляем игру в список ЧС, чтобы избежать повторной отправки
                    SP_BED_MATCHES.append(k)
                    time.sleep(1.5)
                                       
        
            if len(sl_matches_stavka_now) != 0:
                # Отправляем игры, кэф на которые падает
                start_avtostavka(sl_matches_stavka_now)                    

    else:
        print('Подходящих стран на сайте https://kushvsporte.ru не обнаружено')    
    
    print('Жду следующего времени...')
    return sl_matches_stavka_do_igri




def check_upcoming_games_simple(sl):
    # Проверяем игры и проставляем ставки за час до игры
    global sl_count_bed_response
    current_time = datetime.now()    
    
    sl_m = {} # Временный словарь для отправки игр за час до игры
    sl_copy = sl.copy()
    for game_key, game_data in sl_copy.items():
        try:
            # Формируем datetime объект из данных игры
            date_parts = game_data[0].split('.')
            time_parts = game_data[1].replace('.', ':').split(':')
            
            game_datetime = datetime(
                year=int(date_parts[2]),
                month=int(date_parts[1]),
                day=int(date_parts[0]),
                hour=int(time_parts[0]),
                minute=int(time_parts[1])
            )
            
            # Вычисляем разницу
            time_diff = game_datetime - current_time
            
            # Проверяем, что игра еще не началась и до начала <= 1 час
            if timedelta(seconds=0) < time_diff <= timedelta(hours=1):
                # Преобразуем разницу в минуты
                sl_m[game_key] = game_data                
                
        except Exception as e:
            print(f"Ошибка при обработке {game_key}: {str(e)}")
            continue
    
    #
    # Отправляем игры, (за час до игры)
    if len(sl_m) != 0:
        print(f'Проставляю игры за час до начала ({len(sl_m)} игр)')
        sp_otpr_m1 = start_avtostavka(sl_m)
        
        # Удаляем отправленные игры
        for s in sp_otpr_m1:            
            if s in sl:
                sl.pop(s)
            if s in sl_m:
                sl_m.pop(s)
        
        # обновляем счетчик ошибок отправки
        for s in sl_m:
            if s in sl_count_bed_response:
                sl_count_bed_response[s]+=1
                # Если ошибок больше 3х, то удаляем игру из словаря
                if sl_count_bed_response[s]>=3:
                    if s in sl:                        
                        print('Игра не отправилась после 3х попыток:')
                        print(sl[s])
                        print('')
                        sl.pop(s)
            else:
                sl_count_bed_response[s] = 1
            
    return sl


def start_monitor():
    global COUNT_LIMIT_STAVKA
    
    sl_matches_stavka_do_igri = {} # Словарь игр, которые проставляем до игры    
    
    hours_1 = 12
    # Флаги для отслеживания, был ли уже запущен парсинг
    ten_am_notified = False
    eleven_thirty_pm_notified = False
    print('Работа начата...')
    while True:
        # Получаем текущее время
        now = datetime.now()
        current_time = now.time()
        current_date = now.date()
        
        if current_time.hour == hours_1 and ten_am_notified == False:            
            print(f'Запуск парсера и ставок в {now.strftime("%d.%m.%Y %H:%M")}')
            day = 0
            d_start = datetime.now().strftime('%d.%m.%Y')#'06.12.2025'
            d_end = datetime.now().strftime('%d.%m.%Y')#'06.12.2025'
            sl_matches_stavka_do_igri = get_stavka_matches(sl_matches_stavka_do_igri, day, d_start, d_end)
            ten_am_notified = True
        
        if current_time.hour == 23 and eleven_thirty_pm_notified == False:
            if current_time.minute >= 30 and current_time.minute <= 50:
                print(f'Запуск парсера и ставок в {now.strftime("%d.%m.%Y %H:%M")}')
                day = 1
                d_start = (datetime.now()+timedelta(days=1)).strftime('%d.%m.%Y')#'06.12.2025'
                d_end = (datetime.now()+timedelta(days=1)).strftime('%d.%m.%Y')#'06.12.2025'
                COUNT_LIMIT_STAVKA = 0
                sl_matches_stavka_do_igri = get_stavka_matches(sl_matches_stavka_do_igri, day, d_start, d_end)
                eleven_thirty_pm_notified = True
        
        if current_time.hour != hours_1:
            ten_am_notified = False
        if current_time.hour != 23:
            eleven_thirty_pm_notified = False
        
        # Проверяем игры и проставляем ставки за час до игры
        if len(sl_matches_stavka_do_igri) != 0:
            sl_matches_stavka_do_igri = check_upcoming_games_simple(sl_matches_stavka_do_igri)


        hours_1 = 10
        time.sleep(60)


start_monitor()


