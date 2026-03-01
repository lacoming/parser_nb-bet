import os
from openpyxl import load_workbook


def find_excel_files():
    """
    Находит все Excel файлы (.xlsx и .xls) в папке с программой.
    
    Returns:
        list: Список имен файлов с расширением .xlsx и .xls
    """
    # Получаем путь к папке с программой
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    excel_files = []
    
    try:
        # Получаем список всех файлов в директории
        all_files = os.listdir(current_dir)
        
        # Фильтруем файлы по расширению
        for filename in all_files:
            # Проверяем, что это файл (а не папка)
            full_path = os.path.join(current_dir, filename)
            if os.path.isfile(full_path):
                # Проверяем расширение файла
                if filename.lower().endswith('.xlsx') or filename.lower().endswith('.xls'):
                    excel_files.append(filename)
        
        return excel_files
        
    except Exception as e:
        print(f"Ошибка при поиске файлов: {e}")
        return []


def read_excel_with_openpyxl(file_path):
    """
    Читает Excel-файл с помощью openpyxl и формирует структуру данных.
    
    Args:
        file_path (str): Путь к Excel-файлу
        
    Returns:
        dict: Словарь с данными, сгруппированными по виду спорта
    """
    try:
        # Загружаем рабочую книгу
        wb = load_workbook(filename=file_path, data_only=True)
        ws = wb.active
        
        # Инициализируем структуру для хранения результатов
        result = {}        
        
        current_sport = None
        max_row = ws.max_row
        
        fl_sport = []
        nom_settings = 0
        fl_sport_count = 0
        # Проходим по всем строкам (начиная с 1, так как в Excel нумерация с 1)
        for row in range(2, max_row + 1):
            # Получаем значения ячеек A-F            
            sport_cell = ws.cell(row=row, column=1).value  # Столбец A
            
            # Проверяем, есть ли значение в столбце A (спорт)
            if sport_cell is not None and str(sport_cell).strip():
                current_sport = str(sport_cell).strip().lower()
                nom_settings+=1 # номер стратегии
                fl_sport.append(nom_settings)
                result[nom_settings] = {'спорт':current_sport,
                                        'страны': [],
                                        'диапазон_мин': 0,
                                        'диапазон_макс': 100,
                                        'ставка_НБ': '',                                        
                                        'ставка_куш': ''
                                        }
            
            if nom_settings != 0:
                country_cell = ws.cell(row=row, column=2).value  # Столбец B
                min_kf = ws.cell(row=row, column=3).value  # Столбец C
                max_kf = ws.cell(row=row, column=4).value  # Столбец D
                bet_nb = ws.cell(row=row, column=5).value  # Столбец E
                bet_kush = ws.cell(row=row, column=6).value  # Столбец F           
                country = str(country_cell).strip()
                #print(country_cell, country, min_kf, max_kf, bet_nb, bet_kush)
                
                if country and country != 'None' and country != '':
                    #print(result[nom_settings]['страны'])
                    result[nom_settings]['страны'].append(country)
                
                if min_kf and min_kf != '':                
                    result[nom_settings]['диапазон_мин'] = min_kf
                
                if max_kf and max_kf != '':                
                    result[nom_settings]['диапазон_макс'] = max_kf
                
                if bet_nb and bet_nb != '':        
                    result[nom_settings]['ставка_НБ'] = bet_nb
                
                if bet_kush and bet_kush != '':
                    result[nom_settings]['ставка_куш']= bet_kush
        
        return dict(result)
        
    except FileNotFoundError:
        print(f"Ошибка: Файл {file_path} не найден")
        return None
    except Exception as e:
        print(f"Ошибка при чтении файла: {e}")
        return None


if __name__ == "__main__":
    # Находим файл и считываем настройки
    sp_files = find_excel_files()
    for file_path in sp_files:
        settings = read_excel_with_openpyxl(file_path)


    print(len(settings))
