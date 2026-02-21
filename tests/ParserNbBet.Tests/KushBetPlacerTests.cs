using ParserNbBet.Config;
using ParserNbBet.Decision;
using ParserNbBet.Kush;
using ParserNbBet.Nb;
using Xunit;

namespace ParserNbBet.Tests;

public class KushBetPlacerTests
{
    // ── CalculateRatio ──────────────────────────────────────────────

    [Fact]
    public void CalculateRatio_StandardCase()
    {
        // KfKush * (1 + ROI) / KfNB
        // 2.0 * (1 + 0.05) / 1.8 = 2.1 / 1.8 = 1.1667
        var ratio = KushBetPlacer.CalculateRatio(2.0, 1.8, 0.05);
        Assert.Equal(1.1667, ratio, 3);
    }

    [Fact]
    public void CalculateRatio_ExactThreshold()
    {
        // 1.9 * 1.05 / 1.9 = 1.05 — below default threshold 1.10
        var ratio = KushBetPlacer.CalculateRatio(1.9, 1.9, 0.05);
        Assert.Equal(1.05, ratio, 3);
    }

    [Fact]
    public void CalculateRatio_ZeroNbOdds_ReturnsZero()
    {
        var ratio = KushBetPlacer.CalculateRatio(2.0, 0, 0.05);
        Assert.Equal(0, ratio);
    }

    [Fact]
    public void CalculateRatio_HighKushOdds_PassesThreshold()
    {
        // 3.5 * 1.05 / 3.0 = 1.225 > 1.10
        var ratio = KushBetPlacer.CalculateRatio(3.5, 3.0, 0.05);
        Assert.True(ratio > 1.10);
    }

    [Fact]
    public void CalculateRatio_LowKushOdds_FailsThreshold()
    {
        // 1.5 * 1.05 / 1.8 = 0.875 < 1.10
        var ratio = KushBetPlacer.CalculateRatio(1.5, 1.8, 0.05);
        Assert.True(ratio < 1.10);
    }

    [Fact]
    public void CalculateRatio_ZeroRoi()
    {
        // 2.0 * 1.0 / 1.8 = 1.1111
        var ratio = KushBetPlacer.CalculateRatio(2.0, 1.8, 0);
        Assert.Equal(1.1111, ratio, 3);
    }

    // ── GetThreshold ────────────────────────────────────────────────

    [Fact]
    public void GetThreshold_DefaultLeague_ReturnsDefault()
    {
        var placer = CreatePlacer();
        Assert.Equal(1.10, placer.GetThreshold("Random League"));
    }

    [Fact]
    public void GetThreshold_BigLeague_ReturnsLower()
    {
        var placer = CreatePlacer(bigLeagues: ["Premier League", "La Liga"]);
        Assert.Equal(1.05, placer.GetThreshold("English Premier League"));
    }

    [Fact]
    public void GetThreshold_BigLeague_CaseInsensitive()
    {
        var placer = CreatePlacer(bigLeagues: ["premier league"]);
        Assert.Equal(1.05, placer.GetThreshold("PREMIER LEAGUE"));
    }

    [Fact]
    public void GetThreshold_NoBigLeagues_AlwaysDefault()
    {
        var placer = CreatePlacer(bigLeagues: []);
        Assert.Equal(1.10, placer.GetThreshold("Premier League"));
    }

    // ── ResolveKushBetType ──────────────────────────────────────────

    [Fact]
    public void ResolveKushBetType_StandardMapping_1()
    {
        var placer = CreatePlacer();
        Assert.Equal("П1", placer.ResolveKushBetType("1", null));
    }

    [Fact]
    public void ResolveKushBetType_StandardMapping_2()
    {
        var placer = CreatePlacer();
        Assert.Equal("П2", placer.ResolveKushBetType("2", null));
    }

