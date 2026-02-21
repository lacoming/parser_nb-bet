using FuzzySharp;
using ParserNbBet.Config;
using ParserNbBet.Nb;
using Serilog;

namespace ParserNbBet.Kush;

/// <summary>
/// Matches NB events to Kush events using fuzzy team name comparison + time proximity.
/// Confidence = nameScore * 0.7 + timeScore * 0.3 (per ARCHITECTURE.md).
/// </summary>
public sealed class EventMatcher
{
    private const double NameWeight = 0.70;
    private const double TimeWeight = 0.30;

    private readonly int _timeToleranceHours;
    private readonly double _minConfidence;

    public EventMatcher(KushConfig config)
    {
        _timeToleranceHours = config.MatchTimeToleranceHours;
        _minConfidence = config.MinConfidence;
    }

    public EventMatcher(int timeToleranceHours = 2, double minConfidence = 0.80)
    {
        _timeToleranceHours = timeToleranceHours;
        _minConfidence = minConfidence;
    }

    /// <summary>
    /// Find the best matching Kush event for the given NB match.
    /// </summary>
    public MatchResult FindBestMatch(Match nbMatch, IReadOnlyList<KushEvent> kushEvents)
    {
        if (kushEvents.Count == 0)
            return MatchResult.NoMatch("No Kush events available");

        MatchResult? bestResult = null;

        foreach (var kushEvent in kushEvents)
        {
            var result = ScoreMatch(nbMatch, kushEvent);
            if (bestResult is null || result.Confidence > bestResult.Confidence)
                bestResult = result;
        }

        if (bestResult is null)
            return MatchResult.NoMatch("No Kush events evaluated");

        Log.Debug("Best match for {NbMatch}: {KushMatch} (confidence={Confidence:F3}, name={Name:F3}, time={Time:F3})",
            nbMatch, bestResult.KushEvent, bestResult.Confidence, bestResult.NameScore, bestResult.TimeScore);

        return bestResult;
    }

    /// <summary>
    /// Score a single NB ↔ Kush pair.
    /// </summary>
    public MatchResult ScoreMatch(Match nbMatch, KushEvent kushEvent)
    {
        // Time check: must be within tolerance
        var timeDiff = Math.Abs((nbMatch.StartTimeUtc - kushEvent.StartTimeUtc).TotalHours);
        if (timeDiff > _timeToleranceHours)
        {
            return new MatchResult(kushEvent, 0, 0, 0, false,
                $"Time difference {timeDiff:F1}h exceeds tolerance {_timeToleranceHours}h");
        }

        // Time score: 1.0 at exact match, linear decay to 0.0 at tolerance boundary
        var timeScore = 1.0 - (timeDiff / _timeToleranceHours);

        // Name score: fuzzy match both home and away teams
        var homeScore = ComputeNameSimilarity(nbMatch.TeamHome, kushEvent.TeamHome);
        var awayScore = ComputeNameSimilarity(nbMatch.TeamAway, kushEvent.TeamAway);

        // Also check swapped (NB home = Kush away, NB away = Kush home) — some sources swap order
        var homeSwapScore = ComputeNameSimilarity(nbMatch.TeamHome, kushEvent.TeamAway);
        var awaySwapScore = ComputeNameSimilarity(nbMatch.TeamAway, kushEvent.TeamHome);

        var normalScore = (homeScore + awayScore) / 2.0;
        var swappedScore = (homeSwapScore + awaySwapScore) / 2.0;
        var nameScore = Math.Max(normalScore, swappedScore);

        // Overall confidence
        var confidence = nameScore * NameWeight + timeScore * TimeWeight;

        var isAccepted = confidence >= _minConfidence;
        var reason = isAccepted
            ? $"Matched (confidence={confidence:F3}, name={nameScore:F3}, time={timeScore:F3})"
            : $"Below threshold (confidence={confidence:F3} < {_minConfidence:F2}, name={nameScore:F3}, time={timeScore:F3})";

        return new MatchResult(kushEvent, nameScore, timeScore, confidence, isAccepted, reason);
    }

    /// <summary>
    /// Compute fuzzy similarity between two team names (0.0–1.0).
    /// Uses FuzzySharp WRatio (weighted ratio) — same approach as legacy Python (RapidFuzz).
    /// </summary>
    public static double ComputeNameSimilarity(string name1, string name2)
    {
        var n1 = TeamNormalizer.Normalize(name1);
        var n2 = TeamNormalizer.Normalize(name2);

        if (string.IsNullOrEmpty(n1) || string.IsNullOrEmpty(n2))
            return 0.0;

        if (n1 == n2)
            return 1.0;

        // FuzzySharp.Fuzz.WeightedRatio returns 0–100
        var ratio = Fuzz.WeightedRatio(n1, n2);
        return ratio / 100.0;
    }
}
