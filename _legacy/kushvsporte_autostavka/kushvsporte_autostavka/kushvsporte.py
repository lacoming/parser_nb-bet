import time
import json
import requests

from bs4 import BeautifulSoup



def get_all_leagas(day):
    sl_country = {}
    PHPSESSID = None
    _csrf = None
    csrf_token = None
    
    
    url = f'https://kushvsporte.ru/centerbet/football?day={day}&_pjax=#center-bet'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate',
        'Sec-GPC': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Priority': 'u=0, i',
        }
    
    response = None
    for i in range(3):
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                break
        except Exception as ex:
            print(f'Ошибка подключения:\n{ex}')
            time.sleep(1.5)
            pass
    
    if response:        
        header = response.headers
        PHPSESSID = f"{header}".split('PHPSESSID=')[1].split(';')[0]
        _csrf = f"{header}".split('_csrf=')[1].split(';')[0]
        
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            csrf_token = soup.find('meta', {'name':'csrf-token'}).attrs['content']
            
            tables = soup.find('div', {'id':'center-bet'}).find_all('a', {'class':'centerEventLink'})
            for tabl in tables:
                country_name = tabl.find('span', {'class':'align-super'}).text.strip()
                country_id = tabl.attrs['data-cid']        
                #print(country_id, country_name)
                sl_country[country_id] = country_name
        except Exception as ex:
            print(f'Ошибка получения стран:\n{ex}')
            time.sleep(1.5)
            pass

    return sl_country, csrf_token, PHPSESSID, _csrf


def get_matches_leagas(cid, day, csrf_token, PHPSESSID, _csrf, ligas):
    sp_matches = []
    
    cookies = {
        'PHPSESSID': PHPSESSID,
        '_csrf': _csrf,
        'rambler': '1',        
        'showPresent': 'true',
        'hideCookie': 'true',
        }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0',
        'Accept': '*/*',
        'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate',        
        'X-CSRF-Token': csrf_token,
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Origin': 'https://kushvsporte.ru',
        'Sec-GPC': '1',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Priority': 'u=0',
        }
    
    data = {
        'cid': f'{cid}',
        'day': f'{day}',
        'status': '',
        }
    
    response = None
    for i in range(3):
        try:
            response = requests.post('https://kushvsporte.ru/bet/event-list', cookies=cookies, headers=headers, data=data)
            if response.status_code == 200:
                break
        except:
            time.sleep(1.5)
            pass
    
    if response:
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            tables = soup.find_all('div', {'class':'row'})
            for tabl in tables:
                date_m = tabl.find('div', {'class':'medium-text'}).text.strip()
                day_m = tabl.find('div', {'class':'d-inline-block d-md-block'}).text.strip()
                teams = tabl.find('a', {'class':'d-block'})
                link = teams.attrs['href']
                home = teams.find_all('div', {'class':'medium-text'})[0].text.strip()
                away = teams.find_all('div', {'class':'medium-text'})[1].text.strip()                
                #print([date_m,day_m,ligas,home,away,link])
                sp_matches.append([date_m,day_m,ligas,home,away,link])
        except:
            pass
    
    return sp_matches



def get_all_variants_po_stavkam(csrf_token, PHPSESSID, _csrf, eid, stavka, kef_diap, link):
    # Сканируем все варианты ставок    
    cookies = {
        'showPresent': 'true',
        'PHPSESSID': PHPSESSID,
        '_csrf': _csrf,
        'rambler': '1',
        '_ym_isad': '2',
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0',
        'Accept': '*/*',
        'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate',
        'Referer': f'https://kushvsporte.ru{link}',
        'X-CSRF-Token': csrf_token,
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Origin': 'https://kushvsporte.ru',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Priority': 'u=0',
        }

    data = {
        'eid': f"{eid}",
        }
    
    response = None
    for i in range(3):
        try:
            response = requests.post('https://kushvsporte.ru/bet/cf-list', cookies=cookies, headers=headers, data=data)
            #print(response.status_code)
            if response.status_code == 200:
                break
        except:
            time.sleep(1.5)
            pass
    
    if response:
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            #print(soup)
            tables = soup.find_all('button', {'class':'coefLink'})
            for tabl in tables:
                stavka_btn = tabl.find('div', {'class':'d-sm-none'})                
                # Ищем подходящую ставку
                if stavka_btn.text.strip() == stavka:
                    kef_btn = tabl.find('span').text.strip()                    
                    # проверяем на диапазон кэфов
                    if float(kef_btn) >= kef_diap[0] and float(kef_btn) <= kef_diap[1]:
                        #print(tabl)
                        return [tabl.attrs['url'],kef_btn]
        except:
            pass
    
    return None
        
        

