import re
import json

# ГЛОБАЛЬНЫЙ СЛОВАРЬ ПЕРЕВОДОВ
TRANSLATIONS = {
    "home": "1",
    "away": "2", 
    "total": "Т",
    "individualTotal": "ИТ", 
    "totalEven": "Тотал чет",
    "even": "Чет",
    "handicap": "Ф",
    "over": "Б",
    "under": "М",
    "home": "1",
    "away": "2",
    "individual": "И",
    "yes": "Да",
    "no": "Нет",
    "atLeastOneTeamWillNotScore": "Хотя бы одна не заб.",
    "bothTeamsToScore": "Обе забьют",
    "first": "1-й",
    "second": "2-й", 
    "third": "3-й",
    "corners": "Угловые",
    "yellowCards": "ЖК",
    "half": "тайм",
    "period": "период",
    "set": "сет",
    "win": "П",
    "draw": "X",
    "byExactlyOneGoalOrDraw": "в 1 мяч или X",
    "scoreDraw": "Рез. ничья",
    "winToNil": "Сухая П{{count}}",
    "winToNilShort": "СП",
    "HT/FT": "Тайм/Матч",
    "setMatch": "Сет/Матч",
    "drawShort": "X",
    "numberOfGoals": {"1": "в {{countGoals}} гол", "2": "в {{countGoals}} гола"},
    "correctScore": "Точный счет",
    "anyScore": "любой после",
    "goalInBothHalves": "Гол в обоих таймах",
    "goalInEachPeriods": "Гол в каждом периоде",
    "scoreIn": {"1": "Результативность таймов", "2": "Результативность периодов", "3": "Результативность сетов"},
    "firstTeam": "К1",
    "secondTeam": "К2",
    "team": "К",
    "firstTeamWin": "П1", 
    "secondTeamWin": "П2",
    "whoWillWinMostPeriods": "Кто выиграет больше периодов",
    "teamWins": "Победа в матче",
    "teamToQualify": "Проход",
    "penalty": "Пенальти",
    "removal": "Удаление",
    "drawOneHalf": "Ничья хотя бы в одном из таймов",
    "toScoreAndLose": "забьет и проиграет",
    "winsOneHalf": "Выиграет один из таймов",
    "whoWillWinTheCup": "Кубок выиграет",
    "highestScoringPeriod": "Самый результативный период",
    "tieBreak": "Тай-брейк",
    "lossSetWithoutScoring": "Игрок не выиграет ни одного гейма в сете",
    "totalSets": "Тотал сетов"
}

def decode_odds_key(odds_key, ODDS_KEYS):
    """
    Распознает ключ ставки и возвращает читаемое название
    """
    if isinstance(odds_key, int):
        key_str = ODDS_KEYS.get(odds_key, "")
        if not key_str:
            return f"Неизвестный ключ: {odds_key}"
    else:
        key_str = str(odds_key)
    
    if not key_str:
        return "Неизвестная ставка"
    
    # Обработка угловых с периодами
    if key_str.startswith("CORNERS_") and ("FIRST_PERIOD_" in key_str or "SECOND_PERIOD_" in key_str or "THIRD_PERIOD_" in key_str):
        return decode_corners_with_period_key(key_str)
    
    # Обработка угловых
    elif key_str.startswith("CORNERS_"):
        return decode_corners_key(key_str)
    
    # Обработка желтых карточек с периодами
    elif key_str.startswith("YELLOW_CARDS_") and ("FIRST_PERIOD_" in key_str or "SECOND_PERIOD_" in key_str or "THIRD_PERIOD_" in key_str):
        return decode_yellow_cards_with_period_key(key_str)
    
    # Обработка желтых карточек
    elif key_str.startswith("YELLOW_CARDS_"):
        return decode_yellow_cards_key(key_str)
    
    # Обработка периодов
    elif key_str.startswith("FIRST_PERIOD_"):
        return decode_period_key(key_str, TRANSLATIONS["first"])
    elif key_str.startswith("SECOND_PERIOD_"):
        return decode_period_key(key_str, TRANSLATIONS["second"])
    elif key_str.startswith("THIRD_PERIOD_"):
        return decode_period_key(key_str, TRANSLATIONS["third"])
    
    elif key_str.startswith("ASIAN_HANDICAP_"):
        return decode_asian_handicap_key(key_str)
    elif key_str.startswith("HANDICAP_"):
        return decode_handicap_key(key_str)
    elif key_str.startswith("ASIAN_TOTAL_"):
        return decode_asian_total_key(key_str)
    elif key_str.startswith("ASIAN_TEAM_TOTAL_"):
        return decode_asian_team_total_key(key_str)
    elif key_str.startswith("ITB_") or key_str.startswith("ITM_"):
        return decode_individual_total_key(key_str)
    elif key_str.startswith("TB_") or key_str.startswith("TM_"):
        return decode_total_key(key_str)
    else:
        return decode_main_key(key_str)


def decode_asian_team_total_key(key_str):
    """Обрабатывает азиатские командные тоталы"""
    parts = key_str.split("_")
    
    if len(parts) >= 5:
        # ASIAN_TEAM_TOTAL_0_75_MORE_HOME или ASIAN_TEAM_TOTAL_0_75_LESS_AWAY
        value_part1 = parts[3]  # 0
        value_part2 = parts[4]  # 75
        direction = parts[5]  # MORE или LESS
        team = parts[6] if len(parts) > 6 else "HOME"  # HOME или AWAY
        
        team_num = "1" if team == "HOME" else "2"
        direction_text = TRANSLATIONS["over"] if direction == "MORE" else TRANSLATIONS["under"]
        value_formatted = f"{value_part1}.{value_part2}"
        
        return f"Азиатский {TRANSLATIONS['individualTotal']}{team_num} {direction_text} ({value_formatted})"
    
    return key_str


def decode_asian_total_key(key_str):
    """Обрабатывает азиатские тоталы"""
    parts = key_str.split("_")
    
    if len(parts) >= 4:
        # ASIAN_TOTAL_0_75_MORE или ASIAN_TOTAL_0_75_LESS
        value_part1 = parts[2]  # 0
        value_part2 = parts[3]  # 75
        direction = parts[4] if len(parts) > 4 else "MORE"  # MORE или LESS
        
        # Форматируем значение (0.75)
        value_formatted = f"{value_part1}.{value_part2}"
        
        if direction == "MORE":
            return f"Азиатский тотал Б ({value_formatted})"
        elif direction == "LESS":
            return f"Азиатский тотал М ({value_formatted})"
    
    return key_str



def decode_handicap_key(key_str):
    parts = key_str.split("_")
    #print(parts)
    if len(parts) >= 3:
        direction = parts[1]
        value = '_'.join(parts[2:-1])
        team = parts[-1] if len(parts) > 3 else "HOME"
        team_num = "1" if team == "HOME" else "2"
        
        # Обработка знаков PLUS/MINUS
        if direction == "MINUS":
            sign = "-"
        elif direction == "PLUS":
            sign = "+"
        else:
            # Если direction - это число, определяем знак автоматически
            try:
                num_value = float(direction.replace("_", "."))                
                sign = "-" if num_value > 0 else "+"
                value = direction  # в этом случае direction - это значение
                team = parts[-1] if len(parts) > 2 else "HOME"
                team_num = "1" if team == "HOME" else "2"
            except ValueError:
                sign = ""
        
        value_formatted = value.replace("_", ".")
        return f"Фора {team_num} ({sign}{value_formatted})"
    
    return key_str


def decode_asian_handicap_key(key_str):
    """Обрабатывает азиатские форы"""
    parts = key_str.split("_")
    
    if len(parts) >= 5:
        # ASIAN_HANDICAP_MINUS_0_75_HOME или ASIAN_HANDICAP_PLUS_0_75_AWAY
        direction = parts[2]  # MINUS или PLUS
        value_part1 = parts[3]  # 0
        value_part2 = parts[4]  # 75
        team = parts[5] if len(parts) > 5 else "HOME"  # HOME или AWAY
        
        team_num = "1" if team == "HOME" else "2"
        sign = "-" if direction == "MINUS" else "+"
        value_formatted = f"{value_part1}.{value_part2}"
        
        return f"Азиатская фора {team_num} ({sign}{value_formatted})"
    
    return key_str


