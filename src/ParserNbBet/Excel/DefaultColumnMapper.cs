using System.Globalization;

namespace ParserNbBet.Excel;

/// <summary>
/// Default column mapper based on legacy Excel output format.
/// Covers: date, time, league, teams, odds (start/end/movement), decision, kush matching, bet result.
/// </summary>
public sealed class DefaultColumnMapper : IColumnMapper
{
    public IReadOnlyList<ColumnDef> GetColumns() =>
    [
        new("Дата", 12, r => r.Date.ToString("dd.MM.yyyy", CultureInfo.InvariantCulture)),
        new("Время", 10, r => r.Time),
        new("Спорт", 10, r => r.Sport),
        new("Лига", 25, r => r.League),
        new("Команда 1", 25, r => r.TeamHome),
        new("Команда 2", 25, r => r.TeamAway),

        // NB odds
        new("КФ1 нач", 10, r => r.Odds1Start, "0.00"),
        new("КФ1 кон", 10, r => r.Odds1End, "0.00"),
        new("КФX нач", 10, r => r.OddsXStart, "0.00"),
        new("КФX кон", 10, r => r.OddsXEnd, "0.00"),
        new("КФ2 нач", 10, r => r.Odds2Start, "0.00"),
        new("КФ2 кон", 10, r => r.Odds2End, "0.00"),

        // Movement
        new("Движ КФ1", 10, r => r.OddsMovement1, "0.00%"),
        new("Движ КФ2", 10, r => r.OddsMovement2, "0.00%"),

        // Decision
        new("Тип ставки", 12, r => r.BetType),
        new("Проходит", 10, r => r.Passes ? "Да" : "Нет"),
        new("Причины", 40, r => r.Reasons),

        // Kush
        new("Куш найден", 12, r => r.KushMatched ? "Да" : "Нет"),
        new("КФ Куш", 10, r => r.OddsKush, "0.00"),
        new("Ratio", 10, r => r.Ratio, "0.0000"),

        // Bet
        new("Статус", 12, r => r.BetStatus),
        new("Сумма", 10, r => r.Stake, "0"),

        // Links
        new("NB ссылка", 50, r => r.NbUrl),
        new("Куш ссылка", 50, r => r.KushUrl),
    ];
}