    [Fact]
    public void ResolveKushBetType_StandardMapping_X()
    {
        var placer = CreatePlacer();
        Assert.Equal("Ничья", placer.ResolveKushBetType("X", null));
    }

    [Fact]
    public void ResolveKushBetType_StandardMapping_1X()
    {
        var placer = CreatePlacer();
        Assert.Equal("1X", placer.ResolveKushBetType("1X", null));
    }

    [Fact]
    public void ResolveKushBetType_LeagueSetting_OverridesDefault()
    {
        var placer = CreatePlacer();
        var setting = new LeagueSetting { BetTypeKush = "ТБ (2.50)" };
        Assert.Equal("ТБ (2.50)", placer.ResolveKushBetType("1", setting));
    }

    // ── ExtractFormTokens ───────────────────────────────────────────

    [Fact]
    public void ExtractFormTokens_ValidForm_ExtractsAll()
    {
        var html = """
            <div>
                <form action="/coupon/create-coupon" method="post">
                    <input type="hidden" name="_csrf" value="abc123" />
                    <input type="hidden" name="Coupon[eid]" value="999" />
                    <input type="hidden" name="Coupon[cfid]" value="555" />
                    <input type="submit" name="addReviewButton" value="Submit" />
                </form>
            </div>
            """;

        var tokens = KushBetPlacer.ExtractFormTokens(html);
        Assert.NotNull(tokens);
        Assert.Equal("abc123", tokens["_csrf"]);
        Assert.Equal("999", tokens["Coupon[eid]"]);
        Assert.Equal("555", tokens["Coupon[cfid]"]);
    }

    [Fact]
    public void ExtractFormTokens_NoForm_ReturnsNull()
    {
        var html = "<div>No form here</div>";
        var tokens = KushBetPlacer.ExtractFormTokens(html);
        Assert.Null(tokens);
    }

    [Fact]
    public void ExtractFormTokens_EmptyHtml_ReturnsNull()
    {
        var tokens = KushBetPlacer.ExtractFormTokens("");
        Assert.Null(tokens);
    }

    [Fact]
    public void ExtractFormTokens_FormWithoutInputs_ReturnsNull()
    {
        var html = """<form action="/coupon/create-coupon"><p>No inputs</p></form>""";
        var tokens = KushBetPlacer.ExtractFormTokens(html);
        Assert.Null(tokens);
    }

    // ── BetResult ───────────────────────────────────────────────────

    [Fact]
    public void BetResult_DryRun_ToString()
    {
        var result = new BetResult(true, true, "1X", 1.8, 2.1, 1.225, 100, "ev123", "Dry-run: ok");
        var str = result.ToString();
        Assert.Contains("[DRY-RUN]", str);
        Assert.Contains("1X", str);
    }

    [Fact]
    public void BetResult_Success_ToString()
    {
        var result = new BetResult(true, false, "1", 1.8, 2.0, 1.17, 100, "ev123", "Placed");
        var str = result.ToString();
        Assert.Contains("[OK]", str);
    }

    [Fact]
    public void BetResult_Failed_ToString()
    {
        var result = BetResult.Failed("No odds", "2", "ev456");
        var str = result.ToString();
        Assert.Contains("[FAIL]", str);
        Assert.Contains("No odds", str);
    }

    // ── Helpers ─────────────────────────────────────────────────────

    private static KushBetPlacer CreatePlacer(List<string>? bigLeagues = null)
    {
        var kushConfig = new KushConfig { DryRun = true, DefaultStake = 100 };
        var thresholds = new ThresholdConfig
        {
            Roi = 0.05,
            DefaultRatio = 1.10,
            BigLeagueRatio = 1.05,
            BigLeagues = bigLeagues ?? []
        };

        // Use a fake KushClient (won't be called in these tests)
        var session = new KushSession(kushConfig);
        var client = new KushClient(session, kushConfig);

        return new KushBetPlacer(client, kushConfig, thresholds, "nonexistent_path");
    }
}