def login_to_kushvsporte(username, password):
    # авторизация на сайте
    # 1. Инициализация сессии для сохранения cookies между запросами
    session = requests.Session()
    base_url = "https://kushvsporte.ru"
    
    # Устанавливаем общие заголовки для всех запросов сессии
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0',
        'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
        'Sec-GPC': '1',
        'Connection': 'keep-alive',
        })

    # 2. Загрузка главной страницы для получения CSRF-токена
    try:
        response = session.get(base_url)
        response.raise_for_status()  # Проверка на ошибки HTTP
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при загрузке страницы: {e}")
        return None

    # 3. Поиск формы авторизации в HTML и извлечение токена
    soup = BeautifulSoup(response.content, 'html.parser')

    # 3.1 Находим форму входа по id модального окна
    login_form = soup.find('form', {'id': 'login-widget-form'})
    if not login_form:
        print("Не удалось найти форму авторизации на странице.")
        return None

    # 3.2 Находим CSRF-токен
    csrf_token = None
    csrf_input = login_form.find('input', {'name': '_csrf'})
    if csrf_input and csrf_input.get('value'):
        csrf_token = csrf_input['value']
    else:
        print("Внимание: CSRF-токен не найден. Авторизация не удалась.")
        return None

    # 4. Подготовка данных для отправки
    login_url = base_url + "/users/login"
    login_data = {
        'login-form[login]': username,
        'login-form[password]': password,
        'login-form[rememberMe]': '0',  # "Запомнить меня"
        '_csrf': csrf_token if csrf_token else ''
        }

    # 5. Отправка POST-запроса на авторизацию
    headers = {
        #'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0',
        'Referer': base_url,
        'Content-Type': 'application/x-www-form-urlencoded',
        }

    try:
        login_response = session.post(login_url, data=login_data, headers=headers)
        login_response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при отправке запроса на авторизацию: {e}")
        return None

    # 6. Проверка успешности авторизации
    # 6.1 Проверяем наличие перенаправления на главную страницу после логина
    if login_response.url == base_url or '/users/login' not in login_response.url:
        print(f"Авторизация успешна для пользователя: {username}")
        return session, csrf_token  # Возвращаем авторизованную сессию
    else:
        # 6.2 Проверяем текст ответа на наличие ошибки
        if "неправильный логин или пароль" in login_response.text.lower():
            print("Ошибка авторизации: Неверный логин или пароль.")
        else:
            print("Авторизация не удалась. Неизвестная ошибка.")
        return None


def get_match_leagas_session(link, session):
    sl_country = {}
    PHPSESSID = None
    _csrf = None
    csrf_token = None
    
    
    url = f'https://kushvsporte.ru{link}?abtest=9'
    current_cookies = dict(session.cookies)
    # Дополняем куки недостающими значениями
    cookies = {
        'PHPSESSID': current_cookies['PHPSESSID'],
        '_csrf': current_cookies['_csrf'],
        'rambler': '1',
        #'_ymab_param': 'PbeeuQJBd0sWvEvPc6rp6vFsk2swngJmOxNDfcnFWp7N5ue0CpM7uTy_so8zz0dW2saTki6jywDwoC1bubnH9lilhu0',
        'showPresent': 'true',
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Sec-GPC': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Priority': 'u=0, i',
        }  
    
    response = None
    for i in range(3):
        try:
            response = session.get(url, cookies=cookies, headers=headers)
            if response.status_code == 200:
                print(response.status_code)
                break
        except Exception as ex:
            print(f'Ошибка подключения:\n{ex}')
            time.sleep(1.5)
            pass
    
    if response:        
        try:
            soup = BeautifulSoup(response.text, 'html.parser')            
            csrf_token = soup.find('meta', {'name':'csrf-token'}).attrs['content']            
        except:
            pass

    return csrf_token, session


