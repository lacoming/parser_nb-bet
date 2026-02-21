using ParserNbBet.Nb;
using Xunit;

namespace ParserNbBet.Tests;

public class NbClientTests
{
    private const string SampleJson = """
    {
      "data": {
        "leagues": [
          {
            "1": "Англия",
            "3": "Премьер-лига",
            "4": [
              {
                "3": "arsenal-manchester-city-prognoz",
                "4": 1708646400000,
                "5": { "1": 2.10, "2": 3.50, "3": 3.20 },
                "6": { "1": 2.00, "2": 3.40, "3": 3.10 },
                "7": "Arsenal",
                "15": "Manchester City",
                "10": 2,
                "18": 1
              },
              {
                "3": "liverpool-chelsea-prognoz",
                "4": 1708650000000,
                "5": { "1": 1.85, "2": 4.00, "3": 3.50 },
                "6": { "1": 1.90, "2": 3.80, "3": 3.40 },
                "7": "Liverpool",
                "15": "Chelsea",
                "10": 3,
                "18": 0
              }
            ]
          },
          {
            "1": "Испания",
            "3": "Ла Лига",
            "4": [
              {
                "3": "real-madrid-barcelona-prognoz",
                "4": 1708660000000,
                "5": { "1": 2.50, "2": 2.80, "3": 3.10 },
                "6": null,
                "7": "Real Madrid",
                "15": "Barcelona"
              }
            ]
          }
        ]
      }
    }
    """;

    [Fact]
    public void ParseResponse_ReturnsCorrectMatchCount()
    {
        var matches = NbClient.ParseResponse(SampleJson, "soccer");
        Assert.Equal(3, matches.Count);
    }

    [Fact]
    public void ParseResponse_ParsesLeagueCorrectly()
    {
        var matches = NbClient.ParseResponse(SampleJson, "soccer");
        Assert.Equal("Англия. Премьер-лига", matches[0].League);
        Assert.Equal("Испания. Ла Лига", matches[2].League);
    }

    [Fact]
    public void ParseResponse_ParsesTeamsCorrectly()
    {
        var matches = NbClient.ParseResponse(SampleJson, "soccer");
        Assert.Equal("Arsenal", matches[0].TeamHome);
        Assert.Equal("Manchester City", matches[0].TeamAway);
    }

    [Fact]
    public void ParseResponse_ParsesTimestamp()
    {
        var matches = NbClient.ParseResponse(SampleJson, "soccer");
        // 1708646400000 ms = 2024-02-23 00:00:00 UTC
        var expected = DateTimeOffset.FromUnixTimeMilliseconds(1708646400000).UtcDateTime;
        Assert.Equal(expected, matches[0].StartTimeUtc);
    }

    [Fact]
    public void ParseResponse_ParsesEndOdds()
    {
        var matches = NbClient.ParseResponse(SampleJson, "soccer");
        Assert.Equal(2.10, matches[0].Odds1End);
        Assert.Equal(3.20, matches[0].OddsXEnd);
        Assert.Equal(3.50, matches[0].Odds2End);
    }

    [Fact]
    public void ParseResponse_ParsesStartOdds()
    {
        var matches = NbClient.ParseResponse(SampleJson, "soccer");
        Assert.Equal(2.00, matches[0].Odds1Start);
        Assert.Equal(3.10, matches[0].OddsXStart);
        Assert.Equal(3.40, matches[0].Odds2Start);
    }

    [Fact]
    public void ParseResponse_NullStartOdds_HandledGracefully()
    {
        var matches = NbClient.ParseResponse(SampleJson, "soccer");
        // Third match (Real Madrid vs Barcelona) has "6": null
        Assert.Null(matches[2].Odds1Start);
        Assert.Null(matches[2].OddsXStart);
        Assert.Null(matches[2].Odds2Start);
        // But end odds are present
        Assert.Equal(2.50, matches[2].Odds1End);
    }

    [Fact]
    public void ParseResponse_MatchKey_IsStable()
    {
        var matches = NbClient.ParseResponse(SampleJson, "soccer");
        var expected = "Англия. Премьер-лига|Arsenal|Manchester City|20240223";
        Assert.Equal(expected, matches[0].MatchKey);
    }

    [Fact]
    public void ParseResponse_Odds1XEnd_Derived()
    {
        var matches = NbClient.ParseResponse(SampleJson, "soccer");
        // Odds1End=2.10, OddsXEnd=3.20 => Odds1XEnd = min(2.10, 3.20) = 2.10
        Assert.Equal(2.10, matches[0].Odds1XEnd);
    }

    [Fact]
    public void ParseResponse_SetsSport()
    {
        var matches = NbClient.ParseResponse(SampleJson, "soccer");
        Assert.All(matches, m => Assert.Equal("soccer", m.Sport));
    }

    [Fact]
    public void ParseResponse_EmptyJson_ReturnsEmpty()
    {
        var matches = NbClient.ParseResponse("{}", "soccer");
        Assert.Empty(matches);
    }

    [Fact]
    public void ParseResponse_NoLeagues_ReturnsEmpty()
    {
        var matches = NbClient.ParseResponse("""{"data": {"leagues": []}}""", "soccer");
        Assert.Empty(matches);
    }

    [Fact]
    public void ParseResponse_SkipsMatchWithoutTeams()
    {
        var json = """
        {
          "data": {
            "leagues": [{
              "1": "Test",
              "3": "League",
              "4": [
                { "3": "slug", "4": 1708646400000, "7": "Home", "15": "" },
                { "3": "slug2", "4": 1708646400000, "7": "", "15": "Away" },
                { "3": "slug3", "4": 1708646400000, "7": "Home", "15": "Away", "5": {"1": 1.5, "2": 2.5, "3": 3.0} }
              ]
            }]
          }
        }
        """;
        var matches = NbClient.ParseResponse(json, "soccer");
        Assert.Single(matches);
        Assert.Equal("Home", matches[0].TeamHome);
    }

    [Fact]
    public void ParseResponse_StringOdds_ParsedCorrectly()
    {
        var json = """
        {
          "data": {
            "leagues": [{
              "1": "Test",
              "3": "League",
              "4": [{
                "3": "slug",
                "4": 1708646400000,
                "5": { "1": "2.10", "2": "3.50", "3": "3.20" },
                "7": "Home",
                "15": "Away"
              }]
            }]
          }
        }
        """;
        var matches = NbClient.ParseResponse(json, "soccer");
        Assert.Equal(2.10, matches[0].Odds1End);
        Assert.Equal(3.50, matches[0].Odds2End);
    }
}