def decode_corners_with_period_key(key_str):
    """Обрабатывает угловые с периодами"""
    if "FIRST_PERIOD_" in key_str:
        period = f"{TRANSLATIONS['first']} {TRANSLATIONS['period']}"
        rest = key_str.replace("CORNERS_FIRST_PERIOD_", "")
    elif "SECOND_PERIOD_" in key_str:
        period = f"{TRANSLATIONS['second']} {TRANSLATIONS['period']}"
        rest = key_str.replace("CORNERS_SECOND_PERIOD_", "")
    elif "THIRD_PERIOD_" in key_str:
        period = f"{TRANSLATIONS['third']} {TRANSLATIONS['period']}"
        rest = key_str.replace("CORNERS_THIRD_PERIOD_", "")
    else:
        period = ""
        rest = key_str.replace("CORNERS_", "")
    
    # Форы угловых с периодами
    if rest.startswith("HANDICAP_"):
        handicap_result = decode_handicap_key(rest)
        return f"{TRANSLATIONS['corners']} {period} - {handicap_result}"
    
    # Тоталы на чет/нечет угловых с периодами
    elif rest.startswith("TOTAL_EVEN_"):
        even_result = decode_total_even_key(rest)
        return f"{TRANSLATIONS['corners']} {period} - {even_result}"
    
    # Индивидуальные тоталы
    elif rest.startswith("ITB_") or rest.startswith("ITM_"):
        total_result = decode_individual_total_key(rest)
        return f"{TRANSLATIONS['corners']} {period} - {total_result}"
    
    # Тоталы
    elif rest.startswith("TB_") or rest.startswith("TM_"):
        total_result = decode_total_key(rest)
        return f"{TRANSLATIONS['corners']} {period} - {total_result}"
    
    # Основные
    else:
        return f"{TRANSLATIONS['corners']} {period} - {decode_main_key(rest)}"

def decode_yellow_cards_with_period_key(key_str):
    """Обрабатывает желтые карточки с периодами"""
    if "FIRST_PERIOD_" in key_str:
        period = f"{TRANSLATIONS['first']} {TRANSLATIONS['period']}"
        rest = key_str.replace("YELLOW_CARDS_FIRST_PERIOD_", "")
    elif "SECOND_PERIOD_" in key_str:
        period = f"{TRANSLATIONS['second']} {TRANSLATIONS['period']}"
        rest = key_str.replace("YELLOW_CARDS_SECOND_PERIOD_", "")
    elif "THIRD_PERIOD_" in key_str:
        period = f"{TRANSLATIONS['third']} {TRANSLATIONS['period']}"
        rest = key_str.replace("YELLOW_CARDS_THIRD_PERIOD_", "")
    else:
        period = ""
        rest = key_str.replace("YELLOW_CARDS_", "")
    
    # Форы желтых карточек с периодами
    if rest.startswith("HANDICAP_"):
        handicap_result = decode_handicap_key(rest)
        return f"{TRANSLATIONS['yellowCards']} {period} - {handicap_result}"
    
    # Тоталы на чет/нечет желтых карточек с периодами
    elif rest.startswith("TOTAL_EVEN_"):
        even_result = decode_total_even_key(rest)
        return f"{TRANSLATIONS['yellowCards']} {period} - {even_result}"
    
    # Индивидуальные тоталы
    elif rest.startswith("ITB_") or rest.startswith("ITM_"):
        total_result = decode_individual_total_key(rest)
        return f"{TRANSLATIONS['yellowCards']} {period} - {total_result}"
    
    # Тоталы
    elif rest.startswith("TB_") or rest.startswith("TM_"):
        total_result = decode_total_key(rest)
        return f"{TRANSLATIONS['yellowCards']} {period} - {total_result}"
    
    # Основные
    else:
        return f"{TRANSLATIONS['yellowCards']} {period} - {decode_main_key(rest)}"

def decode_individual_total_key(key_str):
    """Обрабатывает индивидуальные тоталы"""
    parts = key_str.split("_")
    #print(parts)
    
    if len(parts) >= 3:
        bet_type = parts[0]  # ITB или ITM
        if len(parts) == 3:
            value = parts[1]  # 5, 1_5 и т.д.
        
        if len(parts) == 4:
            value = '_'.join(parts[1:3])  # 5, 1_5 и т.д.
        
        team = "HOME"
        if len(parts) > 2 and len(parts) <=3:
            team = parts[2]
        if len(parts) > 3:
            team = parts[3]        
        
        team_num = TRANSLATIONS["home"] if team == "HOME" else TRANSLATIONS["away"]        
        direction = TRANSLATIONS["over"] if bet_type == "ITB" else TRANSLATIONS["under"]
        value_formatted = value.replace("_", ".")
        #print(team_num)        
        return f"{TRANSLATIONS['individualTotal']}{team_num} {direction} ({value_formatted})"
    
    return key_str

def decode_total_key(key_str):
    """Обрабатывает тоталы"""
    if key_str.startswith("TB_"):
        total_val = key_str.replace("TB_", "").replace("_", ".")
        return f"{TRANSLATIONS['total']}{TRANSLATIONS['over']} ({total_val})"
    elif key_str.startswith("TM_"):
        total_val = key_str.replace("TM_", "").replace("_", ".")
        return f"{TRANSLATIONS['total']}{TRANSLATIONS['under']} ({total_val})"
    return key_str

def decode_corners_key(key_str):
    """Обрабатывает ключи угловых"""
    rest = key_str.replace("CORNERS_", "")
    
    # Форы угловых
    if rest.startswith("HANDICAP_"):
        handicap_result = decode_handicap_key(rest)
        return f"{TRANSLATIONS['corners']} - {handicap_result}"
    
    # Тоталы на чет/нечет угловых
    elif rest.startswith("TOTAL_EVEN_"):
        even_result = decode_total_even_key(rest)
        return f"{TRANSLATIONS['corners']} - {even_result}"
    
    # Индивидуальные тоталы угловых
    elif rest.startswith("ITB_") or rest.startswith("ITM_"):
        total_result = decode_individual_total_key(rest)
        return f"{TRANSLATIONS['corners']} - {total_result}"
    
    # Тоталы угловых
    elif rest.startswith("TB_") or rest.startswith("TM_"):
        total_result = decode_total_key(rest)
        return f"{TRANSLATIONS['corners']} - {total_result}"
    
    # Основные угловые
    else:
        return f"{TRANSLATIONS['corners']} - {decode_main_key(rest)}"

def decode_total_even_key(key_str):
    """Обрабатывает тоталы на чет/нечет"""
    rest = key_str.replace("TOTAL_EVEN_", "")
    
    if rest == "YES":
        return TRANSLATIONS["totalEven"]
    elif rest == "NO":
        return f"{TRANSLATIONS['total']}{TRANSLATIONS['even']} {TRANSLATIONS['no']}"
    
    return f"{TRANSLATIONS['totalEven']} {rest}"


def decode_yellow_cards_key(key_str):
    """Обрабатывает ключи желтых карточек"""
    rest = key_str.replace("YELLOW_CARDS_", "")
    
    # Форы желтых карточек
    if rest.startswith("HANDICAP_"):
        handicap_result = decode_handicap_key(rest)
        return f"{TRANSLATIONS['yellowCards']} - {handicap_result}"
    
    # Тоталы на чет/нечет желтых карточек
    elif rest.startswith("TOTAL_EVEN_"):
        even_result = decode_total_even_key(rest)
        return f"{TRANSLATIONS['yellowCards']} - {even_result}"
    
    # Индивидуальные тоталы желтых карточек
    elif rest.startswith("ITB_") or rest.startswith("ITM_"):
        total_result = decode_individual_total_key(rest)
        return f"{TRANSLATIONS['yellowCards']} - {total_result}"
    
    # Тоталы желтых карточек
    elif rest.startswith("TB_") or rest.startswith("TM_"):
        total_result = decode_total_key(rest)
        return f"{TRANSLATIONS['yellowCards']} - {total_result}"
    
    # Основные желтые карточки
    else:
        return f"{TRANSLATIONS['yellowCards']} - {decode_main_key(rest)}"
    
    

