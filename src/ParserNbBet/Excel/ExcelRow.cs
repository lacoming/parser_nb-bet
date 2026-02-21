namespace ParserNbBet.Excel;

/// <summary>
/// One row of data to write into the Excel output file.
/// Represents a bet decision/placement result for a single match.
/// </summary>
public sealed class ExcelRow
{
    // Match info
    public DateTime Date { get; init; }
    public string Time { get; init; } = "";
    public string League { get; init; } = "";
    public string TeamHome { get; init; } = "";
    public string TeamAway { get; init; } = "";
    public string Sport { get; init; } = "";

    // NB odds (start / end)
    public double? Odds1Start { get; init; }
    public double? Odds1End { get; init; }
    public double? OddsXStart { get; init; }
    public double? OddsXEnd { get; init; }
    public double? Odds2Start { get; init; }
    public double? Odds2End { get; init; }

    // Odds movement: (start - end) / start
    public double? OddsMovement1 => (Odds1Start.HasValue && Odds1End.HasValue && Odds1Start.Value != 0)
        ? (Odds1Start.Value - Odds1End.Value) / Odds1Start.Value
        : null;
    public double? OddsMovement2 => (Odds2Start.HasValue && Odds2End.HasValue && Odds2Start.Value != 0)
        ? (Odds2Start.Value - Odds2End.Value) / Odds2Start.Value
        : null;

    // Decision
    public string BetType { get; init; } = "";
    public bool Passes { get; init; }
    public string Reasons { get; init; } = "";

    // Kush matching
    public bool KushMatched { get; init; }
    public double? OddsKush { get; init; }
    public double? Ratio { get; init; }

    // Bet result
    public string BetStatus { get; init; } = ""; // "placed", "dry-run", "pending", "failed", "skipped"
    public double? Stake { get; init; }

    // Links
    public string NbUrl { get; init; } = "";
    public string KushUrl { get; init; } = "";
}