def create_coupon(session, tokens, csrf_token, link):
    # отправляем ставку
    try:
        current_cookies = dict(session.cookies)
        # Дополняем куки недостающими значениями
        cookies = {
            'PHPSESSID': current_cookies['PHPSESSID'],
            '_csrf': current_cookies['_csrf'],
            'rambler': '1',            
            'showPresent': 'true',
            'showCoupon': 'true',
            }
        
        # Генерируем boundary
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0',
            'Accept': 'text/html, */*; q=0.01',        
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Referer': f'https://kushvsporte.ru{link}?abtest=9',
            'X-CSRF-Token': current_cookies['_csrf'],
            'X-PJAX': 'true',
            'X-PJAX-Container': '#coupon',
            'X-Requested-With': 'XMLHttpRequest',
            #'Content-Type': f'multipart/form-data; boundary={boundary}',        
            'Origin': 'https://kushvsporte.ru',
            'Sec-GPC': '1',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            }    
     
        form_data = {}
        for k,v in tokens.items():
            form_data[f"{k}"] = f"{v}"
        
        form_data['Coupon[bet_amount]'] = '400'
        form_data['Coupon[comment]'] = ''    
        form_data['addReviewButton2'] = ''
        form_data['_pjax'] = '#coupon'

        response = requests.post('https://kushvsporte.ru/coupon/create-coupon',
                                 headers=headers, cookies=cookies, data=form_data,
                                 timeout=30,allow_redirects=True)
        
        #print(response.status_code)
        #with open('333.txt', 'w', encoding='utf-8') as f:
        #    f.write(f"{response.text}")
        #print(response.text)
        return response
    except Exception as ex:
        print(f'ошибка ставки: {ex}')
        return None



def get_cf_list(session, csrf_token, eid, link):
    try:
        target_url = 'https://kushvsporte.ru/bet/cf-list'
        
        current_cookies = dict(session.cookies)
        # Дополняем куки недостающими значениями
        required_cookies = {
            'showPresent': 'true',
            'PHPSESSID': current_cookies['PHPSESSID'],
            '_csrf': current_cookies['_csrf'],
            'rambler': '1',        
            }
        
        # Данные для POST-запроса
        post_data = {
            'eid': f"{eid}",
            }
        
        # Заголовки для целевого запроса (важные специфичные заголовки)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0',
            'Accept': '*/*',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Referer': f'https://kushvsporte.ru{link}?abtest=9',
            'X-CSRF-Token': csrf_token,
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://kushvsporte.ru',
            'Sec-GPC': '1',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Priority': 'u=0',
            }
        response = session.post('https://kushvsporte.ru/bet/cf-list', cookies=required_cookies, data=post_data, headers=headers)
        return response
    except:
        return None


def add_coupon(session, csrf_token, eid, cfid, link):    
    response = get_cf_list(session, csrf_token, eid, link)
    if response and response.status_code == 200:
        try:
            url = f"https://kushvsporte.ru/coupon/add-coupon?eid={eid}&cfid={cfid}&_pjax=%23coupon"
            
            # Делаем запрос на извлечение параметров для составления купона
            current_cookies = dict(session.cookies)
            cookies = {
                'PHPSESSID': current_cookies['PHPSESSID'],
                '_csrf': current_cookies['_csrf'],
                'rambler': '1',                
                'showPresent': 'true',
                }

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0',
                'Accept': 'text/html, */*; q=0.01',
                'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
                'Accept-Encoding': 'gzip, deflate, br, zstd',            
                'Referer': f'https://kushvsporte.ru{link}?abtest=9',
                'X-CSRF-Token': csrf_token,
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-PJAX': 'true',
                'X-PJAX-Container': '#coupon',
                'X-Requested-With': 'XMLHttpRequest',
                'Sec-GPC': '1',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'Priority': 'u=0',
                }

            response = session.get(url, cookies=cookies, headers=headers)
            # Парсим HTML для извлечения токенов        
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Находим форму добавления прогноза
            form = soup.find('form', {'action': '/coupon/create-coupon'})
            #print(form)
            if not form:
                print("Форма не найдена!")
                return None
            
            # Ищем все скрытые поля
            hidden_inputs = form.find_all('input')
            
            tokens = {}        
            for inp in hidden_inputs:                
                name = inp.get('name', '')
                value = inp.get('value', '')
                if name:  # Пропускаем поля без имени
                    tokens[name] = value
                    #print(f"  {name}: {value}")
            return session, tokens
        except Exception as ex:
            print(f'Ошибка в add_coupon: {ex}')
            pass        

    return None, None



