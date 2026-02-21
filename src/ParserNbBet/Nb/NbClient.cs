using System.Net;
using System.Text.Json;
using ParserNbBet.Config;
using Polly;
using Polly.Retry;
using Serilog;

namespace ParserNbBet.Nb;

/// <summary>
/// HTTP client for NB-Bet JSON API.
/// Fetches match data from https://app.nb-bet.com/v1/{sport}/math-analysis/page.
/// </summary>
public sealed class NbClient : IDisposable
{
    private static readonly ILogger Logger = Log.ForContext<NbClient>();

    private readonly HttpClient _http;
    private readonly NbConfig _config;
    private readonly ResiliencePipeline<HttpResponseMessage> _retryPipeline;

    public NbClient(NbConfig config, ProxyConfig? proxyConfig = null)
    {
        _config = config;

        var handler = new HttpClientHandler();
        if (proxyConfig is { Enabled: true })
        {
            var proxyUrl = LoadFirstProxy(proxyConfig.File);
            if (proxyUrl != null)
            {
                handler.Proxy = new WebProxy(proxyUrl);
                handler.UseProxy = true;
                Logger.Information("Using proxy: {Proxy}", proxyUrl);
            }
        }

        _http = new HttpClient(handler)
        {
            Timeout = TimeSpan.FromSeconds(config.TimeoutSeconds)
        };

        // Required headers (from legacy analysis)
        _http.DefaultRequestHeaders.Add("User-Agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0");
        _http.DefaultRequestHeaders.Add("Accept", "application/json, text/plain, */*");
        _http.DefaultRequestHeaders.Add("Accept-Language", "ru");
        _http.DefaultRequestHeaders.Add("Origin", "https://nb-bet.com");
        _http.DefaultRequestHeaders.Add("Referer", "https://nb-bet.com/");

        _retryPipeline = new ResiliencePipelineBuilder<HttpResponseMessage>()
            .AddRetry(new RetryStrategyOptions<HttpResponseMessage>
            {
                MaxRetryAttempts = config.Retries,
                Delay = TimeSpan.FromSeconds(config.RetryDelaySeconds),
                ShouldHandle = new PredicateBuilder<HttpResponseMessage>()
                    .Handle<HttpRequestException>()
                    .Handle<TaskCanceledException>()
                    .HandleResult(r => !r.IsSuccessStatusCode),
                OnRetry = args =>
                {
                    Logger.Warning("NB request retry {Attempt}/{Max}, delay {Delay}s",
                        args.AttemptNumber + 1, config.Retries, config.RetryDelaySeconds);
                    return ValueTask.CompletedTask;
                }
            })
            .Build();
    }

    /// <summary>
    /// Fetch matches for a date range (window_days from today).
    /// </summary>
    public async Task<IReadOnlyList<Match>> GetMatchesAsync(
        int windowDays, string sport = "soccer", CancellationToken ct = default)
    {
        var allMatches = new List<Match>();
        var today = DateTime.UtcNow.Date;

        for (int day = 0; day < windowDays; day++)
        {
            var date = today.AddDays(day);
            try
            {
                var dayMatches = await GetMatchesForDateAsync(date, sport, ct);
                allMatches.AddRange(dayMatches);
                Logger.Debug("NB {Sport} {Date:yyyy-MM-dd}: {Count} matches",
                    sport, date, dayMatches.Count);
            }
            catch (Exception ex) when (ex is not OperationCanceledException)
            {
                Logger.Error(ex, "NB fetch failed for {Date:yyyy-MM-dd}, skipping", date);
            }
        }

        Logger.Information("NB total: {Count} matches ({Sport}, {Days} days)",
            allMatches.Count, sport, windowDays);
        return allMatches;
    }

    /// <summary>
    /// Fetch matches for a single date.
    /// </summary>
    public async Task<IReadOnlyList<Match>> GetMatchesForDateAsync(
        DateTime date, string sport = "soccer", CancellationToken ct = default)
    {
        // Timestamp = end of day in milliseconds (legacy: "23:59:59" + "999")
        var endOfDay = date.Date.AddDays(1).AddSeconds(-1);
        var timestampMs = new DateTimeOffset(endOfDay, TimeSpan.Zero).ToUnixTimeMilliseconds();

        var sportPath = sport.ToLowerInvariant() switch
        {
            "soccer" or "football" => "soccer",
            "hockey" => "hockey",
            _ => throw new ArgumentException($"Unknown sport: {sport}")
        };

        var url = $"{_config.BaseUrl.TrimEnd('/')}/v1/{sportPath}/math-analysis/page?timestamp={timestampMs}";
        Logger.Debug("NB request: {Url}", url);

        var response = await _retryPipeline.ExecuteAsync(
            async token => await _http.GetAsync(url, token), ct);

        response.EnsureSuccessStatusCode();

        var json = await response.Content.ReadAsStringAsync(ct);
        return ParseResponse(json, sport);
    }

