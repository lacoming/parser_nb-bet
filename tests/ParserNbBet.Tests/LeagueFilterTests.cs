using ParserNbBet.Decision;
using ParserNbBet.Nb;
using Xunit;

namespace ParserNbBet.Tests;

public class LeagueFilterTests
{
    private static Match MakeMatch(string league) =>
        new(league, "Home", "Away", DateTime.UtcNow, "slug", "soccer")
        {
            Odds1End = 2.0,
            OddsXEnd = 3.0,
            Odds2End = 3.5,
        };

    private static LeagueSetting MakeSetting(params string[] leagues) =>
        new()
        {
            StrategyId = 1,
            Sport = "футбол",
            Leagues = leagues.ToList(),
            BetTypeNb = "МП",
            BetTypeKush = "П1",
        };

    [Fact]
    public void Filter_KeepsMatchingLeagues()
    {
        var settings = new List<LeagueSetting>
        {
            MakeSetting("Англия. Премьер-Лига", "Испания. Ла Лига")
        };

        var filter = new LeagueFilter(settings);
        var matches = new List<Match>
        {
            MakeMatch("Англия. Премьер-Лига"),
            MakeMatch("Германия. Бундеслига"),
            MakeMatch("Испания. Ла Лига"),
        };

        var result = filter.Filter(matches);
        Assert.Equal(2, result.Count);
        Assert.Equal("Англия. Премьер-Лига", result[0].Match.League);
        Assert.Equal("Испания. Ла Лига", result[1].Match.League);
    }

    [Fact]
    public void Filter_NoMatch_ReturnsEmpty()
    {
        var settings = new List<LeagueSetting> { MakeSetting("Англия. Премьер-Лига") };
        var filter = new LeagueFilter(settings);
        var matches = new List<Match> { MakeMatch("Германия. Бундеслига") };

        var result = filter.Filter(matches);
        Assert.Empty(result);
    }

    [Fact]
    public void Filter_CaseInsensitive()
    {
        var settings = new List<LeagueSetting> { MakeSetting("англия. премьер-лига") };
        var filter = new LeagueFilter(settings);
        var matches = new List<Match> { MakeMatch("Англия. Премьер-Лига") };

        var result = filter.Filter(matches);
        Assert.Single(result);
    }

    [Fact]
    public void Filter_UsesRenameDict()
    {
        var settings = new List<LeagueSetting> { MakeSetting("Англия. Премьер-Лига") };
        var renames = new Dictionary<string, string>
        {
            ["Чемпионат Англии. Премьер-лига"] = "Англия. Премьер-Лига"
        };

        var filter = new LeagueFilter(settings, renames);
        var matches = new List<Match> { MakeMatch("Чемпионат Англии. Премьер-лига") };

        var result = filter.Filter(matches);
        Assert.Single(result);
    }

    [Fact]
    public void Filter_AttachesSetting()
    {
        var setting = MakeSetting("Англия. Премьер-Лига");
        var filter = new LeagueFilter([setting]);
        var matches = new List<Match> { MakeMatch("Англия. Премьер-Лига") };

        var result = filter.Filter(matches);
        Assert.Equal(setting, result[0].Setting);
    }

    [Fact]
    public void NormalizeLeague_ReturnsRenamedOrOriginal()
    {
        var renames = new Dictionary<string, string>
        {
            ["Чемпионат Австралии"] = "Австралия. Australian Championship"
        };
        var filter = new LeagueFilter([], renames);

        Assert.Equal("Австралия. Australian Championship", filter.NormalizeLeague("Чемпионат Австралии"));
        Assert.Equal("Some League", filter.NormalizeLeague("Some League"));
    }
}
