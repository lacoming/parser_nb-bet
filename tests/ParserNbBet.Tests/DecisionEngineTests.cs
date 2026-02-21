using ParserNbBet.Decision;
using ParserNbBet.Nb;
using Xunit;

namespace ParserNbBet.Tests;

public class DecisionEngineTests
{
    private static Match MakeMatch(double? kf1, double? kfX, double? kf2) =>
        new("TestLeague", "Home", "Away", DateTime.UtcNow, "slug", "soccer")
        {
            Odds1End = kf1,
            OddsXEnd = kfX,
            Odds2End = kf2,
        };

    // ── Missing odds ────────────────────────────────────────

    [Fact]
    public void NullOdds_ReturnsSkip()
    {
        var result = DecisionEngine.Evaluate(MakeMatch(null, 3.0, 2.0));
        Assert.Single(result.Decisions);
        Assert.Equal("skip", result.Decisions[0].BetType);
        Assert.False(result.AnyPasses);
    }

    [Fact]
    public void NullKf2_ReturnsSkip()
    {
        var result = DecisionEngine.Evaluate(MakeMatch(2.0, 3.0, null));
        Assert.Single(result.Decisions);
        Assert.Equal("skip", result.Decisions[0].BetType);
    }

    // ── Equal odds ──────────────────────────────────────────

    [Fact]
    public void EqualOdds_ReturnsSkip()
    {
        var result = DecisionEngine.Evaluate(MakeMatch(2.0, 3.0, 2.0));
        Assert.Single(result.Decisions);
        Assert.Equal("skip", result.Decisions[0].BetType);
    }

    // ── Home favourite (kf1 > kf2) ─────────────────────────

    [Fact]
    public void HomeFav_AllPass_WhenConditionsMet()
    {
        // kf1=3.0 (≤8), kfX=2.0, kf2=2.0 (≥1.4, ≥1.5)
        // kf1X = min(3.0, 2.0) = 2.0 (≥1.5)
        var result = DecisionEngine.Evaluate(MakeMatch(3.0, 2.0, 2.0));

        Assert.Equal(4, result.Decisions.Count);
        Assert.True(result.AnyPasses);

        var types = result.Decisions.Where(d => d.Passes).Select(d => d.BetType).ToList();
        Assert.Contains("1X", types);
        Assert.Contains("1", types);
        Assert.Contains("2", types);
        Assert.Contains("X", types);
    }

    [Fact]
    public void HomeFav_1X_Fails_WhenKf1Over8()
    {
        // kf1=9.0 > 8 → 1X fails, 1 fails, X fails; 2 still depends on kf2
        var result = DecisionEngine.Evaluate(MakeMatch(9.0, 2.0, 2.0));

        var d1x = result.Decisions.First(d => d.BetType == "1X");
        Assert.False(d1x.Passes);
        Assert.Contains(d1x.Reasons, r => r.Contains("kf1=9.00 > 8"));

        var d1 = result.Decisions.First(d => d.BetType == "1");
        Assert.False(d1.Passes);

        // "2" should still pass (kf2=2.0 ≥ 1.5)
        var d2 = result.Decisions.First(d => d.BetType == "2");
        Assert.True(d2.Passes);
    }

    [Fact]
    public void HomeFav_1X_Fails_WhenKf1XBelow1_5()
    {
        // kf1=2.0, kfX=1.3 → kf1X=min(2.0,1.3)=1.3 < 1.5
        // kf2=1.5
        var result = DecisionEngine.Evaluate(MakeMatch(2.0, 1.3, 1.5));

        var d1x = result.Decisions.First(d => d.BetType == "1X");
        Assert.False(d1x.Passes);
        Assert.Contains(d1x.Reasons, r => r.Contains("kf1X=1.30 < 1.5"));
    }

    [Fact]
    public void HomeFav_1X_Fails_WhenKfXNull()
    {
        // kfX = null → kf1X = null → 1X fails
        var result = DecisionEngine.Evaluate(MakeMatch(3.0, null, 2.0));

        var d1x = result.Decisions.First(d => d.BetType == "1X");
        Assert.False(d1x.Passes);
        Assert.Contains(d1x.Reasons, r => r.Contains("kf1X is null"));

        // "1" should still pass (kf1=3≤8, kf2=2≥1.4)
        var d1 = result.Decisions.First(d => d.BetType == "1");
        Assert.True(d1.Passes);
    }

