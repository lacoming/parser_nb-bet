using System.Text.Json;
using ParserNbBet.Config;
using ParserNbBet.Decision;
using ParserNbBet.Excel;
using ParserNbBet.Kush;
using ParserNbBet.Nb;
using ParserNbBet.State;
using ParserNbBet.Telegram;
using Serilog;

namespace ParserNbBet.Scheduler;

/// <summary>
/// Encapsulates a single parsing/matching/betting cycle.
/// Extracted from Program.RunHeadless so it can be reused by scheduler and UI.
/// </summary>
public sealed class CycleRunner
{
    private readonly AppConfig _config;
    private readonly StateStore _state;
    private readonly TelegramNotifier _telegram;

    /// <summary>Results of the last cycle (for UI display).</summary>
    public CycleResult? LastResult { get; private set; }

    public CycleRunner(AppConfig config, StateStore state, TelegramNotifier telegram)
    {
        _config = config;
        _state = state;
        _telegram = telegram;
    }

    /// <summary>
    /// Run one full cycle: fetch NB → filter → decide → match Kush → bet → excel → notify.
    /// </summary>
    public async Task RunAsync(CancellationToken ct = default)
    {
        Log.Information("Cycle starting...");

        using var nbClient = new NbClient(_config.Nb, _config.Proxies);
        var windowDays = _config.Schedule.WindowDays;

        // Fetch soccer matches
        var matches = await nbClient.GetMatchesAsync(windowDays, "soccer");
        Log.Information("NB fetched: {Count} soccer matches over {Days} days", matches.Count, windowDays);

        ct.ThrowIfCancellationRequested();

        // League filter
        var leagueSettings = LoadLeagues();
        var leagueRenames = LoadLeagueRenames();
        var filter = new LeagueFilter(leagueSettings, leagueRenames);
        var filtered = filter.Filter(matches);
        Log.Information("After league filter: {Count}/{Total}", filtered.Count, matches.Count);

        // Decision engine
        var passingMatches = new List<(Match Match, LeagueSetting Setting, MatchDecision Decision)>();
        foreach (var (match, setting) in filtered)
        {
            var decision = DecisionEngine.Evaluate(match);
            if (decision.AnyPasses)
            {
                passingMatches.Add((match, setting, decision));
                var bets = string.Join(", ", decision.PassingBets.Select(d => d.BetType));
                Log.Information("  PASS: {Match} -> bets: {Bets}", match, bets);
            }
        }
        Log.Information("After decision: {PassCount}/{FilteredCount} matches pass",
            passingMatches.Count, filtered.Count);

        ct.ThrowIfCancellationRequested();

        // Excel writer
        var excel = new ExcelWriter(_config.Files.OutputDir);

        // Kush matching + pending queue
        var (matched, placed, pending) = await RunKushMatchingAsync(excel, passingMatches, ct);

        // Process pending queue
        await ProcessPendingQueueAsync(excel, ct);

        // Save Excel
        var excelPath = excel.Save();
        if (excelPath != null)
            Log.Information("Excel saved: {Path} ({Rows} rows)", excelPath, excel.RowCount);

        // Cycle summary notification
        await _telegram.NotifyCycleSummaryAsync(
            matches.Count, filtered.Count, passingMatches.Count,
            matched, placed, pending, _config.Kush.DryRun);

        LastResult = new CycleResult(
            DateTime.UtcNow, matches.Count, filtered.Count,
            passingMatches.Count, matched, placed, pending);

        Log.Information("Cycle complete.");
    }

    private async Task<(int matched, int placed, int pending)> RunKushMatchingAsync(
        ExcelWriter excel,
        List<(Match Match, LeagueSetting Setting, MatchDecision Decision)> passingMatches,
        CancellationToken ct)
    {
        if (passingMatches.Count == 0) return (0, 0, 0);

        Log.Information("Kush matching: checking {Count} passing matches...", passingMatches.Count);

        using var kushClient = new KushClient(_config.Kush, _config.Proxies);
        var betPlacer = new KushBetPlacer(kushClient, _config.Kush, _config.Thresholds);
        int matched = 0, pending = 0, skipped = 0, placed = 0;

        foreach (var (match, setting, decision) in passingMatches)
        {
            ct.ThrowIfCancellationRequested();

            if (_state.IsKnown(match.MatchKey))
            {
                Log.Debug("  SKIP (already known): {Match}", match);
                skipped++;
                continue;
            }

            try
            {
                var result = await kushClient.FindEventAsync(match);

                if (result.IsAccepted && result.KushEvent != null)
                {
                    matched++;
                    Log.Information("  MATCHED: {NbMatch} → {KushEvent} (confidence={Confidence:F3})",
                        match, result.KushEvent, result.Confidence);

                    foreach (var bet in decision.PassingBets)
                    {
                        var betResult = await betPlacer.PlaceAsync(match, result.KushEvent, bet, setting);

                        Log.Information("  BET: {Result}", betResult);

                        if (betResult.Success || betResult.DryRun)
                        {
                            placed++;
                            _state.RecordBet(match.MatchKey, betResult.BetType,
                                betResult.KushEventId, betResult.OddsNb, betResult.OddsKush,
                                betResult.Stake, betResult.Ratio, betResult.DryRun);
                            await _telegram.NotifyPlacedAsync(match, betResult);
                            excel.AddRow(ExcelWriter.BuildRow(match, bet, betResult, result.KushEvent));
                            break;
                        }
                    }
                }
                else
                {
                    var betTypes = string.Join(",", decision.PassingBets.Select(d => d.BetType));
                    var enqueued = _state.Enqueue(
                        match.MatchKey, match.League, match.TeamHome, match.TeamAway,
                        match.StartTimeUtc, match.NbSlug, betTypes);

                    if (enqueued)
                    {
                        pending++;
                        Log.Information("  PENDING: {Match} — {Reason}", match, result.Reason);
                        await _telegram.NotifyMissingAsync(match, result.Reason);
                        var firstBet = decision.PassingBets.FirstOrDefault();
                        if (firstBet != null)
                            excel.AddRow(ExcelWriter.BuildRow(match, firstBet, status: "pending"));
                    }
                    else
                    {
                        skipped++;
                        Log.Debug("  SKIP (already pending): {Match}", match);
                    }
                }
            }
            catch (Exception ex) when (ex is not OperationCanceledException)
            {
                Log.Warning(ex, "  ERROR matching {Match}, enqueueing as pending", match);
                var betTypes = string.Join(",", decision.PassingBets.Select(d => d.BetType));
                _state.Enqueue(match.MatchKey, match.League, match.TeamHome, match.TeamAway,
                    match.StartTimeUtc, match.NbSlug, betTypes);
                pending++;
            }
        }

        Log.Information("Kush matching done: {Matched} matched, {Placed} placed, {Pending} pending, {Skipped} skipped",
            matched, placed, pending, skipped);
        return (matched, placed, pending);
    }

