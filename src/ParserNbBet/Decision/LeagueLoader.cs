using ClosedXML.Excel;
using Serilog;

namespace ParserNbBet.Decision;

/// <summary>
/// Reads leagues.xlsx and produces a list of <see cref="LeagueSetting"/>.
///
/// Expected Excel format (columns A–F, header row 1, data from row 2):
///   A = Sport (e.g. "Футбол") — starts a new strategy group
///   B = League name (one per row; multiple rows = multiple leagues in same strategy)
///   C = Min coefficient (optional, default 0)
///   D = Max coefficient (optional, default 100)
///   E = Bet type on NB (e.g. "МП", "П1")
///   F = Bet type on Kush (e.g. "П1", "ТМ (2.50)")
/// </summary>
public static class LeagueLoader
{
    public static List<LeagueSetting> Load(string xlsxPath)
    {
        if (!File.Exists(xlsxPath))
            throw new FileNotFoundException($"leagues.xlsx not found: {xlsxPath}");

        using var workbook = new XLWorkbook(xlsxPath);
        var ws = workbook.Worksheets.First();

        var result = new List<LeagueSetting>();
        LeagueSetting? current = null;
        int strategyId = 0;

        int lastRow = ws.LastRowUsed()?.RowNumber() ?? 0;

        for (int row = 2; row <= lastRow; row++) // skip header
        {
            var sportCell = ws.Cell(row, 1).GetString().Trim();
            var leagueCell = ws.Cell(row, 2).GetString().Trim();
            var minKfCell = ws.Cell(row, 3).GetString().Trim();
            var maxKfCell = ws.Cell(row, 4).GetString().Trim();
            var betNbCell = ws.Cell(row, 5).GetString().Trim();
            var betKushCell = ws.Cell(row, 6).GetString().Trim();

            // New sport cell = new strategy group
            if (!string.IsNullOrEmpty(sportCell))
            {
                if (current != null)
                    result.Add(current);

                strategyId++;
                current = new LeagueSetting
                {
                    StrategyId = strategyId,
                    Sport = sportCell.ToLowerInvariant(),
                    Leagues = [],
                    MinKf = ParseDouble(minKfCell, 0),
                    MaxKf = ParseDouble(maxKfCell, 100),
                    BetTypeNb = betNbCell,
                    BetTypeKush = betKushCell,
                };
            }

            if (current == null)
                continue;

            // Update non-league fields if they appear on subsequent rows (same strategy)
            if (string.IsNullOrEmpty(sportCell))
            {
                if (!string.IsNullOrEmpty(minKfCell))
                    current.MinKf = ParseDouble(minKfCell, current.MinKf);
                if (!string.IsNullOrEmpty(maxKfCell))
                    current.MaxKf = ParseDouble(maxKfCell, current.MaxKf);
                if (!string.IsNullOrEmpty(betNbCell))
                    current.BetTypeNb = betNbCell;
                if (!string.IsNullOrEmpty(betKushCell))
                    current.BetTypeKush = betKushCell;
            }

            // Add league if present
            if (!string.IsNullOrEmpty(leagueCell))
                current.Leagues.Add(leagueCell);
        }

        // Don't forget the last group
        if (current != null)
            result.Add(current);

        Log.Information("LeagueLoader: loaded {Count} strategies with {LeagueCount} total leagues from {Path}",
            result.Count,
            result.Sum(s => s.Leagues.Count),
            xlsxPath);

        return result;
    }

    private static double ParseDouble(string value, double fallback)
    {
        if (string.IsNullOrWhiteSpace(value))
            return fallback;

        // Handle both comma and dot as decimal separator
        value = value.Replace(',', '.');
        return double.TryParse(value, System.Globalization.NumberStyles.Float,
            System.Globalization.CultureInfo.InvariantCulture, out var result)
            ? result
            : fallback;
    }
}