def start_avtostavka(sl_matches):
    # Функция для проставления списка ставок
    sp_otpr = []
    
    # Считываем настройки
    with open('settings.json', 'r', encoding='utf-8') as file:
        settings = json.load(file)
    
    MY_USERNAME = settings['MY_USERNAME']
    MY_PASSWORD = settings['MY_PASSWORD']
    
    sl_matches_copy = sl_matches.copy()
    # Авторизация на сайте
    
    auth_session, csrf_token = login_to_kushvsporte(MY_USERNAME, MY_PASSWORD)
    if auth_session:
        for k,v in sl_matches_copy.items():
            # sheffild-yunayted-norvich-siti
            # ['09.12.2025', '22.45', 'Чемпионат Англии. Чемпионшип', 'Шеффилд Юнайтед', 'Норвич Сити',
            # '/event/6304590-sheffild-yunayted-norvich-siti', '/coupon/add-coupon?eid=6304590&cfid=1995008947',
            # 'ТБ (2.50)', '1.64']
            print(k,v)
            link = v[5]
            if '?eid=' not in v[6]:
                day = 0
                sl_country,  csrf_token_m, PHPSESSID_m, _csrf_m = get_all_leagas(day)
                tabl = get_all_variants_po_stavkam(csrf_token_m, PHPSESSID_m, _csrf_m, v[6], v[7], [0,100],v[8])
                eid = tabl[0].split('?eid=')[1].split('&')[0].strip()
                cfid = tabl[0].split('cfid=')[1].strip()
            
            if '?eid=' in v[6]:
                eid = v[6].split('?eid=')[1].split('&')[0].strip()
                cfid = v[6].split('cfid=')[1].strip()                        
            
            csrf_token, auth_session = get_match_leagas_session(link, auth_session)
            #print(csrf_token)
            auth_session, tokens = add_coupon(auth_session,csrf_token, eid, cfid, link)
            print([link, eid, cfid])
            response = create_coupon(auth_session, tokens, csrf_token, link)
            try:
                with open(f'{eid}_{cfid}.txt', 'w', encoding='utf-8') as f:
                    f.write(f"{response.text}")                
            except:
                pass
            
            if "Прогноз успешно добавлен" in response.text:
                print('Добавлен прогноз:')
                print(f"{v[0]} в {v[1]}\n{v[2]}\n{v[3]} - {v[4]}\n{v[7]}: {v[8]}")
                sl_matches.pop(k)
                sp_otpr.append(k)
            time.sleep(2.5)
    
    return sp_otpr


'''
MY_USERNAME = "ds-maloy1986@yandex.ru"
MY_PASSWORD = "Lvbnhbq28"
eid = '6304592'
cfid = '1997052033'
link = '/event/6304592-suonsi-siti-portsmut'

auth_session, csrf_token = login_to_kushvsporte(MY_USERNAME, MY_PASSWORD)
print(csrf_token)

if auth_session:
    print('Авторизован')    
    csrf_token, auth_session = get_match_leagas_session(link, auth_session)
    print(csrf_token)
    auth_session, tokens = add_coupon(auth_session,csrf_token, eid, cfid, link)
    
    response = create_coupon(auth_session, tokens, csrf_token, link)
    if "Прогноз успешно добавлен" in response.text:
        print('ok')
input()
'''          
'''
eid = '6298832'
link = '/event/6298832-boregem-vud-nyuport-kaunti'
csrf_token ='yZzuYPk4N3E8Ch3sewCB1JugedK7th3Cj58j2fwkGLuz8qw2lX0GJV5HdIVNbeiV9ewSo9ObKK_2qxa4sGh73Q=='
_csrf = 'znBVlE1TbMii6miAnLkqh-5my45aLLcf'
PHPSESSID = 'q8a1ntkkd8a6ha2iu58hpvecvq'
stavka = 'Обе забьют Да'
kef_diap = [0,100]
get_all_variants_po_stavkam(csrf_token, PHPSESSID, _csrf, eid, stavka, kef_diap, link)

input()
'''

'''
cid = 29431
day = 'Чемпионат Англии. Премьер-лига'
get_matches_leagas(cid, day)
'''

'''
day = 1
sl_country,  csrf_token, PHPSESSID, _csrf = get_all_leagas(day)
for k,v in sl_country.items():
    print(k,v)
    get_matches_leagas(k, day, csrf_token, PHPSESSID, _csrf, v)
    break
'''