    private async Task ProcessPendingQueueAsync(ExcelWriter excel, CancellationToken ct)
    {
        var duePending = _state.GetDuePending();
        if (duePending.Count == 0)
        {
            Log.Debug("Pending queue: no due items");
            return;
        }

        Log.Information("Pending queue: {Count} due items to re-check", duePending.Count);

        using var kushClient = new KushClient(_config.Kush, _config.Proxies);
        var betPlacer = new KushBetPlacer(kushClient, _config.Kush, _config.Thresholds);
        int resolved = 0, placed = 0;

        foreach (var pm in duePending)
        {
            ct.ThrowIfCancellationRequested();

            if (pm.StartTimeUtc < DateTime.UtcNow)
            {
                Log.Information("  EXPIRED: {Match} (started {Start:HH:mm})", pm.MatchKey, pm.StartTimeUtc);
                _state.RemovePending(pm.MatchKey);
                continue;
            }

            try
            {
                var tempMatch = new Match(pm.League, pm.TeamHome, pm.TeamAway,
                    pm.StartTimeUtc, pm.NbUrl, "soccer");

                var result = await kushClient.FindEventAsync(tempMatch);

                if (result.IsAccepted && result.KushEvent != null)
                {
                    resolved++;
                    Log.Information("  RESOLVED: {Match} → {KushEvent} (confidence={Confidence:F3})",
                        pm.MatchKey, result.KushEvent, result.Confidence);

                    var betTypes = pm.BetType.Split(',', StringSplitOptions.RemoveEmptyEntries);
                    foreach (var bt in betTypes)
                    {
                        var fakeBet = new BetDecision { BetType = bt.Trim(), Passes = true };
                        var betResult = await betPlacer.PlaceAsync(tempMatch, result.KushEvent, fakeBet);

                        Log.Information("  BET: {Result}", betResult);

                        if (betResult.Success || betResult.DryRun)
                        {
                            placed++;
                            _state.RecordBet(pm.MatchKey, betResult.BetType,
                                betResult.KushEventId, betResult.OddsNb, betResult.OddsKush,
                                betResult.Stake, betResult.Ratio, betResult.DryRun);
                            await _telegram.NotifyPlacedAsync(tempMatch, betResult);
                            excel.AddRow(ExcelWriter.BuildRow(tempMatch, fakeBet, betResult, result.KushEvent));
                            break;
                        }
                    }

                    _state.RemovePending(pm.MatchKey);
                }
                else
                {
                    var nextCheck = DateTime.UtcNow.AddMinutes(30);
                    _state.UpdateNextCheck(pm.MatchKey, nextCheck);
                    Log.Debug("  STILL PENDING: {Match}, next check at {Next:HH:mm}",
                        pm.MatchKey, nextCheck);
                }
            }
            catch (Exception ex) when (ex is not OperationCanceledException)
            {
                Log.Warning(ex, "  ERROR re-checking {Match}", pm.MatchKey);
                _state.UpdateNextCheck(pm.MatchKey, DateTime.UtcNow.AddMinutes(30));
            }
        }

        Log.Information("Pending queue: {Resolved}/{Total} resolved, {Placed} bets placed",
            resolved, duePending.Count, placed);
    }

    private List<LeagueSetting> LoadLeagues()
    {
        var path = _config.Files.LeaguesXlsxPath;
        if (!File.Exists(path))
        {
            Log.Warning("leagues.xlsx not found at {Path}, skipping league filter (all matches pass)", path);
            return [];
        }
        return LeagueLoader.Load(path);
    }

    private static Dictionary<string, string>? LoadLeagueRenames()
    {
        var path = Path.Combine("assets", "data", "sl_chemps_zamen.json");
        if (!File.Exists(path))
        {
            Log.Debug("sl_chemps_zamen.json not found, skipping league renames");
            return null;
        }

        var json = File.ReadAllText(path);
        return JsonSerializer.Deserialize<Dictionary<string, string>>(json);
    }
}

/// <summary>
/// Summary of a completed cycle (for UI/logging).
/// </summary>
public sealed record CycleResult(
    DateTime CompletedUtc,
    int TotalMatches,
    int FilteredMatches,
    int PassingMatches,
    int KushMatched,
    int BetsPlaced,
    int Pending
);
