using System.Globalization;
using System.Text.Json;
using ParserNbBet.Config;
using ParserNbBet.Decision;
using ParserNbBet.Nb;
using Serilog;

namespace ParserNbBet.Kush;

/// <summary>
/// Places bets on kushvsporte.ru.
/// Flow: check ratio → GET /coupon/add-coupon (extract tokens) → POST /coupon/create-coupon.
/// Supports dry-run mode (logs but does not submit).
/// </summary>
public sealed class KushBetPlacer
{
    private static readonly ILogger Logger = Log.ForContext<KushBetPlacer>();

    private readonly KushSession _session;
    private readonly KushClient _client;
    private readonly KushConfig _kushConfig;
    private readonly ThresholdConfig _thresholds;
    private readonly Dictionary<string, string[]>? _betTypeMapping;

    /// <summary>Success marker in response HTML.</summary>
    private const string SuccessMarker = "Прогноз успешно добавлен";

    public KushBetPlacer(KushClient client, KushConfig kushConfig,
                         ThresholdConfig thresholds, string? betTypeMappingPath = null)
    {
        _client = client;
        _session = client.Session;
        _kushConfig = kushConfig;
        _thresholds = thresholds;
        _betTypeMapping = LoadBetTypeMapping(betTypeMappingPath);
    }

    /// <summary>
    /// Attempt to place a bet for a matched NB↔Kush event.
    /// Steps:
    ///   1. Get odds from Kush for the event.
    ///   2. Find the matching odds entry (using bet type mapping).
    ///   3. Check ratio threshold.
    ///   4. Place bet (or dry-run).
    /// </summary>
    public async Task<BetResult> PlaceAsync(
        Match nbMatch, KushEvent kushEvent, BetDecision decision,
        LeagueSetting? leagueSetting = null, CancellationToken ct = default)
    {
        var betType = decision.BetType;
        Logger.Information("BetPlacer: attempting {BetType} for {Match} on Kush event {EventId}",
            betType, nbMatch, kushEvent.EventId);

        // Step 1: Get odds from Kush
        IReadOnlyDictionary<string, KushOddsEntry> kushOdds;
        try
        {
            kushOdds = await _client.GetOddsAsync(kushEvent.EventId, kushEvent.Url, ct);
        }
        catch (Exception ex)
        {
            Logger.Error(ex, "BetPlacer: failed to get odds for event {EventId}", kushEvent.EventId);
            return BetResult.Failed($"Failed to get Kush odds: {ex.Message}", betType, kushEvent.EventId);
        }

        if (kushOdds.Count == 0)
            return BetResult.Failed("No odds available on Kush", betType, kushEvent.EventId);

        // Step 2: Find matching odds entry
        var kushBetType = ResolveKushBetType(betType, leagueSetting);
        var oddsEntry = FindOddsEntry(kushOdds, kushBetType);

        if (oddsEntry == null)
        {
            Logger.Warning("BetPlacer: odds type '{KushBetType}' not found on Kush (available: {Available})",
                kushBetType, string.Join(", ", kushOdds.Keys));
            return BetResult.Failed($"Odds type '{kushBetType}' not found on Kush", betType, kushEvent.EventId);
        }

        // Step 3: Get NB odds for ratio calculation
        var oddsNb = GetNbOdds(nbMatch, betType);
        if (oddsNb <= 0)
            return BetResult.Failed($"NB odds for '{betType}' not available", betType, kushEvent.EventId);

        var oddsKush = oddsEntry.Value;

        // Step 4: Check ratio threshold
        var ratio = CalculateRatio(oddsKush, oddsNb, _thresholds.Roi);
        var threshold = GetThreshold(nbMatch.League);
        var ratioPass = ratio > threshold;

        Logger.Information("BetPlacer: {BetType} ratio={Ratio:F4} threshold={Threshold:F2} pass={Pass} " +
                          "(kushOdds={KushOdds:F2} nbOdds={NbOdds:F2} roi={Roi})",
            betType, ratio, threshold, ratioPass, oddsKush, oddsNb, _thresholds.Roi);

        if (!ratioPass)
        {
            return new BetResult(false, _kushConfig.DryRun, betType, oddsNb, oddsKush, ratio,
                0, kushEvent.EventId, $"Ratio {ratio:F4} below threshold {threshold:F2}");
        }

        // Step 5: Check coefficient range from league setting
        if (leagueSetting != null)
        {
            if (oddsKush < leagueSetting.MinKf || oddsKush > leagueSetting.MaxKf)
            {
                return new BetResult(false, _kushConfig.DryRun, betType, oddsNb, oddsKush, ratio,
                    0, kushEvent.EventId,
                    $"Kush odds {oddsKush:F2} outside range [{leagueSetting.MinKf:F2}..{leagueSetting.MaxKf:F2}]");
            }
        }

        var stake = _kushConfig.DefaultStake;

        // Step 6: Dry-run or real placement
        if (_kushConfig.DryRun)
        {
            Logger.Information("BetPlacer: [DRY-RUN] would place {BetType} on {Event} " +
                              "kush={KushOdds:F2} nb={NbOdds:F2} ratio={Ratio:F4} stake={Stake}",
                betType, kushEvent, oddsKush, oddsNb, ratio, stake);

            return new BetResult(true, true, betType, oddsNb, oddsKush, ratio,
                stake, kushEvent.EventId, "Dry-run: bet would be placed");
        }

        // Real bet placement
        return await PlaceRealBetAsync(
            nbMatch, kushEvent, oddsEntry, betType, oddsNb, oddsKush, ratio, stake, ct);
    }