def decode_period_key(key_str, period_name):
    """Обрабатывает ключи периодов"""
    rest = key_str.replace("FIRST_PERIOD_", "").replace("SECOND_PERIOD_", "").replace("THIRD_PERIOD_", "")
    #print(rest)
    # Азиатские командные тоталы периода
    if rest.startswith("ASIAN_TEAM_TOTAL_"):
        asian_result = decode_asian_team_total_key(rest)
        return f"{period_name} {TRANSLATIONS['period']} - {asian_result}"
    
    # Форы периода
    elif rest.startswith("HANDICAP_"):
        handicap_result = decode_handicap_key(rest)
        return f"{period_name} {TRANSLATIONS['period']} - {handicap_result}"
    
    # Азиатские форы периода
    elif rest.startswith("ASIAN_HANDICAP_"):
        asian_handicap_result = decode_asian_handicap_key(rest)
        return f"{period_name} {TRANSLATIONS['period']} - {asian_handicap_result}"
    
    # Азиатские тоталы периода
    elif rest.startswith("ASIAN_TOTAL_"):
        asian_total_result = decode_asian_total_key(rest)
        return f"{period_name} {TRANSLATIONS['period']} - {asian_total_result}"
    
    # Тоталы на чет/нечет периода
    elif rest.startswith("TOTAL_EVEN_"):
        even_result = decode_total_even_key(rest)
        return f"{period_name} {TRANSLATIONS['period']} - {even_result}"
    
    # Индивидуальные тоталы периода
    elif rest.startswith("ITB_") or rest.startswith("ITM_"):
        total_result = decode_individual_total_key(rest)
        #print(total_result)
        return f"{period_name} {TRANSLATIONS['period']} - {total_result}"
    
    # Тоталы периода
    elif rest.startswith("TB_") or rest.startswith("TM_"):
        total_result = decode_total_key(rest)
        return f"{period_name} {TRANSLATIONS['period']} - {total_result}"
    
    # Победы в периоде
    elif rest == "WIN_HOME":
        return f"{period_name} {TRANSLATIONS['period']} - {TRANSLATIONS['win']}{TRANSLATIONS['home']}"
    elif rest == "WIN_AWAY":
        return f"{period_name} {TRANSLATIONS['period']} - {TRANSLATIONS['win']}{TRANSLATIONS['away']}"
    elif rest == "DRAW":
        return f"{period_name} {TRANSLATIONS['period']} - {TRANSLATIONS['draw']}"
    
    return f"{period_name} {TRANSLATIONS['period']} - {decode_main_key(rest)}"


def decode_main_key(key_str):
    """Обрабатывает основные ключи ставок"""
    if key_str.startswith("CORRECT_SCORE_"):
        score = key_str.replace("CORRECT_SCORE_", "").replace("_", ":")
        return f"{TRANSLATIONS['correctScore']} {score}"
    elif key_str == "WIN_HOME":
        return f"{TRANSLATIONS['win']}{TRANSLATIONS['home']}"
    elif key_str == "WIN_AWAY":
        return f"{TRANSLATIONS['win']}{TRANSLATIONS['away']}"
    elif key_str == "DRAW":
        return TRANSLATIONS["draw"]
    elif key_str == "BOTH_TO_SCORE_YES":
        return f"{TRANSLATIONS['bothTeamsToScore']} - {TRANSLATIONS['yes']}"
    elif key_str == "BOTH_TO_SCORE_NO":
        return f"{TRANSLATIONS['bothTeamsToScore']} - {TRANSLATIONS['no']}"
    elif key_str == "TOTAL_EVEN_YES":
        return TRANSLATIONS["totalEven"]
    elif key_str == "TOTAL_EVEN_NO":
        return f"{TRANSLATIONS['total']}{TRANSLATIONS['even']} {TRANSLATIONS['no']}"
    # Двойные исходы
    elif key_str == "HOME_OR_X":
        return f"{TRANSLATIONS['home']} или {TRANSLATIONS['drawShort']}"
    elif key_str == "AWAY_OR_X":
        return f"{TRANSLATIONS['away']} или {TRANSLATIONS['drawShort']}"
    elif key_str == "HOME_OR_AWAY":
        return f"{TRANSLATIONS['home']} или {TRANSLATIONS['away']}"
    elif key_str == "X_OR_AWAY":
        return f"{TRANSLATIONS['drawShort']} или {TRANSLATIONS['away']}"
    # Результативная ничья
    elif key_str == "SCORE_DRAW_YES":
        return f"{TRANSLATIONS['scoreDraw']} - {TRANSLATIONS['yes']}"
    elif key_str == "SCORE_DRAW_NO":
        return f"{TRANSLATIONS['scoreDraw']} - {TRANSLATIONS['no']}"
    # Комбинированные ставки "победа + точное количество голов"
    elif key_str.startswith("WIN_AND_NUMBER_OF_GOALS_"):
        return decode_win_and_number_of_goals_key(key_str)
    
    elif key_str.startswith("RESULT_FIRST_IS_") or key_str.startswith("RESULT_SECOND_IS_"):
        return decode_result_comparison_extended_key(key_str)
    
    # Ставки на квалификацию и кубок
    elif key_str.startswith("TEAM_TO_QUALIFY_"):
        return decode_team_to_qualify_key(key_str)
    elif key_str.startswith("WHO_WILL_WIN_THE_CUP_"):
        return decode_who_will_win_the_cup_key(key_str)
    
    # Ставки на таймы и специальные события
    elif key_str.startswith("GOAL_IN_BOTH_HALVES_"):
        return decode_goal_in_both_halves_key(key_str)
    elif key_str.startswith("WIN_ONE_HALF_"):
        return decode_win_one_half_key(key_str)
    elif key_str.startswith("DRAW_ONE_HALF_"):
        return decode_draw_one_half_key(key_str)
    elif key_str.startswith("PERSONAL_TOTAL_EVEN_"):
        return decode_personal_total_even_key(key_str)
    elif key_str.startswith("PENALTY_"):
        return decode_penalty_key(key_str)
    elif key_str.startswith("REMOVAL_"):
        return decode_removal_key(key_str)
    
    # Теннисные ставки
    elif key_str.startswith("TIE_BREAK_"):
        return decode_tie_break_key(key_str)
    elif key_str.startswith("SETS_TB_") or key_str.startswith("SETS_TM_"):
        return decode_sets_total_key(key_str)
    
    # Сложные комбинированные ставки
    elif key_str.startswith("WIN_OR_DRAW_AND_BOTH_TEAMS_TO_SCORE_"):
        return decode_win_or_draw_and_both_teams_to_score_key(key_str)
    elif key_str.startswith("HOME_OR_AWAY_AND_BOTH_TEAMS_TO_SCORE_"):
        return decode_home_or_away_and_both_teams_to_score_key(key_str)
    
    # Комбинированные ставки "обе забьют + тотал"
    elif key_str.startswith("BOTH_TEAMS_TO_SCORE_"):
        return decode_both_teams_total_key(key_str)
    # Победа в 1 мяч или ничья
    elif key_str.startswith("WIN_BY_EXACTLY_ONE_GOAL_OR_DRAW_"):
        return decode_win_by_one_or_draw_key(key_str)
    
    # Ставки на сравнение результатов периодов
    elif key_str.startswith("RESULT_FIRST_IS_"):
        return decode_result_comparison_key(key_str)
        
    # Победа всухую
    elif key_str.startswith("WIN_TO_NIL_"):
        # Проверяем, есть ли тотал в ключе
        if "TB_" in key_str or "TM_" in key_str:
            return decode_win_to_nil_total_key(key_str)
        else:
            return decode_win_to_nil_key(key_str)
    
    # Комбинированные ставки "победа + обе забьют"
    elif key_str.startswith("WIN_AND_BOTH_TEAMS_TO_SCORE_"):
        return decode_win_and_both_teams_to_score_key(key_str)

    # Комбинированные ставки с ничьей
    elif key_str.startswith("DRAW_AND_BOTH_TEAMS_TO_SCORE_"):
        return decode_draw_and_both_teams_to_score_key(key_str)
    elif key_str.startswith("DRAW_AND_TB_") or key_str.startswith("DRAW_AND_TM_"):
        return decode_draw_and_total_key(key_str)

    # Забьет и проиграет
    elif key_str in ["HOME_TO_SCORE_AND_LOSE", "AWAY_TO_SCORE_AND_LOSE"]:
        return decode_score_and_lose_key(key_str)
    
    # Ставки на периоды
    elif key_str.startswith("WHO_WILL_WIN_MOST_PERIODS_"):
        return decode_who_will_win_most_periods_key(key_str)
    elif key_str.startswith("GOAL_IN_EACH_PERIOD_"):
        return decode_goal_in_each_period_key(key_str)
    
    # Ставки на самый результативный период и расширенные сравнения
    elif key_str.startswith("HIGHEST_SCORING_PERIOD_TOTAL_"):
        return decode_highest_scoring_period_key(key_str)
    elif key_str.startswith("TEAM_WINS_"):
        return decode_team_wins_key(key_str)
    
    # Комбинированные теннисные ставки
    elif key_str.startswith("WIN_AND_SETS_"):
        return decode_win_and_sets_total_key(key_str)
    elif key_str.startswith("LOSS_SET_WITHOUT_SCORING_"):
        return decode_loss_set_without_scoring_key(key_str)
    
    # Теннисные ставки на сеты
    elif key_str.startswith("SM_"):
        return decode_set_match_key(key_str)
    elif key_str.startswith("SET_FIRST_IS_"):
        return decode_set_comparison_key(key_str)
    
    # Комбинированные ставки "победа + тотал"
    elif key_str.startswith("WIN_AND_"):
        return decode_win_and_total_key(key_str)
    # Комбинированные ставки "поражение + тотал"
    elif key_str.startswith("LOSE_AND_"):
        return decode_lose_and_total_key(key_str)
    # Комбинированные ставки "победа или ничья + тотал"
    elif key_str.startswith("WIN_OR_DRAW_AND_"):
        return decode_win_or_draw_and_total_key(key_str)
    # Комбинированные ставки "хотя бы одна не забьет + тотал"
    elif key_str.startswith("AT_LEAST_ONE_TEAM_WILL_NOT_SCORE_"):
        return decode_at_least_one_not_score_total_key(key_str)    
        
    # Ставки на точный счет и HT/FT
    elif key_str.startswith("ANY_SCORE_AFTER_"):
        return decode_any_score_after_key(key_str)
    elif key_str.startswith("HT_FT_"):
        return decode_ht_ft_key(key_str)
    
    return key_str