    [Fact]
    public void HomeFav_2_Fails_WhenKf2Below1_5()
    {
        // kf2=1.4 < 1.5 → "2" fails
        var result = DecisionEngine.Evaluate(MakeMatch(3.0, 2.0, 1.4));

        var d2 = result.Decisions.First(d => d.BetType == "2");
        Assert.False(d2.Passes);

        // "1" should pass (kf1≤8, kf2≥1.4)
        var d1 = result.Decisions.First(d => d.BetType == "1");
        Assert.True(d1.Passes);
    }

    [Fact]
    public void HomeFav_1_Fails_WhenKf2Below1_4()
    {
        // kf2=1.3 < 1.4 → "1" fails, "1X" fails, "X" fails
        var result = DecisionEngine.Evaluate(MakeMatch(3.0, 2.0, 1.3));

        var d1 = result.Decisions.First(d => d.BetType == "1");
        Assert.False(d1.Passes);

        var d1x = result.Decisions.First(d => d.BetType == "1X");
        Assert.False(d1x.Passes);
    }

    [Fact]
    public void HomeFav_BoundaryValues_Kf1Exactly8()
    {
        // kf1=8.0 exactly ≤ 8 → should pass
        var result = DecisionEngine.Evaluate(MakeMatch(8.0, 2.0, 2.0));

        var d1 = result.Decisions.First(d => d.BetType == "1");
        Assert.True(d1.Passes);
    }

    [Fact]
    public void HomeFav_BoundaryValues_Kf2Exactly1_4()
    {
        // kf2=1.4 exactly ≥ 1.4 → "1" passes, but "2" fails (1.4 < 1.5)
        var result = DecisionEngine.Evaluate(MakeMatch(3.0, 2.0, 1.4));

        var d1 = result.Decisions.First(d => d.BetType == "1");
        Assert.True(d1.Passes);

        var d2 = result.Decisions.First(d => d.BetType == "2");
        Assert.False(d2.Passes);
    }

    // ── Away favourite (kf2 > kf1) ─────────────────────────

    [Fact]
    public void AwayFav_AllPass_WhenConditionsMet()
    {
        // kf1=2.0 (≥1.4, ≥1.5), kf2=3.0 (≤8)
        var result = DecisionEngine.Evaluate(MakeMatch(2.0, 3.5, 3.0));

        Assert.Equal(2, result.Decisions.Count);
        Assert.True(result.AnyPasses);

        var types = result.Decisions.Where(d => d.Passes).Select(d => d.BetType).ToList();
        Assert.Contains("2", types);
        Assert.Contains("1", types);
    }

    [Fact]
    public void AwayFav_2_Fails_WhenKf2Over8()
    {
        // kf2=9.0 > 8 → "2" fails
        var result = DecisionEngine.Evaluate(MakeMatch(2.0, 5.0, 9.0));

        var d2 = result.Decisions.First(d => d.BetType == "2");
        Assert.False(d2.Passes);
    }

    [Fact]
    public void AwayFav_1_Fails_WhenKf1Below1_5()
    {
        // kf1=1.4 < 1.5 → "1" fails
        var result = DecisionEngine.Evaluate(MakeMatch(1.4, 3.0, 3.0));

        var d1 = result.Decisions.First(d => d.BetType == "1");
        Assert.False(d1.Passes);
    }

    [Fact]
    public void AwayFav_2_Fails_WhenKf1Below1_4()
    {
        // kf1=1.3 < 1.4 → "2" fails
        var result = DecisionEngine.Evaluate(MakeMatch(1.3, 3.0, 3.0));

        var d2 = result.Decisions.First(d => d.BetType == "2");
        Assert.False(d2.Passes);
    }

    [Fact]
    public void AwayFav_BothPass_BoundaryKf1Exactly1_5()
    {
        // kf1=1.5 ≥ 1.5 → "1" passes; kf2=3.0 ≤ 8, kf1=1.5 ≥ 1.4 → "2" passes
        var result = DecisionEngine.Evaluate(MakeMatch(1.5, 3.0, 3.0));

        Assert.All(result.Decisions, d => Assert.True(d.Passes));
    }

    // ── Reasons populated ───────────────────────────────────

    [Fact]
    public void Reasons_ArePopulated()
    {
        var result = DecisionEngine.Evaluate(MakeMatch(3.0, 2.0, 2.0));
        Assert.All(result.Decisions, d => Assert.NotEmpty(d.Reasons));
    }
}
