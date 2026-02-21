using ParserNbBet.Kush;
using Xunit;

namespace ParserNbBet.Tests;

public class KushClientTests
{
    // ── ExtractEventId ──────────────────────────────────────────

    [Fact]
    public void ExtractEventId_StandardPath()
    {
        var id = KushClient.ExtractEventId("/event/6304590-sheffild-yunayted-norvich-siti");
        Assert.Equal("6304590", id);
    }

    [Fact]
    public void ExtractEventId_OnlyId()
    {
        var id = KushClient.ExtractEventId("/event/12345");
        Assert.Equal("12345", id);
    }

    [Fact]
    public void ExtractEventId_EmptyString()
    {
        var id = KushClient.ExtractEventId("");
        Assert.Equal("", id);
    }

    [Fact]
    public void ExtractEventId_NoEventPrefix()
    {
        var id = KushClient.ExtractEventId("/some/other/path");
        Assert.Equal("", id);
    }

    [Fact]
    public void ExtractEventId_FullUrl()
    {
        var id = KushClient.ExtractEventId("https://kushvsporte.ru/event/999-team-a-team-b");
        Assert.Equal("999", id);
    }

    // ── ParseKushDateTime ───────────────────────────────────────

    [Fact]
    public void ParseDateTime_FullFormat()
    {
        var dt = KushClient.ParseKushDateTime("09.12.2025 22.45");
        // MSK (UTC+3) → UTC: 22:45 - 3 = 19:45
        Assert.Equal(new DateTime(2025, 12, 9, 19, 45, 0), dt);
    }

    [Fact]
    public void ParseDateTime_ColonFormat()
    {
        var dt = KushClient.ParseKushDateTime("15.03.2026 14:30");
        Assert.Equal(new DateTime(2026, 3, 15, 11, 30, 0), dt);
    }

    [Fact]
    public void ParseDateTime_Empty()
    {
        var dt = KushClient.ParseKushDateTime("");
        Assert.Equal(DateTime.MinValue, dt);
    }

    [Fact]
    public void ParseDateTime_Null()
    {
        var dt = KushClient.ParseKushDateTime(null!);
        Assert.Equal(DateTime.MinValue, dt);
    }

    // ── ExtractCouponIds ────────────────────────────────────────

    [Fact]
    public void ExtractCouponIds_Standard()
    {
        var (eid, cfid) = KushClient.ExtractCouponIds("/coupon/add-coupon?eid=123&cfid=456");
        Assert.Equal("123", eid);
        Assert.Equal("456", cfid);
    }

    [Fact]
    public void ExtractCouponIds_OnlyEid()
    {
        var (eid, cfid) = KushClient.ExtractCouponIds("/coupon/add-coupon?eid=999");
        Assert.Equal("999", eid);
        Assert.Equal("", cfid);
    }

    [Fact]
    public void ExtractCouponIds_Empty()
    {
        var (eid, cfid) = KushClient.ExtractCouponIds("");
        Assert.Equal("", eid);
        Assert.Equal("", cfid);
    }

    [Fact]
    public void ExtractCouponIds_ExtraParams()
    {
        var (eid, cfid) = KushClient.ExtractCouponIds("/coupon/add-coupon?eid=100&cfid=200&extra=300");
        Assert.Equal("100", eid);
        Assert.Equal("200", cfid);
    }

    // ── ParseEventsHtml ─────────────────────────────────────────

    [Fact]
    public void ParseEventsHtml_WithTeamLink()
    {
        var html = """
            <div class="row">
                <div class="medium-text">09.12.2025 22.45</div>
                <div class="d-inline-block d-md-block">Пн</div>
                <a class="d-block" href="/event/6304590-team-a-team-b">
                    <div class="medium-text">Шеффилд Юнайтед</div>
                    <div class="medium-text">Норвич Сити</div>
                </a>
            </div>
            """;

        var events = KushClient.ParseEventsHtml(html);
        Assert.Single(events);
        Assert.Equal("6304590", events[0].EventId);
        Assert.Equal("Шеффилд Юнайтед", events[0].TeamHome);
        Assert.Equal("Норвич Сити", events[0].TeamAway);
    }