def decode_set_match_key(key_str):
    """Обрабатывает ставки 'сет/матч' для тенниса"""
    rest = key_str.replace("SM_", "")
    
    # Создаем словарь для преобразования
    result_map = {
        "WIN_HOME": f"{TRANSLATIONS['win']}{TRANSLATIONS['home']}",
        "WIN_AWAY": f"{TRANSLATIONS['win']}{TRANSLATIONS['away']}"
    }
    
    # Разбираем комбинацию
    if rest == "WIN_HOME_WIN_HOME":
        return f"{TRANSLATIONS['setMatch']} {result_map['WIN_HOME']}/{result_map['WIN_HOME']}"
    elif rest == "WIN_HOME_WIN_AWAY":
        return f"{TRANSLATIONS['setMatch']} {result_map['WIN_HOME']}/{result_map['WIN_AWAY']}"
    elif rest == "WIN_AWAY_WIN_HOME":
        return f"{TRANSLATIONS['setMatch']} {result_map['WIN_AWAY']}/{result_map['WIN_HOME']}"
    elif rest == "WIN_AWAY_WIN_AWAY":
        return f"{TRANSLATIONS['setMatch']} {result_map['WIN_AWAY']}/{result_map['WIN_AWAY']}"
    
    return key_str

def decode_set_comparison_key(key_str):
    """Обрабатывает ставки на сравнение сетов"""
    
    if key_str == "SET_FIRST_IS_GREATER_THAN_SECOND":
        return f"Счет 1-го {TRANSLATIONS['set']} > 2-го {TRANSLATIONS['set']}"
    elif key_str == "SET_FIRST_IS_EQUAL_THAN_SECOND":
        return f"Счет 1-го {TRANSLATIONS['set']} = 2-му {TRANSLATIONS['set']}"
    elif key_str == "SET_FIRST_IS_LESS_THAN_SECOND":
        return f"Счет 1-го {TRANSLATIONS['set']} < 2-го {TRANSLATIONS['set']}"
    
    return key_str


def decode_win_and_sets_total_key(key_str):
    """Обрабатывает комбинированные ставки 'победа + тотал сетов'"""
    rest = key_str.replace("WIN_AND_SETS_", "")
    
    # Определяем тип тотала сетов и команду
    if rest.startswith("TB_"):
        parts = rest.split("_")
        if len(parts) >= 4:
            total_type = parts[0]  # TB
            total_value = parts[1] + "." + parts[2]  # 2_5 -> 2.5
            result = parts[3]  # YES или NO
            team = parts[4] if len(parts) > 4 else "HOME"  # HOME или AWAY
            
            team_num = "1" if team == "HOME" else "2"
            direction = TRANSLATIONS["over"] if total_type == "TB" else TRANSLATIONS["under"]
            result_text = TRANSLATIONS["yes"] if result == "YES" else TRANSLATIONS["no"]
            
            return f"{TRANSLATIONS['win']}{team_num} + {TRANSLATIONS['totalSets']} {direction} ({total_value}) - {result_text}"
    
    elif rest.startswith("TM_"):
        parts = rest.split("_")
        if len(parts) >= 4:
            total_type = parts[0]  # TM
            total_value = parts[1] + "." + parts[2]  # 2_5 -> 2.5
            result = parts[3]  # YES или NO
            team = parts[4] if len(parts) > 4 else "HOME"  # HOME или AWAY
            
            team_num = "1" if team == "HOME" else "2"
            direction = TRANSLATIONS["under"] if total_type == "TM" else TRANSLATIONS["over"]
            result_text = TRANSLATIONS["yes"] if result == "YES" else TRANSLATIONS["no"]
            
            return f"{TRANSLATIONS['win']}{team_num} + {TRANSLATIONS['totalSets']} {direction} ({total_value}) - {result_text}"
    
    return key_str

def decode_loss_set_without_scoring_key(key_str):
    """Обрабатывает ставки 'игрок не выиграет ни одного гейма в сете'"""
    rest = key_str.replace("LOSS_SET_WITHOUT_SCORING_", "")
    
    if rest == "YES":
        return f"{TRANSLATIONS['lossSetWithoutScoring']} - {TRANSLATIONS['yes']}"
    elif rest == "NO":
        return f"{TRANSLATIONS['lossSetWithoutScoring']} - {TRANSLATIONS['no']}"
    
    return key_str



def decode_tie_break_key(key_str):
    """Обрабатывает ставки 'будет тай-брейк'"""
    rest = key_str.replace("TIE_BREAK_", "")
    
    if rest == "YES":
        return f"{TRANSLATIONS['tieBreak']} - {TRANSLATIONS['yes']}"
    elif rest == "NO":
        return f"{TRANSLATIONS['tieBreak']} - {TRANSLATIONS['no']}"
    
    return key_str

def decode_sets_total_key(key_str):
    """Обрабатывает ставки 'тотал сетов'"""
    if key_str.startswith("SETS_TB_"):
        total_val = key_str.replace("SETS_TB_", "").replace("_", ".")
        return f"{TRANSLATIONS['totalSets']} {TRANSLATIONS['over']} ({total_val})"
    elif key_str.startswith("SETS_TM_"):
        total_val = key_str.replace("SETS_TM_", "").replace("_", ".")
        return f"{TRANSLATIONS['totalSets']} {TRANSLATIONS['under']} ({total_val})"
    return key_str



