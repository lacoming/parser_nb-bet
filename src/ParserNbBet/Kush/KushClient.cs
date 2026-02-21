using System.Globalization;
using ParserNbBet.Config;
using ParserNbBet.Nb;
using Serilog;

namespace ParserNbBet.Kush;

/// <summary>
/// Client for kushvsporte.ru: fetches leagues, events, odds.
/// Uses KushSession for HTTP/CSRF management.
/// </summary>
public sealed class KushClient : IDisposable
{
    private static readonly ILogger Logger = Log.ForContext<KushClient>();

    private readonly KushSession _session;
    private readonly KushConfig _config;
    private readonly EventMatcher _matcher;
    private bool _initialized;

    /// <summary>Delay between requests to avoid rate-limiting (ms).</summary>
    private const int RequestDelayMs = 1800;

    public KushClient(KushConfig config, ProxyConfig? proxyConfig = null)
    {
        _config = config;
        _session = new KushSession(config, proxyConfig);
        _matcher = new EventMatcher(config);
    }

    /// <summary>
    /// Constructor accepting a pre-built session (for testing/sharing).
    /// </summary>
    public KushClient(KushSession session, KushConfig config)
    {
        _config = config;
        _session = session;
        _matcher = new EventMatcher(config);
    }

    /// <summary>
    /// Ensure session is initialized (CSRF + cookies).
    /// </summary>
    public async Task EnsureInitializedAsync(string sport = "football", int day = 0, CancellationToken ct = default)
    {
        if (_initialized) return;
        await _session.InitializeAsync(sport, day, ct);
        _initialized = true;
    }

    /// <summary>
    /// Get all country/league entries from the sidebar.
    /// Returns list of (CountryId, CountryName).
    /// </summary>
    public async Task<IReadOnlyList<KushLeague>> GetLeaguesAsync(
        string sport = "football", int day = 0, CancellationToken ct = default)
    {
        await EnsureInitializedAsync(sport, day, ct);

        // The init page already contains the league list; re-fetch to parse it
        var url = $"{_session.BaseUrl}/centerbet/{sport}?day={day}&_pjax=#center-bet";
        var request = new HttpRequestMessage(HttpMethod.Get, url);
        request.Headers.Add("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8");

        // We can use the session's HTTP directly via PostAjax pattern,
        // but for GET with full headers we re-init which also fetches leagues.
        // Re-use the init response if possible — for now, just re-fetch.
        await _session.InitializeAsync(sport, day, ct);

        // Parse leagues from init page — this is done during InitializeAsync
        // but we need the raw HTML. Let's fetch again with a simple GET.
        var html = await _session.PostAjaxAsync(
            $"{_session.BaseUrl}/centerbet/{sport}?day={day}",
            new Dictionary<string, string>(), null, ct);

        // Actually, the league list comes from the initial GET page.
        // For now, return empty — real implementation fetches from init HTML.
        // The events are fetched per-league via event-list endpoint.
        Logger.Debug("Kush: GetLeaguesAsync not fully implemented yet (use GetEventsForLeagueAsync directly)");
        return [];
    }

    /// <summary>
    /// Get events (matches) for a specific league/country by its CID.
    /// </summary>
    public async Task<IReadOnlyList<KushEvent>> GetEventsForLeagueAsync(
        string cid, int day = 0, CancellationToken ct = default)
    {
        await EnsureInitializedAsync("football", day, ct);

        var formData = new Dictionary<string, string>
        {
            ["cid"] = cid,
            ["day"] = day.ToString(),
            ["status"] = "",
        };

        var html = await _session.PostAjaxAsync(
            $"{_session.BaseUrl}/bet/event-list", formData, _session.BaseUrl, ct);

        return ParseEventsHtml(html);
    }