    [Fact]
    public void ParseEventsHtml_MultipleEvents()
    {
        var html = """
            <div class="row">
                <div class="medium-text">09.12.2025 18.00</div>
                <a class="d-block" href="/event/100-a-b">
                    <div class="medium-text">Team A</div>
                    <div class="medium-text">Team B</div>
                </a>
            </div>
            <div class="row">
                <div class="medium-text">10.12.2025 20.00</div>
                <a class="d-block" href="/event/200-c-d">
                    <div class="medium-text">Team C</div>
                    <div class="medium-text">Team D</div>
                </a>
            </div>
            """;

        var events = KushClient.ParseEventsHtml(html);
        Assert.Equal(2, events.Count);
        Assert.Equal("100", events[0].EventId);
        Assert.Equal("200", events[1].EventId);
    }

    [Fact]
    public void ParseEventsHtml_NoEvents()
    {
        var html = "<div>Nothing here</div>";
        var events = KushClient.ParseEventsHtml(html);
        Assert.Empty(events);
    }

    [Fact]
    public void ParseEventsHtml_MissingLink()
    {
        var html = """
            <div class="row">
                <div class="medium-text">09.12.2025</div>
            </div>
            """;

        var events = KushClient.ParseEventsHtml(html);
        Assert.Empty(events);
    }

    // ── ParseOddsHtml ───────────────────────────────────────────

    [Fact]
    public void ParseOddsHtml_SingleOdd()
    {
        var html = """
            <button class="coefLink" url="/coupon/add-coupon?eid=100&cfid=200">
                <div class="d-sm-none">П1</div>
                <span>1.85</span>
            </button>
            """;

        var odds = KushClient.ParseOddsHtml(html);
        Assert.Single(odds);
        Assert.True(odds.ContainsKey("П1"));
        Assert.Equal(1.85, odds["П1"].Value);
        Assert.Equal("100", odds["П1"].EventId);
        Assert.Equal("200", odds["П1"].CoefficientId);
    }

    [Fact]
    public void ParseOddsHtml_MultipleOdds()
    {
        var html = """
            <button class="coefLink" url="/coupon/add-coupon?eid=1&cfid=10">
                <div class="d-sm-none">П1</div>
                <span>2.10</span>
            </button>
            <button class="coefLink" url="/coupon/add-coupon?eid=1&cfid=11">
                <div class="d-sm-none">Х</div>
                <span>3.40</span>
            </button>
            <button class="coefLink" url="/coupon/add-coupon?eid=1&cfid=12">
                <div class="d-sm-none">П2</div>
                <span>3.10</span>
            </button>
            """;

        var odds = KushClient.ParseOddsHtml(html);
        Assert.Equal(3, odds.Count);
        Assert.Equal(2.10, odds["П1"].Value);
        Assert.Equal(3.40, odds["Х"].Value);
        Assert.Equal(3.10, odds["П2"].Value);
    }

    [Fact]
    public void ParseOddsHtml_NoButtons()
    {
        var html = "<div>No odds here</div>";
        var odds = KushClient.ParseOddsHtml(html);
        Assert.Empty(odds);
    }

    [Fact]
    public void ParseOddsHtml_InvalidOddsSkipped()
    {
        var html = """
            <button class="coefLink" url="">
                <div class="d-sm-none">П1</div>
                <span>not_a_number</span>
            </button>
            <button class="coefLink" url="/coupon/add-coupon?eid=1&cfid=2">
                <div class="d-sm-none">П2</div>
                <span>2.50</span>
            </button>
            """;

        var odds = KushClient.ParseOddsHtml(html);
        Assert.Single(odds);
        Assert.True(odds.ContainsKey("П2"));
    }

    // ── ParseEventsHtml edge cases ──────────────────────────────

    [Fact]
    public void ParseEventsHtml_HtmlEntitiesDecoded()
    {
        var html = """
            <div class="row">
                <div class="medium-text">01.01.2026 12.00</div>
                <a class="d-block" href="/event/555-x-y">
                    <div class="medium-text">FC K&ouml;ln</div>
                    <div class="medium-text">Bayern M&uuml;nchen</div>
                </a>
            </div>
            """;

        var events = KushClient.ParseEventsHtml(html);
        Assert.Single(events);
        Assert.Equal("FC Köln", events[0].TeamHome);
        Assert.Equal("Bayern München", events[0].TeamAway);
    }
}
