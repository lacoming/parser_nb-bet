using ParserNbBet.Kush;
using ParserNbBet.Nb;
using Xunit;

namespace ParserNbBet.Tests;

public class EventMatcherTests
{
    private static readonly DateTime BaseTime = new(2026, 3, 1, 15, 0, 0, DateTimeKind.Utc);

    private readonly EventMatcher _matcher = new(timeToleranceHours: 2, minConfidence: 0.80);

    private static Match MakeNbMatch(string home = "Barcelona", string away = "Real Madrid",
                                      DateTime? time = null, string league = "La Liga") =>
        new(league, home, away, time ?? BaseTime, "slug", "soccer");

    private static KushEvent MakeKushEvent(string home = "Барселона", string away = "Реал Мадрид",
                                            DateTime? time = null, string league = "Испания. Ла Лига") =>
        new("e1", league, home, away, time ?? BaseTime, "https://kush/e1");

    // ──────── Exact matches ────────

    [Fact]
    public void ExactSameNames_HighConfidence()
    {
        var nb = MakeNbMatch("Liverpool", "Arsenal");
        var kush = MakeKushEvent("Liverpool", "Arsenal");
        var result = _matcher.ScoreMatch(nb, kush);

        Assert.True(result.IsAccepted);
        Assert.True(result.Confidence >= 0.95);
        Assert.Equal(1.0, result.NameScore);
    }

    [Fact]
    public void ExactSameTime_TimeScoreIsOne()
    {
        var nb = MakeNbMatch();
        var kush = MakeKushEvent("Barcelona", "Real Madrid", BaseTime);
        var result = _matcher.ScoreMatch(nb, kush);

        Assert.Equal(1.0, result.TimeScore);
    }

    // ──────── Fuzzy name matching ────────

    [Fact]
    public void SimilarNames_AcceptedAboveThreshold()
    {
        var nb = MakeNbMatch("Manchester Utd", "Liverpool FC");
        var kush = MakeKushEvent("Manchester United", "Liverpool");
        var result = _matcher.ScoreMatch(nb, kush);

        Assert.True(result.NameScore > 0.7);
        Assert.True(result.IsAccepted);
    }

    [Fact]
    public void CompletelyDifferentNames_Rejected()
    {
        var nb = MakeNbMatch("Barcelona", "Real Madrid");
        var kush = MakeKushEvent("Bayern Munich", "Borussia Dortmund");
        var result = _matcher.ScoreMatch(nb, kush);

        Assert.False(result.IsAccepted);
        Assert.True(result.NameScore < 0.5);
    }

    // ──────── Cyrillic ↔ Latin ────────

    [Fact]
    public void CyrillicVsLatin_FuzzyMatch()
    {
        // Спартак ≈ Spartak after transliteration
        var nb = MakeNbMatch("Spartak Moscow", "Zenit");
        var kush = MakeKushEvent("Спартак Москва", "Зенит");
        var result = _matcher.ScoreMatch(nb, kush);

        // After transliteration both should be very similar
        Assert.True(result.NameScore > 0.7, $"NameScore was {result.NameScore:F3}");
    }

    // ──────── Team swap detection ────────

    [Fact]
    public void SwappedHomeAway_StillMatches()
    {
        var nb = MakeNbMatch("Team A", "Team B");
        var kush = MakeKushEvent("Team B", "Team A");
        var result = _matcher.ScoreMatch(nb, kush);

        Assert.True(result.IsAccepted);
        Assert.True(result.NameScore >= 0.99);
    }

    // ──────── Time tolerance ────────

    [Fact]
    public void WithinTimeTolerance_Accepted()
    {
        var nb = MakeNbMatch(time: BaseTime);
        var kush = MakeKushEvent("Barcelona", "Real Madrid", BaseTime.AddHours(1));
        var result = _matcher.ScoreMatch(nb, kush);

        Assert.True(result.TimeScore > 0.0);
        Assert.Equal(0.5, result.TimeScore, 2);
    }