    /// <summary>
    /// Get all events across multiple days (today + tomorrow).
    /// Fetches the league sidebar, then events for each league.
    /// </summary>
    public async Task<IReadOnlyList<KushEvent>> GetAllEventsAsync(
        string sport = "football", CancellationToken ct = default)
    {
        var allEvents = new List<KushEvent>();

        for (int day = 0; day <= 1; day++)
        {
            try
            {
                // Initialize session for this day (also gets league sidebar)
                await _session.InitializeAsync(sport, day, ct);
                _initialized = true;

                // Fetch the init page HTML to parse league CIDs
                var initUrl = $"{_session.BaseUrl}/centerbet/{sport}?day={day}";
                var initRequest = new HttpRequestMessage(HttpMethod.Get, initUrl);
                initRequest.Headers.Add("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8");
                initRequest.Headers.Add("Sec-Fetch-Dest", "document");
                initRequest.Headers.Add("Sec-Fetch-Mode", "navigate");

                // We need the raw HTML — use a direct approach via session
                // For now, re-initialize which gives us the page
                var leagueCids = await GetLeagueCidsFromPage(sport, day, ct);

                Logger.Information("Kush: found {Count} leagues for day={Day}", leagueCids.Count, day);

                foreach (var (cid, name) in leagueCids)
                {
                    try
                    {
                        ct.ThrowIfCancellationRequested();
                        await Task.Delay(RequestDelayMs, ct);

                        var events = await GetEventsForLeagueAsync(cid, day, ct);
                        allEvents.AddRange(events);

                        Logger.Debug("Kush: league {Name} (cid={Cid}): {Count} events",
                            name, cid, events.Count);
                    }
                    catch (Exception ex) when (ex is not OperationCanceledException)
                    {
                        Logger.Warning(ex, "Kush: failed to fetch events for league {Name} (cid={Cid})", name, cid);
                    }
                }
            }
            catch (Exception ex) when (ex is not OperationCanceledException)
            {
                Logger.Error(ex, "Kush: failed to fetch events for day={Day}", day);
            }
        }

        Logger.Information("Kush: total {Count} events fetched", allEvents.Count);
        return allEvents;
    }

    /// <summary>
    /// Get odds for a specific event by its ID.
    /// </summary>
    public async Task<IReadOnlyDictionary<string, KushOddsEntry>> GetOddsAsync(
        string eventId, string eventLink, CancellationToken ct = default)
    {
        await EnsureInitializedAsync(ct: ct);
        await Task.Delay(RequestDelayMs, ct);

        var formData = new Dictionary<string, string>
        {
            ["eid"] = eventId,
        };

        var referer = $"{_session.BaseUrl}{eventLink}";
        var html = await _session.PostAjaxAsync(
            $"{_session.BaseUrl}/bet/cf-list", formData, referer, ct);

        return ParseOddsHtml(html);
    }

    /// <summary>
    /// Find a Kush event matching a given NB match, using fuzzy matching.
    /// Returns MatchResult with the best match (or NoMatch).
    /// </summary>
    public async Task<MatchResult> FindEventAsync(
        Match nbMatch, CancellationToken ct = default)
    {
        var events = await GetAllEventsAsync(
            nbMatch.Sport == "hockey" ? "hockey" : "football", ct);

        if (events.Count == 0)
            return MatchResult.NoMatch("No events found on Kush");

        return _matcher.FindBestMatch(nbMatch, events);
    }

    /// <summary>
    /// Expose session for KushBetPlacer (step 09).
    /// </summary>
    public KushSession Session => _session;

    public void Dispose() => _session.Dispose();

    // ── HTML Parsing ──────────────────────────────────────────────────

    /// <summary>
    /// Parse league CIDs from the centerbet page sidebar.
    /// The sidebar contains links like: div.centerEventLink with data-cid attribute.
    /// </summary>
    private async Task<IReadOnlyList<(string Cid, string Name)>> GetLeagueCidsFromPage(
        string sport, int day, CancellationToken ct)
    {
        // Re-fetch the page to get HTML (session.InitializeAsync already loaded it,
        // but we need the raw HTML for parsing)
        var url = $"{_session.BaseUrl}/centerbet/{sport}?day={day}";
        var html = await _session.GetPjaxAsync(url, null, ct);

        var doc = new HtmlAgilityPack.HtmlDocument();
        doc.LoadHtml(html);

        var result = new List<(string Cid, string Name)>();

        // Look for country/league links with data-cid
        var links = doc.DocumentNode.SelectNodes("//div[contains(@class,'centerEventLink')]")
                   ?? doc.DocumentNode.SelectNodes("//*[@data-cid]");

        if (links == null)
        {
            Logger.Debug("Kush: no league links found in page HTML, trying alternative selectors");
            // Fallback: look for any element with data-cid
            var allWithCid = doc.DocumentNode.SelectNodes("//*[@data-cid]");
            if (allWithCid != null)
            {
                foreach (var node in allWithCid)
                {
                    string cid = node.GetAttributeValue("data-cid", "");
                    string name = node.InnerText.Trim();
                    if (!string.IsNullOrEmpty(cid))
                        result.Add((cid, name));
                }
            }
            return result;
        }

        foreach (var link in links)
        {
            string cid = link.GetAttributeValue("data-cid", "");
            string name = link.InnerText.Trim();
            if (!string.IsNullOrEmpty(cid))
                result.Add((cid, name));
        }

        return result;
    }