def decode_highest_scoring_period_key(key_str):
    """Обрабатывает ставки 'самый результативный период + тотал'"""
    rest = key_str.replace("HIGHEST_SCORING_PERIOD_TOTAL_", "")
    
    parts = rest.split("_")
    if len(parts) >= 3:
        total_value = parts[0] + "." + parts[1]  # 2_5 -> 2.5
        direction = parts[2]  # MORE или LESS
        
        direction_text = TRANSLATIONS["over"] if direction == "MORE" else TRANSLATIONS["under"]
        
        return f"{TRANSLATIONS['highestScoringPeriod']} {TRANSLATIONS['total']}{direction_text} ({total_value})"
    
    return key_str

def decode_team_wins_key(key_str):
    """Обрабатывает ставки 'победа команды'"""
    rest = key_str.replace("TEAM_WINS_", "")
    
    if rest == "HOME":
        return f"{TRANSLATIONS['teamWins']} - {TRANSLATIONS['firstTeam']}"
    elif rest == "AWAY":
        return f"{TRANSLATIONS['teamWins']} - {TRANSLATIONS['secondTeam']}"
    
    return key_str

def decode_result_comparison_extended_key(key_str):
    """Обрабатывает расширенные ставки на сравнение результатов периодов"""
    
    if key_str == "RESULT_FIRST_IS_GREATER_THAN_THIRD":
        return f"Результат 1-го {TRANSLATIONS['period']} > 3-го {TRANSLATIONS['period']}"
    elif key_str == "RESULT_SECOND_IS_GREATER_THAN_THIRD":
        return f"Результат 2-го {TRANSLATIONS['period']} > 3-го {TRANSLATIONS['period']}"
    elif key_str == "RESULT_FIRST_IS_EQUAL_THAN_THIRD":
        return f"Результат 1-го {TRANSLATIONS['period']} = 3-му {TRANSLATIONS['period']}"
    elif key_str == "RESULT_SECOND_IS_EQUAL_THAN_THIRD":
        return f"Результат 2-го {TRANSLATIONS['period']} = 3-му {TRANSLATIONS['period']}"
    elif key_str == "RESULT_FIRST_IS_LESS_THAN_THIRD":
        return f"Результат 1-го {TRANSLATIONS['period']} < 3-го {TRANSLATIONS['period']}"
    elif key_str == "RESULT_SECOND_IS_LESS_THAN_THIRD":
        return f"Результат 2-го {TRANSLATIONS['period']} < 3-го {TRANSLATIONS['period']}"
    
    return key_str


def decode_result_comparison_key(key_str):
    """Обрабатывает ставки на сравнение результатов периодов/таймов"""
    
    if key_str == "RESULT_FIRST_IS_EQUAL_THAN_SECOND":
        return f"Результат 1-го {TRANSLATIONS['period']} = 2-му {TRANSLATIONS['period']}"
    elif key_str == "RESULT_FIRST_IS_GREATER_THAN_SECOND":
        return f"Результат 1-го {TRANSLATIONS['period']} > 2-го {TRANSLATIONS['period']}"
    elif key_str == "RESULT_FIRST_IS_LESS_THAN_SECOND":
        return f"Результат 1-го {TRANSLATIONS['period']} < 2-го {TRANSLATIONS['period']}"
    elif key_str == "RESULT_FIRST_IS_EQUAL_THAN_SECOND_HOME":
        return f"Результат 1-го {TRANSLATIONS['period']} = 2-му {TRANSLATIONS['period']} ({TRANSLATIONS['firstTeam']})"
    elif key_str == "RESULT_FIRST_IS_GREATER_THAN_SECOND_HOME":
        return f"Результат 1-го {TRANSLATIONS['period']} > 2-го {TRANSLATIONS['period']} ({TRANSLATIONS['firstTeam']})"
    elif key_str == "RESULT_FIRST_IS_LESS_THAN_SECOND_HOME":
        return f"Результат 1-го {TRANSLATIONS['period']} < 2-го {TRANSLATIONS['period']} ({TRANSLATIONS['firstTeam']})"
    elif key_str == "RESULT_FIRST_IS_EQUAL_THAN_SECOND_AWAY":
        return f"Результат 1-го {TRANSLATIONS['period']} = 2-му {TRANSLATIONS['period']} ({TRANSLATIONS['secondTeam']})"
    elif key_str == "RESULT_FIRST_IS_GREATER_THAN_SECOND_AWAY":
        return f"Результат 1-го {TRANSLATIONS['period']} > 2-го {TRANSLATIONS['period']} ({TRANSLATIONS['secondTeam']})"
    elif key_str == "RESULT_FIRST_IS_LESS_THAN_SECOND_AWAY":
        return f"Результат 1-го {TRANSLATIONS['period']} < 2-го {TRANSLATIONS['period']} ({TRANSLATIONS['secondTeam']})"
    
    return key_str



def decode_any_score_after_key(key_str):
    """Обрабатывает ставки 'любой счет после'"""
    rest = key_str.replace("ANY_SCORE_AFTER_", "")
    
    # Заменяем подчеркивания на двоеточия для отображения счета
    score = rest.replace("_", ":")
    return f"{TRANSLATIONS['anyScore']} {score}"

def decode_ht_ft_key(key_str):
    """Обрабатывает ставки 'тайм/матч'"""
    rest = key_str.replace("HT_FT_", "")
    
    # Создаем словарь для преобразования
    result_map = {
        "WIN_HOME": f"{TRANSLATIONS['win']}{TRANSLATIONS['home']}",
        "WIN_AWAY": f"{TRANSLATIONS['win']}{TRANSLATIONS['away']}",
        "DRAW": TRANSLATIONS["draw"],
        "WIN_DRAW_HOME": f"{TRANSLATIONS['home']} или {TRANSLATIONS['drawShort']}",
        "WIN_DRAW_AWAY": f"{TRANSLATIONS['away']} или {TRANSLATIONS['drawShort']}"
    }
    
    # Разбираем комбинацию
    if rest == "DRAW_MATCH_DRAW":
        return f"{TRANSLATIONS['HT/FT']} {result_map['DRAW']}/{result_map['DRAW']}"
    elif rest == "DRAW_MATCH_WIN_HOME":
        return f"{TRANSLATIONS['HT/FT']} {result_map['DRAW']}/{result_map['WIN_HOME']}"
    elif rest == "DRAW_MATCH_WIN_AWAY":
        return f"{TRANSLATIONS['HT/FT']} {result_map['DRAW']}/{result_map['WIN_AWAY']}"
    elif rest == "WIN_HOME_WIN_HOME":
        return f"{TRANSLATIONS['HT/FT']} {result_map['WIN_HOME']}/{result_map['WIN_HOME']}"
    elif rest == "WIN_HOME_MATCH_DRAW":
        return f"{TRANSLATIONS['HT/FT']} {result_map['WIN_HOME']}/{result_map['DRAW']}"
    elif rest == "WIN_HOME_MATCH_WIN_AWAY":
        return f"{TRANSLATIONS['HT/FT']} {result_map['WIN_HOME']}/{result_map['WIN_AWAY']}"
    elif rest == "WIN_AWAY_WIN_AWAY":
        return f"{TRANSLATIONS['HT/FT']} {result_map['WIN_AWAY']}/{result_map['WIN_AWAY']}"
    elif rest == "WIN_AWAY_MATCH_DRAW":
        return f"{TRANSLATIONS['HT/FT']} {result_map['WIN_AWAY']}/{result_map['DRAW']}"
    elif rest == "WIN_AWAY_MATCH_WIN_HOME":
        return f"{TRANSLATIONS['HT/FT']} {result_map['WIN_AWAY']}/{result_map['WIN_HOME']}"
    elif rest == "WIN_AWAY_MATCH_WIN_AWAY":  # ДОБАВИТЬ ЭТУ СТРОЧКУ
        return f"{TRANSLATIONS['HT/FT']} {result_map['WIN_AWAY']}/{result_map['WIN_AWAY']}"
    # Обработка сложных комбинаций с тремя исходами
    elif rest == "WIN_HOME_MATCH_WIN_DRAW_AWAY":
        return f"{TRANSLATIONS['HT/FT']} {result_map['WIN_HOME']}/{result_map['WIN_DRAW_AWAY']}"
    elif rest == "WIN_AWAY_MATCH_WIN_DRAW_HOME":
        return f"{TRANSLATIONS['HT/FT']} {result_map['WIN_AWAY']}/{result_map['WIN_DRAW_HOME']}"
    
    return key_str