    /// <summary>
    /// Calculate ratio: KfKush * (1 + ROI) / KfNB.
    /// </summary>
    public static double CalculateRatio(double oddsKush, double oddsNb, double roi)
    {
        if (oddsNb <= 0) return 0;
        return oddsKush * (1 + roi) / oddsNb;
    }

    /// <summary>
    /// Get the ratio threshold for a league (big leagues use lower threshold).
    /// </summary>
    public double GetThreshold(string league)
    {
        if (_thresholds.BigLeagues.Count > 0)
        {
            var normalizedLeague = league.Trim().ToLowerInvariant();
            foreach (var big in _thresholds.BigLeagues)
            {
                if (normalizedLeague.Contains(big.Trim().ToLowerInvariant()))
                    return _thresholds.BigLeagueRatio;
            }
        }
        return _thresholds.DefaultRatio;
    }

    /// <summary>
    /// Resolve NB bet type to Kush bet type using sl_stavok.json mapping and league setting.
    /// </summary>
    public string ResolveKushBetType(string nbBetType, LeagueSetting? setting)
    {
        // If league setting specifies a Kush bet type, use it
        if (setting != null && !string.IsNullOrWhiteSpace(setting.BetTypeKush))
            return setting.BetTypeKush;

        // Map standard decision engine types to Kush equivalents
        var kushType = nbBetType switch
        {
            "1" => "П1",
            "2" => "П2",
            "X" => "Ничья",
            "1X" => "1X",
            _ => nbBetType
        };

        // Check sl_stavok.json for direct mapping
        if (_betTypeMapping != null)
        {
            // First try direct match
            if (_betTypeMapping.TryGetValue(kushType, out var mapped) && mapped.Length > 0)
                return mapped[0]; // [0] = direct, [1] = inverse

            // Try the NB bet type directly
            if (_betTypeMapping.TryGetValue(nbBetType, out var mapped2) && mapped2.Length > 0)
                return mapped2[0];
        }

        return kushType;
    }

    // ── Private Methods ──────────────────────────────────────────────

    private async Task<BetResult> PlaceRealBetAsync(
        Match nbMatch, KushEvent kushEvent, KushOddsEntry oddsEntry,
        string betType, double oddsNb, double oddsKush, double ratio, double stake,
        CancellationToken ct)
    {
        // Ensure logged in
        if (!_session.IsLoggedIn)
        {
            var loginOk = await _session.LoginAsync(ct);
            if (!loginOk)
            {
                return new BetResult(false, false, betType, oddsNb, oddsKush, ratio,
                    stake, kushEvent.EventId, "Login to Kush failed");
            }
        }

        try
        {
            // Step A: GET /coupon/add-coupon — extract form tokens
            var tokens = await AddCouponAsync(
                oddsEntry.EventId, oddsEntry.CoefficientId, kushEvent.Url, ct);

            if (tokens == null || tokens.Count == 0)
            {
                return new BetResult(false, false, betType, oddsNb, oddsKush, ratio,
                    stake, kushEvent.EventId, "Failed to extract coupon form tokens");
            }

            // Step B: POST /coupon/create-coupon — place the bet
            var success = await CreateCouponAsync(tokens, stake, kushEvent.Url, ct);

            Logger.Information("BetPlacer: {Result} {BetType} on {Event} " +
                              "kush={KushOdds:F2} nb={NbOdds:F2} ratio={Ratio:F4} stake={Stake}",
                success ? "PLACED" : "FAILED", betType, kushEvent, oddsKush, oddsNb, ratio, stake);

            return new BetResult(success, false, betType, oddsNb, oddsKush, ratio,
                stake, kushEvent.EventId,
                success ? "Bet placed successfully" : "Coupon creation failed");
        }
        catch (Exception ex)
        {
            Logger.Error(ex, "BetPlacer: error placing bet on {Event}", kushEvent);
            return new BetResult(false, false, betType, oddsNb, oddsKush, ratio,
                stake, kushEvent.EventId, $"Error: {ex.Message}");
        }
    }