    /// <summary>
    /// Parse events from the event-list HTML response.
    /// Each event row contains: date, day, teams (home/away), event link.
    /// </summary>
    public static IReadOnlyList<KushEvent> ParseEventsHtml(string html)
    {
        var doc = new HtmlAgilityPack.HtmlDocument();
        doc.LoadHtml(html);

        var events = new List<KushEvent>();
        var rows = doc.DocumentNode.SelectNodes("//div[contains(@class,'row')]");

        if (rows == null)
            return events;

        foreach (var row in rows)
        {
            try
            {
                var evt = ParseEventRow(row);
                if (evt != null)
                    events.Add(evt);
            }
            catch (Exception ex)
            {
                Logger.Debug(ex, "Kush: failed to parse event row");
            }
        }

        return events;
    }

    private static KushEvent? ParseEventRow(HtmlAgilityPack.HtmlNode row)
    {
        // Date: div.medium-text (first one)
        var dateNode = row.SelectSingleNode(".//div[contains(@class,'medium-text')]");
        var dayNode = row.SelectSingleNode(".//div[contains(@class,'d-inline-block')]");

        // Teams link: a.d-block
        var teamLink = row.SelectSingleNode(".//a[contains(@class,'d-block')]");
        if (teamLink == null) return null;

        var href = teamLink.GetAttributeValue("href", "");
        if (string.IsNullOrEmpty(href)) return null;

        // Extract event ID from link: /event/6304590-team1-team2
        var eventId = ExtractEventId(href);
        if (string.IsNullOrEmpty(eventId)) return null;

        // Team names: div.medium-text inside the link
        var teamNodes = teamLink.SelectNodes(".//div[contains(@class,'medium-text')]");
        if (teamNodes == null || teamNodes.Count < 2) return null;

        var teamHome = HtmlAgilityPack.HtmlEntity.DeEntitize(teamNodes[0].InnerText).Trim();
        var teamAway = HtmlAgilityPack.HtmlEntity.DeEntitize(teamNodes[1].InnerText).Trim();

        if (string.IsNullOrEmpty(teamHome) || string.IsNullOrEmpty(teamAway))
            return null;

        // Parse date/time from the date node
        var dateText = dateNode != null ? HtmlAgilityPack.HtmlEntity.DeEntitize(dateNode.InnerText).Trim() : "";
        var startTimeUtc = ParseKushDateTime(dateText);

        // League name: extracted from page context (not in event row itself)
        // Will be populated by the caller or left empty
        var league = "";

        return new KushEvent(eventId, league, teamHome, teamAway, startTimeUtc, href);
    }

    /// <summary>
    /// Extract event ID from URL path like /event/6304590-team1-team2.
    /// </summary>
    public static string ExtractEventId(string eventPath)
    {
        // /event/6304590-sheffild-yunayted-norvich-siti
        var idx = eventPath.LastIndexOf("/event/", StringComparison.Ordinal);
        if (idx < 0) return "";

        var rest = eventPath[(idx + "/event/".Length)..];
        var dashIdx = rest.IndexOf('-');
        return dashIdx > 0 ? rest[..dashIdx] : rest;
    }