def decode_goal_in_both_halves_key(key_str):
    """Обрабатывает ставки 'гол в обоих таймах'"""
    rest = key_str.replace("GOAL_IN_BOTH_HALVES_", "")
    
    if rest == "YES":
        return f"{TRANSLATIONS['goalInBothHalves']} - {TRANSLATIONS['yes']}"
    elif rest == "NO":
        return f"{TRANSLATIONS['goalInBothHalves']} - {TRANSLATIONS['no']}"
    
    return key_str

def decode_win_one_half_key(key_str):
    """Обрабатывает ставки 'выиграет один из таймов'"""
    rest = key_str.replace("WIN_ONE_HALF_", "")
    
    parts = rest.split("_")
    if len(parts) >= 2:
        result = parts[0]  # YES или NO
        team = parts[1]    # HOME или AWAY
        
        team_num = "1" if team == "HOME" else "2"
        result_text = TRANSLATIONS["yes"] if result == "YES" else TRANSLATIONS["no"]
        
        return f"{TRANSLATIONS['winsOneHalf']} {team_num} - {result_text}"
    
    return key_str

def decode_draw_one_half_key(key_str):
    """Обрабатывает ставки 'ничья хотя бы в одном из таймов'"""
    rest = key_str.replace("DRAW_ONE_HALF_", "")
    
    if rest == "YES":
        return f"{TRANSLATIONS['drawOneHalf']} - {TRANSLATIONS['yes']}"
    elif rest == "NO":
        return f"{TRANSLATIONS['drawOneHalf']} - {TRANSLATIONS['no']}"
    
    return key_str

def decode_personal_total_even_key(key_str):
    """Обрабатывает ставки 'индивидуальный тотал на чет/нечет'"""
    rest = key_str.replace("PERSONAL_TOTAL_EVEN_", "")
    
    parts = rest.split("_")
    if len(parts) >= 2:
        result = parts[0]  # YES или NO
        team = parts[1]    # HOME или AWAY
        
        team_num = "1" if team == "HOME" else "2"
        result_text = TRANSLATIONS["yes"] if result == "YES" else TRANSLATIONS["no"]
        
        return f"{TRANSLATIONS['individualTotal']}{team_num} {TRANSLATIONS['even']} - {result_text}"
    
    return key_str

def decode_penalty_key(key_str):
    """Обрабатывает ставки 'будет пенальти'"""
    rest = key_str.replace("PENALTY_", "")
    
    if rest == "YES":
        return f"{TRANSLATIONS['penalty']} - {TRANSLATIONS['yes']}"
    elif rest == "NO":
        return f"{TRANSLATIONS['penalty']} - {TRANSLATIONS['no']}"
    
    return key_str

def decode_removal_key(key_str):
    """Обрабатывает ставки 'будет удаление'"""
    rest = key_str.replace("REMOVAL_", "")
    
    if rest == "YES":
        return f"{TRANSLATIONS['removal']} - {TRANSLATIONS['yes']}"
    elif rest == "NO":
        return f"{TRANSLATIONS['removal']} - {TRANSLATIONS['no']}"
    
    return key_str


def decode_team_to_qualify_key(key_str):
    """Обрабатывает ставки 'команда пройдет дальше'"""
    rest = key_str.replace("TEAM_TO_QUALIFY_", "")
    
    if rest == "HOME":
        return f"{TRANSLATIONS['teamToQualify']} - {TRANSLATIONS['firstTeam']}"
    elif rest == "AWAY":
        return f"{TRANSLATIONS['teamToQualify']} - {TRANSLATIONS['secondTeam']}"
    
    return key_str

def decode_who_will_win_the_cup_key(key_str):
    """Обрабатывает ставки 'кто выиграет кубок'"""
    rest = key_str.replace("WHO_WILL_WIN_THE_CUP_", "")
    
    if rest == "HOME":
        return f"{TRANSLATIONS['whoWillWinTheCup']} - {TRANSLATIONS['firstTeam']}"
    elif rest == "AWAY":
        return f"{TRANSLATIONS['whoWillWinTheCup']} - {TRANSLATIONS['secondTeam']}"
    
    return key_str



def decode_who_will_win_most_periods_key(key_str):
    """Обрабатывает ставки 'кто выиграет больше периодов'"""
    rest = key_str.replace("WHO_WILL_WIN_MOST_PERIODS_", "")
    
    if rest == "HOME":
        return f"{TRANSLATIONS['whoWillWinMostPeriods']} - {TRANSLATIONS['firstTeam']}"
    elif rest == "AWAY":
        return f"{TRANSLATIONS['whoWillWinMostPeriods']} - {TRANSLATIONS['secondTeam']}"
    elif rest == "DRAW":
        return f"{TRANSLATIONS['whoWillWinMostPeriods']} - {TRANSLATIONS['draw']}"
    
    return key_str

def decode_goal_in_each_period_key(key_str):
    """Обрабатывает ставки 'гол в каждом периоде'"""
    rest = key_str.replace("GOAL_IN_EACH_PERIOD_", "")
    
    if rest == "YES":
        return f"{TRANSLATIONS['goalInEachPeriods']} - {TRANSLATIONS['yes']}"
    elif rest == "NO":
        return f"{TRANSLATIONS['goalInEachPeriods']} - {TRANSLATIONS['no']}"
    
    return key_str


def decode_win_or_draw_and_both_teams_to_score_key(key_str):
    """Обрабатывает комбинированные ставки 'победа или ничья + обе забьют'"""
    rest = key_str.replace("WIN_OR_DRAW_AND_BOTH_TEAMS_TO_SCORE_", "")
    
    parts = rest.split("_")
    if len(parts) >= 2:
        result = parts[0]  # YES или NO
        team = parts[1]    # HOME или AWAY
        
        team_num = "1" if team == "HOME" else "2"
        result_text = TRANSLATIONS["yes"] if result == "YES" else TRANSLATIONS["no"]
        
        return f"{TRANSLATIONS['home'] if team == 'HOME' else TRANSLATIONS['away']} или {TRANSLATIONS['drawShort']} + {TRANSLATIONS['bothTeamsToScore']} - {result_text}"
    
    return key_str

def decode_home_or_away_and_both_teams_to_score_key(key_str):
    """Обрабатывает комбинированные ставки 'победа любой команды + обе забьют'"""
    rest = key_str.replace("HOME_OR_AWAY_AND_BOTH_TEAMS_TO_SCORE_", "")
    
    if rest == "YES":
        return f"{TRANSLATIONS['home']} или {TRANSLATIONS['away']} + {TRANSLATIONS['bothTeamsToScore']} - {TRANSLATIONS['yes']}"
    elif rest == "NO":
        return f"{TRANSLATIONS['home']} или {TRANSLATIONS['away']} + {TRANSLATIONS['bothTeamsToScore']} - {TRANSLATIONS['no']}"
    
    return key_str



def decode_draw_and_both_teams_to_score_key(key_str):
    """Обрабатывает комбинированные ставки 'ничья + обе забьют'"""
    rest = key_str.replace("DRAW_AND_BOTH_TEAMS_TO_SCORE_", "")
    
    if rest == "YES":
        return f"{TRANSLATIONS['draw']} + {TRANSLATIONS['bothTeamsToScore']} - {TRANSLATIONS['yes']}"
    elif rest == "NO":
        return f"{TRANSLATIONS['draw']} + {TRANSLATIONS['bothTeamsToScore']} - {TRANSLATIONS['no']}"
    
    return key_str