    [Fact]
    public void AtTimeBoundary_TimeScoreZero()
    {
        var nb = MakeNbMatch(time: BaseTime);
        var kush = MakeKushEvent("Barcelona", "Real Madrid", BaseTime.AddHours(2));
        var result = _matcher.ScoreMatch(nb, kush);

        Assert.Equal(0.0, result.TimeScore, 2);
    }

    [Fact]
    public void ExceedsTimeTolerance_Rejected()
    {
        var nb = MakeNbMatch(time: BaseTime);
        var kush = MakeKushEvent("Barcelona", "Real Madrid", BaseTime.AddHours(3));
        var result = _matcher.ScoreMatch(nb, kush);

        Assert.False(result.IsAccepted);
        Assert.Equal(0.0, result.Confidence);
    }

    // ──────── FindBestMatch ────────

    [Fact]
    public void FindBestMatch_PicksHighestConfidence()
    {
        var nb = MakeNbMatch("Chelsea", "Arsenal");
        var events = new[]
        {
            MakeKushEvent("Bayern", "Dortmund"),
            MakeKushEvent("Chelsea FC", "Arsenal FC"),
            MakeKushEvent("Chelsea", "Arsenal", BaseTime.AddHours(1.5)),
        };

        var result = _matcher.FindBestMatch(nb, events);

        Assert.True(result.IsAccepted);
        // Should pick the exact-time match (index 1) as best
        Assert.Equal("Chelsea FC", result.KushEvent!.TeamHome);
    }

    [Fact]
    public void FindBestMatch_EmptyList_NoMatch()
    {
        var nb = MakeNbMatch();
        var result = _matcher.FindBestMatch(nb, []);

        Assert.False(result.IsAccepted);
        Assert.Null(result.KushEvent);
        Assert.Contains("No Kush events available", result.Reason);
    }

    [Fact]
    public void FindBestMatch_AllBelowThreshold_NotAccepted()
    {
        var nb = MakeNbMatch("Unique Team Alpha", "Unique Team Beta");
        var events = new[]
        {
            MakeKushEvent("Completely Different X", "Completely Different Y"),
        };

        var result = _matcher.FindBestMatch(nb, events);
        Assert.False(result.IsAccepted);
    }

    // ──────── Confidence formula ────────

    [Fact]
    public void ConfidenceFormula_WeightedCorrectly()
    {
        // nameScore * 0.7 + timeScore * 0.3
        var nb = MakeNbMatch("Liverpool", "Arsenal");
        var kush = MakeKushEvent("Liverpool", "Arsenal", BaseTime);

        var result = _matcher.ScoreMatch(nb, kush);

        // Both should be 1.0, so confidence = 1.0
        var expected = result.NameScore * 0.70 + result.TimeScore * 0.30;
        Assert.Equal(expected, result.Confidence, 3);
    }

    // ──────── ComputeNameSimilarity edge cases ────────

    [Fact]
    public void ComputeNameSimilarity_EmptyStrings_Zero()
    {
        Assert.Equal(0.0, EventMatcher.ComputeNameSimilarity("", "Arsenal"));
        Assert.Equal(0.0, EventMatcher.ComputeNameSimilarity("Arsenal", ""));
    }

    [Fact]
    public void ComputeNameSimilarity_IdenticalNames_One()
    {
        Assert.Equal(1.0, EventMatcher.ComputeNameSimilarity("Arsenal", "Arsenal"));
    }

    [Fact]
    public void ComputeNameSimilarity_CaseInsensitive()
    {
        Assert.Equal(1.0, EventMatcher.ComputeNameSimilarity("ARSENAL", "arsenal"));
    }

    // ──────── Custom threshold ────────

    [Fact]
    public void CustomThreshold_LowerMinConfidence_Accepts()
    {
        var lenientMatcher = new EventMatcher(timeToleranceHours: 2, minConfidence: 0.50);
        var nb = MakeNbMatch("Manchester City", "Tottenham");
        var kush = MakeKushEvent("Man City", "Tottenham Hotspur", BaseTime.AddHours(1));
        var result = lenientMatcher.ScoreMatch(nb, kush);

        Assert.True(result.IsAccepted);
    }
}
