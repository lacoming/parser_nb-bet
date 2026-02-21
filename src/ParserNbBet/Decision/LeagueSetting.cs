namespace ParserNbBet.Decision;

/// <summary>
/// A betting strategy loaded from leagues.xlsx.
/// One setting = one sport + list of leagues + bet type + coefficient range.
/// Multiple leagues can share the same strategy (grouped by sport row in Excel).
/// </summary>
public sealed class LeagueSetting
{
    /// <summary>Strategy number (1-based, order in Excel).</summary>
    public int StrategyId { get; set; }

    /// <summary>"футбол" or "хоккей" (lowercased).</summary>
    public string Sport { get; set; } = "";

    /// <summary>League names that belong to this strategy.</summary>
    public List<string> Leagues { get; set; } = [];

    /// <summary>Min coefficient on Kush to accept (default 0).</summary>
    public double MinKf { get; set; }

    /// <summary>Max coefficient on Kush to accept (default 100).</summary>
    public double MaxKf { get; set; } = 100;

    /// <summary>Bet type name on NB-Bet (e.g. "П1", "1X", "ТБ (2.5)").</summary>
    public string BetTypeNb { get; set; } = "";

    /// <summary>Corresponding bet type on Kush (e.g. "П1", "ТМ (2.50)").</summary>
    public string BetTypeKush { get; set; } = "";

    /// <summary>True if NB and Kush bet types differ (inverse bet).</summary>
    public bool IsInverse =>
        !string.IsNullOrWhiteSpace(BetTypeNb) &&
        !string.IsNullOrWhiteSpace(BetTypeKush) &&
        !BetTypeNb.Trim().Equals(BetTypeKush.Trim(), StringComparison.OrdinalIgnoreCase);
}