def decode_draw_and_total_key(key_str):
    """Обрабатывает комбинированные ставки 'ничья + тотал'"""
    rest = key_str.replace("DRAW_AND_", "")
    
    # Определяем тип тотала
    if rest.startswith("TB_"):
        parts = rest.split("_")
        if len(parts) >= 3:
            total_type = parts[0]  # TB
            total_value = parts[1] + "." + parts[2]  # 2_5 -> 2.5
            result = parts[3] if len(parts) > 3 else "YES"  # YES или NO
            
            direction = TRANSLATIONS["over"] if total_type == "TB" else TRANSLATIONS["under"]
            result_text = TRANSLATIONS["yes"] if result == "YES" else TRANSLATIONS["no"]
            
            return f"{TRANSLATIONS['draw']} + {TRANSLATIONS['total']}{direction} ({total_value}) - {result_text}"
    
    elif rest.startswith("TM_"):
        parts = rest.split("_")
        if len(parts) >= 3:
            total_type = parts[0]  # TM
            total_value = parts[1] + "." + parts[2]  # 2_5 -> 2.5
            result = parts[3] if len(parts) > 3 else "YES"  # YES или NO
            
            direction = TRANSLATIONS["under"] if total_type == "TM" else TRANSLATIONS["over"]
            result_text = TRANSLATIONS["yes"] if result == "YES" else TRANSLATIONS["no"]
            
            return f"{TRANSLATIONS['draw']} + {TRANSLATIONS['total']}{direction} ({total_value}) - {result_text}"
    
    return key_str

def decode_score_and_lose_key(key_str):
    """Обрабатывает ставки 'забьет и проиграет'"""
    if key_str == "HOME_TO_SCORE_AND_LOSE":
        return f"{TRANSLATIONS['home']} {TRANSLATIONS['toScoreAndLose']}"
    elif key_str == "AWAY_TO_SCORE_AND_LOSE":
        return f"{TRANSLATIONS['away']} {TRANSLATIONS['toScoreAndLose']}"
    
    return key_str


def decode_win_and_both_teams_to_score_key(key_str):
    """Обрабатывает комбинированные ставки 'победа + обе забьют'"""
    rest = key_str.replace("WIN_AND_BOTH_TEAMS_TO_SCORE_", "")
    
    parts = rest.split("_")
    if len(parts) >= 2:
        result = parts[0]  # YES или NO
        team = parts[1]    # HOME или AWAY
        
        team_num = "1" if team == "HOME" else "2"
        result_text = TRANSLATIONS["yes"] if result == "YES" else TRANSLATIONS["no"]
        
        return f"{TRANSLATIONS['win']}{team_num} + {TRANSLATIONS['bothTeamsToScore']} - {result_text}"
    
    return key_str



def decode_win_to_nil_total_key(key_str):
    """Обрабатывает комбинированные ставки 'победа всухую + тотал'"""
    rest = key_str.replace("WIN_TO_NIL_", "")
    
    # Определяем тип тотала и команду
    if rest.startswith("TB_"):
        parts = rest.split("_")
        if len(parts) >= 4:
            total_type = parts[0]  # TB
            total_value = parts[1] + "." + parts[2]  # 2_5 -> 2.5
            result = parts[3]  # YES или NO
            team = parts[4] if len(parts) > 4 else "HOME"  # HOME или AWAY
            
            team_num = "1" if team == "HOME" else "2"
            direction = TRANSLATIONS["over"] if total_type == "TB" else TRANSLATIONS["under"]
            result_text = TRANSLATIONS["yes"] if result == "YES" else TRANSLATIONS["no"]
            
            return f"{TRANSLATIONS['winToNilShort']}{team_num} + {TRANSLATIONS['total']}{direction} ({total_value}) - {result_text}"
    
    elif rest.startswith("TM_"):
        parts = rest.split("_")
        if len(parts) >= 4:
            total_type = parts[0]  # TM
            total_value = parts[1] + "." + parts[2]  # 2_5 -> 2.5
            result = parts[3]  # YES или NO
            team = parts[4] if len(parts) > 4 else "HOME"  # HOME или AWAY
            
            team_num = "1" if team == "HOME" else "2"
            direction = TRANSLATIONS["under"] if total_type == "TM" else TRANSLATIONS["over"]
            result_text = TRANSLATIONS["yes"] if result == "YES" else TRANSLATIONS["no"]
            
            return f"{TRANSLATIONS['winToNilShort']}{team_num} + {TRANSLATIONS['total']}{direction} ({total_value}) - {result_text}"
    
    return key_str



def decode_win_and_number_of_goals_key(key_str):
    """Обрабатывает комбинированные ставки 'победа + точное количество голов'"""
    rest = key_str.replace("WIN_AND_NUMBER_OF_GOALS_", "")
    
    parts = rest.split("_")
    if len(parts) >= 3:
        # Извлекаем количество голов (может быть 1, 1_2 и т.д.)
        # Собираем части до YES/NO
        goals_parts = []
        result = None
        team = None
        
        for i, part in enumerate(parts):
            if part in ["YES", "NO"]:
                result = part
                if i + 1 < len(parts):
                    team = parts[i + 1]
                break
            else:
                goals_parts.append(part)
        
        if not result:
            return key_str
            
        goals_value = "_".join(goals_parts)
        team = team or "HOME"
        
        team_num = "1" if team == "HOME" else "2"
        result_text = TRANSLATIONS["yes"] if result == "YES" else TRANSLATIONS["no"]
        
        # Обрабатываем количество голов (1 или 1_2)
        if "_" in goals_value:
            # Диапазон голов (1_2 -> 1-2)
            goals_range = goals_value.replace("_", "-")
            goals_display = f"{goals_range} гола"
        else:
            # Одно конкретное количество голов
            try:
                count = int(goals_value)
                if count == 1:
                    goals_display = "1 гол"
                elif 2 <= count <= 4:
                    goals_display = f"{count} гола"
                else:
                    goals_display = f"{count} голов"
            except ValueError:
                goals_display = f"{goals_value} гола"
        
        return f"{TRANSLATIONS['win']}{team_num} + {goals_display} - {result_text}"
    
    return key_str

def decode_at_least_one_not_score_total_key(key_str):
    """Обрабатывает комбинированные ставки 'хотя бы одна не забьет + тотал'"""
    rest = key_str.replace("AT_LEAST_ONE_TEAM_WILL_NOT_SCORE_", "")
    
    # Определяем тип тотала
    if rest.startswith("TM_"):
        parts = rest.split("_")
        if len(parts) >= 3:
            total_type = parts[0]  # TM
            total_value = parts[1] + "." + parts[2]  # 2_5 -> 2.5
            result = parts[3] if len(parts) > 3 else "YES"  # YES или NO
            
            direction = TRANSLATIONS["under"] if total_type == "TM" else TRANSLATIONS["over"]
            result_text = TRANSLATIONS["yes"] if result == "YES" else TRANSLATIONS["no"]
            
            return f"{TRANSLATIONS['atLeastOneTeamWillNotScore']} + {TRANSLATIONS['total']}{direction} ({total_value}) - {result_text}"
    
    elif rest.startswith("TB_"):
        parts = rest.split("_")
        if len(parts) >= 3:
            total_type = parts[0]  # TB
            total_value = parts[1] + "." + parts[2]  # 2_5 -> 2.5
            result = parts[3] if len(parts) > 3 else "YES"  # YES или NO
            
            direction = TRANSLATIONS["over"] if total_type == "TB" else TRANSLATIONS["under"]
            result_text = TRANSLATIONS["yes"] if result == "YES" else TRANSLATIONS["no"]
            
            return f"{TRANSLATIONS['atLeastOneTeamWillNotScore']} + {TRANSLATIONS['total']}{direction} ({total_value}) - {result_text}"
    
    return key_str

def decode_lose_and_total_key(key_str):
    """Обрабатывает комбинированные ставки 'поражение + тотал'"""
    rest = key_str.replace("LOSE_AND_", "")
    
    # Определяем тип тотала и команду
    if rest.startswith("TB_"):
        parts = rest.split("_")
        if len(parts) >= 4:
            total_type = parts[0]  # TB
            total_value = parts[1] + "." + parts[2]  # 2_5 -> 2.5
            result = parts[3]  # YES или NO
            team = parts[4] if len(parts) > 4 else "HOME"  # HOME или AWAY
            
            team_num = "1" if team == "HOME" else "2"
            direction = TRANSLATIONS["over"] if total_type == "TB" else TRANSLATIONS["under"]
            result_text = TRANSLATIONS["yes"] if result == "YES" else TRANSLATIONS["no"]
            
            return f"Поражение {team_num} + {TRANSLATIONS['total']}{direction} ({total_value}) - {result_text}"
    
    elif rest.startswith("TM_"):
        parts = rest.split("_")
        if len(parts) >= 4:
            total_type = parts[0]  # TM
            total_value = parts[1] + "." + parts[2]  # 2_5 -> 2.5
            result = parts[3]  # YES или NO
            team = parts[4] if len(parts) > 4 else "HOME"  # HOME или AWAY
            
            team_num = "1" if team == "HOME" else "2"
            direction = TRANSLATIONS["under"] if total_type == "TM" else TRANSLATIONS["over"]
            result_text = TRANSLATIONS["yes"] if result == "YES" else TRANSLATIONS["no"]
            
            return f"Поражение {team_num} + {TRANSLATIONS['total']}{direction} ({total_value}) - {result_text}"
    
    return key_str

