namespace ParserNbBet.Kush;

/// <summary>
/// An event fetched from kushvsporte.ru.
/// </summary>
public sealed class KushEvent
{
    public string EventId { get; }
    public string League { get; }
    public string TeamHome { get; }
    public string TeamAway { get; }
    public DateTime StartTimeUtc { get; }
    public string Url { get; }

    /// <summary>Odds keyed by type string (e.g. "1", "X", "2", "1X", "12", "X2").</summary>
    public IReadOnlyDictionary<string, double> Odds { get; }

    public KushEvent(string eventId, string league, string teamHome, string teamAway,
                     DateTime startTimeUtc, string url,
                     IReadOnlyDictionary<string, double>? odds = null)
    {
        EventId = eventId;
        League = league;
        TeamHome = teamHome;
        TeamAway = teamAway;
        StartTimeUtc = startTimeUtc;
        Url = url;
        Odds = odds ?? new Dictionary<string, double>();
    }

    public override string ToString() =>
        $"[Kush] {League}: {TeamHome} vs {TeamAway} ({StartTimeUtc:yyyy-MM-dd HH:mm})";
}
