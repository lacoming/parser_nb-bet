namespace ParserNbBet.Kush;

/// <summary>
/// Result of matching an NB event to a Kush event.
/// </summary>
public sealed class MatchResult
{
    /// <summary>The matched Kush event (null if no match found).</summary>
    public KushEvent? KushEvent { get; }

    /// <summary>Overall confidence score 0.0–1.0.</summary>
    public double Confidence { get; }

    /// <summary>Name similarity component (0.0–1.0).</summary>
    public double NameScore { get; }

    /// <summary>Time proximity component (0.0–1.0).</summary>
    public double TimeScore { get; }

    /// <summary>Whether the match meets the minimum confidence threshold.</summary>
    public bool IsAccepted { get; }

    /// <summary>Human-readable explanation.</summary>
    public string Reason { get; }

    public MatchResult(KushEvent? kushEvent, double nameScore, double timeScore,
                       double confidence, bool isAccepted, string reason)
    {
        KushEvent = kushEvent;
        NameScore = nameScore;
        TimeScore = timeScore;
        Confidence = confidence;
        IsAccepted = isAccepted;
        Reason = reason;
    }

    /// <summary>No match found at all.</summary>
    public static MatchResult NoMatch(string reason) =>
        new(null, 0, 0, 0, false, reason);
}
