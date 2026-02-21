namespace ParserNbBet.Nb;

/// <summary>
/// A match parsed from NB-Bet API.
/// </summary>
public sealed class Match
{
    /// <summary>Stable dedup key: "{league}|{home}|{away}|{yyyyMMdd}".</summary>
    public string MatchKey { get; }
    public string League { get; }
    public string TeamHome { get; }
    public string TeamAway { get; }
    public DateTime StartTimeUtc { get; }
    public string NbSlug { get; }
    public string Sport { get; }

    // 1X2 odds (start / end)
    public double? Odds1Start { get; init; }
    public double? OddsXStart { get; init; }
    public double? Odds2Start { get; init; }
    public double? Odds1End { get; init; }
    public double? OddsXEnd { get; init; }
    public double? Odds2End { get; init; }

    /// <summary>Derived: min(Odds1End, OddsXEnd) — used in decision engine as "kf1X".</summary>
    public double? Odds1XEnd =>
        (Odds1End.HasValue && OddsXEnd.HasValue)
            ? Math.Min(Odds1End.Value, OddsXEnd.Value)
            : null;

    public Match(string league, string teamHome, string teamAway,
                 DateTime startTimeUtc, string nbSlug, string sport)
    {
        League = league;
        TeamHome = teamHome;
        TeamAway = teamAway;
        StartTimeUtc = startTimeUtc;
        NbSlug = nbSlug;
        Sport = sport;
        MatchKey = $"{league}|{teamHome}|{teamAway}|{startTimeUtc:yyyyMMdd}";
    }

    public override string ToString() =>
        $"[{Sport}] {League}: {TeamHome} vs {TeamAway} ({StartTimeUtc:yyyy-MM-dd HH:mm}) " +
        $"1={Odds1End} X={OddsXEnd} 2={Odds2End}";
}