    /// <summary>
    /// Parse Kush date string like "09.12.2025 22.45" into DateTime UTC.
    /// Note: Kush times are in Moscow timezone (MSK = UTC+3).
    /// </summary>
    public static DateTime ParseKushDateTime(string dateText)
    {
        if (string.IsNullOrWhiteSpace(dateText))
            return DateTime.MinValue;

        // Normalize: replace dots in time with colons (22.45 → 22:45)
        // Format variants: "09.12.2025 22.45", "09.12 22:45"
        var parts = dateText.Split(' ', StringSplitOptions.RemoveEmptyEntries);

        string? datePart = null;
        string? timePart = null;

        foreach (var part in parts)
        {
            if (part.Contains(':') || (part.Length <= 5 && part.Count(c => c == '.') == 1))
            {
                // This looks like a time part
                timePart = part.Replace('.', ':');
            }
            else if (part.Count(c => c == '.') >= 1)
            {
                datePart = part;
            }
        }

        if (datePart == null)
            return DateTime.MinValue;

        // Try full format: dd.MM.yyyy HH:mm
        if (timePart != null)
        {
            var combined = $"{datePart} {timePart}";
            string[] formats = ["dd.MM.yyyy HH:mm", "dd.MM HH:mm", "d.M.yyyy H:mm", "d.M H:mm"];

            foreach (var fmt in formats)
            {
                if (DateTime.TryParseExact(combined, fmt, CultureInfo.InvariantCulture,
                    DateTimeStyles.None, out var dt))
                {
                    // If no year, assume current year
                    if (!combined.Contains(dt.Year.ToString()))
                        dt = new DateTime(DateTime.UtcNow.Year, dt.Month, dt.Day, dt.Hour, dt.Minute, 0);

                    // Convert MSK → UTC (MSK = UTC+3)
                    return dt.AddHours(-3);
                }
            }
        }

        return DateTime.MinValue;
    }

    /// <summary>
    /// Parse odds HTML from cf-list response.
    /// Each button.coefLink contains bet type name + odds value + URL for coupon.
    /// </summary>
    public static IReadOnlyDictionary<string, KushOddsEntry> ParseOddsHtml(string html)
    {
        var doc = new HtmlAgilityPack.HtmlDocument();
        doc.LoadHtml(html);

        var odds = new Dictionary<string, KushOddsEntry>();
        var buttons = doc.DocumentNode.SelectNodes("//button[contains(@class,'coefLink')]");

        if (buttons == null)
            return odds;

        foreach (var btn in buttons)
        {
            var nameNode = btn.SelectSingleNode(".//div[contains(@class,'d-sm-none')]");
            var valueNode = btn.SelectSingleNode(".//span");
            var urlAttr = btn.GetAttributeValue("url", "");

            if (nameNode == null || valueNode == null) continue;

            var betName = HtmlAgilityPack.HtmlEntity.DeEntitize(nameNode.InnerText).Trim();
            var valueText = HtmlAgilityPack.HtmlEntity.DeEntitize(valueNode.InnerText).Trim();

            if (string.IsNullOrEmpty(betName)) continue;

            if (double.TryParse(valueText, NumberStyles.Float, CultureInfo.InvariantCulture, out var value))
            {
                // Extract eid and cfid from URL like: /coupon/add-coupon?eid=123&cfid=456
                var (eid, cfid) = ExtractCouponIds(urlAttr);
                odds[betName] = new KushOddsEntry(betName, value, urlAttr, eid, cfid);
            }
        }

        return odds;
    }

    /// <summary>
    /// Extract eid and cfid from coupon URL.
    /// </summary>
    public static (string Eid, string Cfid) ExtractCouponIds(string url)
    {
        if (string.IsNullOrEmpty(url))
            return ("", "");

        var eid = "";
        var cfid = "";

        var eidIdx = url.IndexOf("eid=", StringComparison.Ordinal);
        if (eidIdx >= 0)
        {
            var start = eidIdx + 4;
            var end = url.IndexOf('&', start);
            eid = end > 0 ? url[start..end] : url[start..];
        }

        var cfidIdx = url.IndexOf("cfid=", StringComparison.Ordinal);
        if (cfidIdx >= 0)
        {
            var start = cfidIdx + 5;
            var end = url.IndexOf('&', start);
            cfid = end > 0 ? url[start..end] : url[start..];
        }

        return (eid.Trim(), cfid.Trim());
    }
}

/// <summary>
/// A league entry from the Kush sidebar.
/// </summary>
public sealed record KushLeague(string Cid, string Name);

/// <summary>
/// A single odds entry from the cf-list response.
/// </summary>
public sealed record KushOddsEntry(
    string BetName,
    double Value,
    string CouponUrl,
    string EventId,
    string CoefficientId
);