    /// <summary>
    /// GET /coupon/add-coupon?eid={eid}&amp;cfid={cfid} — extract hidden form tokens.
    /// </summary>
    internal async Task<Dictionary<string, string>?> AddCouponAsync(
        string eid, string cfid, string eventUrl, CancellationToken ct)
    {
        var url = $"{_session.BaseUrl}/coupon/add-coupon?eid={eid}&cfid={cfid}&_pjax=%23coupon";
        var referer = $"{_session.BaseUrl}{eventUrl}?abtest=9";

        Logger.Debug("BetPlacer: GET add-coupon eid={Eid} cfid={Cfid}", eid, cfid);

        var html = await _session.GetPjaxAsync(url, referer, ct);
        return ExtractFormTokens(html);
    }

    /// <summary>
    /// POST /coupon/create-coupon — submit the bet.
    /// </summary>
    internal async Task<bool> CreateCouponAsync(
        Dictionary<string, string> tokens, double stake, string eventUrl,
        CancellationToken ct)
    {
        // Add bet-specific fields
        tokens["Coupon[bet_amount]"] = stake.ToString(CultureInfo.InvariantCulture);
        tokens["Coupon[comment]"] = "";
        tokens["addReviewButton2"] = "";
        tokens["_pjax"] = "#coupon";

        var referer = $"{_session.BaseUrl}{eventUrl}?abtest=9";

        Logger.Debug("BetPlacer: POST create-coupon with {Count} fields, stake={Stake}",
            tokens.Count, stake);

        var html = await _session.PostAjaxAsync(
            $"{_session.BaseUrl}/coupon/create-coupon", tokens, referer, ct);

        var success = html.Contains(SuccessMarker, StringComparison.OrdinalIgnoreCase);

        if (!success)
            Logger.Warning("BetPlacer: create-coupon response did not contain success marker. " +
                          "Response length={Length}", html.Length);

        return success;
    }

    /// <summary>
    /// Extract all hidden input fields from the coupon form HTML.
    /// </summary>
    public static Dictionary<string, string>? ExtractFormTokens(string html)
    {
        if (string.IsNullOrEmpty(html)) return null;

        var doc = new HtmlAgilityPack.HtmlDocument();
        doc.LoadHtml(html);

        var form = doc.DocumentNode.SelectSingleNode("//form[@action='/coupon/create-coupon']");
        if (form == null)
        {
            Logger.Warning("BetPlacer: coupon form not found in response");
            return null;
        }

        var inputs = form.SelectNodes(".//input");
        if (inputs == null) return null;

        var tokens = new Dictionary<string, string>();
        foreach (var input in inputs)
        {
            var name = input.GetAttributeValue("name", "");
            var value = input.GetAttributeValue("value", "");
            if (!string.IsNullOrEmpty(name))
                tokens[name] = value;
        }

        Logger.Debug("BetPlacer: extracted {Count} form tokens", tokens.Count);
        return tokens.Count > 0 ? tokens : null;
    }

    /// <summary>
    /// Find the matching odds entry by bet type name (case-insensitive, trimmed).
    /// </summary>
    private static KushOddsEntry? FindOddsEntry(
        IReadOnlyDictionary<string, KushOddsEntry> odds, string betType)
    {
        // Exact match first
        if (odds.TryGetValue(betType, out var exact))
            return exact;

        // Case-insensitive search
        var normalizedType = betType.Trim().ToLowerInvariant();
        foreach (var (key, entry) in odds)
        {
            if (key.Trim().ToLowerInvariant() == normalizedType)
                return entry;
        }

        return null;
    }

    /// <summary>
    /// Get the NB odds value for a given bet type.
    /// </summary>
    private static double GetNbOdds(Match match, string betType)
    {
        return betType switch
        {
            "1" => match.Odds1End ?? 0,
            "2" => match.Odds2End ?? 0,
            "X" => match.OddsXEnd ?? 0,
            "1X" => match.Odds1XEnd ?? 0,
            _ => 0
        };
    }

    private static Dictionary<string, string[]>? LoadBetTypeMapping(string? path)
    {
        path ??= Path.Combine("assets", "data", "sl_stavok.json");
        if (!File.Exists(path)) return null;

        try
        {
            var json = File.ReadAllText(path);
            return JsonSerializer.Deserialize<Dictionary<string, string[]>>(json);
        }
        catch (Exception ex)
        {
            Logger.Warning(ex, "BetPlacer: failed to load bet type mapping from {Path}", path);
            return null;
        }
    }
}