    /// <summary>
    /// Parse the JSON response into Match objects. Public for testability.
    /// </summary>
    public static IReadOnlyList<Match> ParseResponse(string json, string sport)
    {
        var matches = new List<Match>();

        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;

        if (!root.TryGetProperty("data", out var data))
            return matches;
        if (!data.TryGetProperty("leagues", out var leagues))
            return matches;

        foreach (var league in leagues.EnumerateArray())
        {
            var country = GetString(league, "1") ?? "";
            var leagueName = GetString(league, "3") ?? "";
            var fullLeague = string.IsNullOrEmpty(country)
                ? leagueName
                : $"{country}. {leagueName}";

            if (!league.TryGetProperty("4", out var matchesArr))
                continue;

            foreach (var m in matchesArr.EnumerateArray())
            {
                try
                {
                    var match = ParseMatch(m, fullLeague, sport);
                    if (match != null)
                        matches.Add(match);
                }
                catch (Exception ex)
                {
                    Logger.Warning(ex, "Failed to parse match in league {League}", fullLeague);
                }
            }
        }

        return matches;
    }

    private static Match? ParseMatch(JsonElement m, string league, string sport)
    {
        var home = GetString(m, "7");
        var away = GetString(m, "15");
        var slug = GetString(m, "3");

        if (string.IsNullOrEmpty(home) || string.IsNullOrEmpty(away))
            return null;

        // Timestamp: field "4" is unix ms (13 digits)
        if (!m.TryGetProperty("4", out var tsEl))
            return null;

        long timestampMs;
        if (tsEl.ValueKind == JsonValueKind.Number)
        {
            timestampMs = tsEl.GetInt64();
        }
        else if (tsEl.ValueKind == JsonValueKind.String)
        {
            var tsStr = tsEl.GetString() ?? "";
            // Legacy trims last 3 chars, but if it's already seconds just multiply
            if (!long.TryParse(tsStr, out timestampMs))
                return null;
        }
        else
        {
            return null;
        }

        // If timestamp looks like seconds (10 digits), convert to ms
        if (timestampMs < 10_000_000_000L)
            timestampMs *= 1000;

        var startTimeUtc = DateTimeOffset.FromUnixTimeMilliseconds(timestampMs).UtcDateTime;

        var match = new Match(league, home, away, startTimeUtc, slug ?? "", sport)
        {
            Odds1Start = GetOdd(m, "6", "1"),  // start odds: home
            OddsXStart = GetOdd(m, "6", "3"),  // start odds: draw
            Odds2Start = GetOdd(m, "6", "2"),  // start odds: away
            Odds1End = GetOdd(m, "5", "1"),    // end odds: home
            OddsXEnd = GetOdd(m, "5", "3"),    // end odds: draw
            Odds2End = GetOdd(m, "5", "2"),    // end odds: away
        };

        return match;
    }

    /// <summary>
    /// Extract an odds value from nested JSON: match[outerKey][innerKey].
    /// Odds in NB API are stored as: "5": {"1": home, "2": away, "3": draw}.
    /// </summary>
    private static double? GetOdd(JsonElement match, string outerKey, string innerKey)
    {
        if (!match.TryGetProperty(outerKey, out var outer))
            return null;
        if (outer.ValueKind == JsonValueKind.Null)
            return null;
        if (!outer.TryGetProperty(innerKey, out var val))
            return null;

        return val.ValueKind switch
        {
            JsonValueKind.Number => val.GetDouble(),
            JsonValueKind.String when double.TryParse(val.GetString(),
                System.Globalization.NumberStyles.Float,
                System.Globalization.CultureInfo.InvariantCulture, out var d) => d,
            _ => null
        };
    }

    private static string? GetString(JsonElement el, string prop)
    {
        if (!el.TryGetProperty(prop, out var val))
            return null;
        return val.ValueKind == JsonValueKind.String ? val.GetString() : val.ToString();
    }

    private static string? LoadFirstProxy(string filePath)
    {
        if (!File.Exists(filePath))
            return null;

        foreach (var line in File.ReadLines(filePath))
        {
            var trimmed = line.Trim();
            if (trimmed.Length > 0 && !trimmed.StartsWith('#'))
                return trimmed;
        }

        return null;
    }

    public void Dispose() => _http.Dispose();
}