def decode_win_or_draw_and_total_key(key_str):
    """Обрабатывает комбинированные ставки 'победа или ничья + тотал'"""
    rest = key_str.replace("WIN_OR_DRAW_AND_", "")
    
    # Определяем тип тотала и команду
    if rest.startswith("TB_"):
        parts = rest.split("_")
        if len(parts) >= 4:
            total_type = parts[0]  # TB
            total_value = parts[1] + "." + parts[2]  # 2_5 -> 2.5
            result = parts[3]  # YES или NO
            team = parts[4] if len(parts) > 4 else "HOME"  # HOME или AWAY
            
            team_num = "1" if team == "HOME" else "2"
            direction = TRANSLATIONS["over"] if total_type == "TB" else TRANSLATIONS["under"]
            result_text = TRANSLATIONS["yes"] if result == "YES" else TRANSLATIONS["no"]
            
            return f"{TRANSLATIONS['home'] if team == 'HOME' else TRANSLATIONS['away']} или {TRANSLATIONS['drawShort']} + {TRANSLATIONS['total']}{direction} ({total_value}) - {result_text}"
    
    elif rest.startswith("TM_"):
        parts = rest.split("_")
        if len(parts) >= 4:
            total_type = parts[0]  # TM
            total_value = parts[1] + "." + parts[2]  # 2_5 -> 2.5
            result = parts[3]  # YES или NO
            team = parts[4] if len(parts) > 4 else "HOME"  # HOME или AWAY
            
            team_num = "1" if team == "HOME" else "2"
            direction = TRANSLATIONS["under"] if total_type == "TM" else TRANSLATIONS["over"]
            result_text = TRANSLATIONS["yes"] if result == "YES" else TRANSLATIONS["no"]
            
            return f"{TRANSLATIONS['home'] if team == 'HOME' else TRANSLATIONS['away']} или {TRANSLATIONS['drawShort']} + {TRANSLATIONS['total']}{direction} ({total_value}) - {result_text}"
    
    return key_str

def decode_win_by_one_or_draw_key(key_str):
    """Обрабатывает 'победа в 1 мяч или ничья'"""
    parts = key_str.replace("WIN_BY_EXACTLY_ONE_GOAL_OR_DRAW_", "").split("_")
    if len(parts) >= 2:
        result = parts[0]  # YES или NO
        team = parts[1]    # HOME или AWAY
        
        team_num = "1" if team == "HOME" else "2"
        
        if result == "YES":
            return f"{TRANSLATIONS['byExactlyOneGoalOrDraw']} {team_num}"
        elif result == "NO":
            return f"{TRANSLATIONS['byExactlyOneGoalOrDraw']} {team_num} - {TRANSLATIONS['no']}"
    
    return key_str

def decode_win_and_total_key(key_str):
    """Обрабатывает комбинированные ставки 'победа + тотал'"""
    rest = key_str.replace("WIN_AND_", "")
    
    # Определяем тип тотала и команду
    if rest.startswith("TB_"):
        parts = rest.split("_")
        if len(parts) >= 4:
            total_type = parts[0]  # TB
            total_value = parts[1] + "." + parts[2]  # 2_5 -> 2.5
            result = parts[3]  # YES или NO
            team = parts[4] if len(parts) > 4 else "HOME"  # HOME или AWAY
            
            team_num = "1" if team == "HOME" else "2"
            direction = TRANSLATIONS["over"] if total_type == "TB" else TRANSLATIONS["under"]
            result_text = TRANSLATIONS["yes"] if result == "YES" else TRANSLATIONS["no"]
            
            return f"{TRANSLATIONS['win']}{team_num} + {TRANSLATIONS['total']}{direction} ({total_value}) - {result_text}"
    
    elif rest.startswith("TM_"):
        parts = rest.split("_")
        if len(parts) >= 4:
            total_type = parts[0]  # TM
            total_value = parts[1] + "." + parts[2]  # 2_5 -> 2.5
            result = parts[3]  # YES или NO
            team = parts[4] if len(parts) > 4 else "HOME"  # HOME или AWAY
            
            team_num = "1" if team == "HOME" else "2"
            direction = TRANSLATIONS["under"] if total_type == "TM" else TRANSLATIONS["over"]
            result_text = TRANSLATIONS["yes"] if result == "YES" else TRANSLATIONS["no"]
            
            return f"{TRANSLATIONS['win']}{team_num} + {TRANSLATIONS['total']}{direction} ({total_value}) - {result_text}"
    
    return key_str


def decode_win_to_nil_key(key_str):
    """Обрабатывает победу всухую"""
    parts = key_str.replace("WIN_TO_NIL_", "").split("_")
    if len(parts) >= 2:
        result = parts[0]  # YES или NO
        team = parts[1]    # HOME или AWAY
        
        team_num = "1" if team == "HOME" else "2"
        
        if result == "YES":
            return f"{TRANSLATIONS['winToNilShort']}{team_num}"
        elif result == "NO":
            return f"{TRANSLATIONS['winToNilShort']}{team_num} - {TRANSLATIONS['no']}"
    
    return key_str

def decode_both_teams_total_key(key_str):
    """Обрабатывает комбинированные ставки 'обе забьют + тотал'"""
    rest = key_str.replace("BOTH_TEAMS_TO_SCORE_", "")
    
    # Определяем тип тотала
    if rest.startswith("TB_"):
        total_parts = rest.split("_")
        if len(total_parts) >= 3:
            total_type = total_parts[0]  # TB
            total_value = total_parts[1] + "." + total_parts[2]  # 2_5 -> 2.5
            result = total_parts[3] if len(total_parts) > 3 else "YES"  # YES или NO
            
            direction = TRANSLATIONS["over"] if total_type == "TB" else TRANSLATIONS["under"]
            result_text = TRANSLATIONS["yes"] if result == "YES" else TRANSLATIONS["no"]
            
            return f"{TRANSLATIONS['bothTeamsToScore']} + {TRANSLATIONS['total']}{direction} ({total_value}) - {result_text}"
    
    elif rest.startswith("TM_"):
        total_parts = rest.split("_")
        if len(total_parts) >= 3:
            total_type = total_parts[0]  # TM
            total_value = total_parts[1] + "." + total_parts[2]  # 2_5 -> 2.5
            result = total_parts[3] if len(total_parts) > 3 else "YES"  # YES или NO
            
            direction = TRANSLATIONS["under"] if total_type == "TM" else TRANSLATIONS["over"]
            result_text = TRANSLATIONS["yes"] if result == "YES" else TRANSLATIONS["no"]
            
            return f"{TRANSLATIONS['bothTeamsToScore']} + {TRANSLATIONS['total']}{direction} ({total_value}) - {result_text}"
    
    return key_str


# Пример использования
if __name__ == "__main__":
    # Функция для загрузки словаря (один раз при запуске)
    def load_odds_keys_from_file():
        """Загружает словарь ключей из файла"""
        # Чтение из файла
        with open('sl_keys.json', 'r', encoding='utf-8') as file:
            loaded_data = json.load(file)
            
        return {int(k): v for k, v in loaded_data.items()}

    ODDS_KEYS = load_odds_keys_from_file()
    
    print(decode_odds_key(182, ODDS_KEYS))
    
    
    with open('1.txt', 'w', encoding='utf-8') as f:
        for k in ODDS_KEYS:        
            #print(f"Ключ {k}: {decode_odds_key(k)}")
            f.write(f"Ключ {k}: {decode_odds_key(k, ODDS_KEYS)}\n")
    
    print('ok')
    
