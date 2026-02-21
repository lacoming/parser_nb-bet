using System.Text.Json;
using ParserNbBet.Config;
using ParserNbBet.Decision;
using ParserNbBet.Kush;
using ParserNbBet.Logging;
using ParserNbBet.Nb;
using ParserNbBet.State;
using ParserNbBet.Ui;
using Serilog;

namespace ParserNbBet;

/// <summary>
/// Entry point.
/// Usage:
///   parser_nb-bet.exe --once      — one cycle then exit (no UI)
///   parser_nb-bet.exe --daemon    — run on schedule (with UI)
///   parser_nb-bet.exe             — open UI window (default)
///
/// Optional flags:
///   --dry-run                     — no real bets placed
///   --config path/to/config.json  — custom config path
/// </summary>
static class Program
{
    [STAThread]
    static void Main(string[] args)
    {
        var parsed = CliArgs.Parse(args);

        // Load configuration
        AppConfig config;
        try
        {
            config = ConfigLoader.Load(parsed.ConfigPath);
        }
        catch (ConfigValidationException ex)
        {
            Console.Error.WriteLine(ex.Message);
            Environment.ExitCode = 1;
            return;
        }

        // Apply CLI overrides
        if (parsed.DryRun)
            config.Kush.DryRun = true;

        // Initialize logging
        LoggingSetup.Initialize(config);

        try
        {
            Log.Information("parser_nb-bet starting...");
            Log.Information("  mode:     {Mode}", parsed.Once ? "once" : parsed.Daemon ? "daemon" : "ui");
            Log.Information("  dry-run:  {DryRun}", config.Kush.DryRun);
            Log.Information("  config:   {ConfigPath}", parsed.ConfigPath);

            // Verify state store can initialize
            using var state = new StateStore();
            Log.Information("  state:    ok (pending={PendingCount})", state.PendingCount());

            Log.Information("boot ok");

            // Headless --once mode: no WinForms, just run cycle and exit
            if (parsed.Once)
            {
                RunHeadless(parsed, config, state);
                return;
            }

            // WinForms application (--daemon or default interactive)
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.SetHighDpiMode(HighDpiMode.SystemAware);

            Application.Run(new MainForm(parsed));
        }
        catch (Exception ex)
        {
            Log.Fatal(ex, "Unhandled exception");
            throw;
        }
        finally
        {
            Log.CloseAndFlush();
        }
    }

    static void RunHeadless(CliArgs args, AppConfig config, StateStore state)
    {
        Log.Information("Headless cycle starting...");

        using var nbClient = new NbClient(config.Nb, config.Proxies);
        var windowDays = config.Schedule.WindowDays;

        // Fetch soccer matches
        var matches = nbClient.GetMatchesAsync(windowDays, "soccer").GetAwaiter().GetResult();
        Log.Information("NB fetched: {Count} soccer matches over {Days} days", matches.Count, windowDays);

        // League filter
        var leagueSettings = LoadLeagues(config);
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

        // Kush matching + pending queue
        RunKushMatching(config, state, passingMatches);

        // Process pending queue (re-check previously queued matches)
        ProcessPendingQueue(config, state);

        // TODO step 12: scheduler integration

        Log.Information("Headless cycle complete.");
    }

    static void RunKushMatching(AppConfig config, StateStore state,
        List<(Match Match, LeagueSetting Setting, MatchDecision Decision)> passingMatches)
    {
        if (passingMatches.Count == 0) return;

        Log.Information("Kush matching: checking {Count} passing matches...", passingMatches.Count);

        using var kushClient = new KushClient(config.Kush, config.Proxies);
        var betPlacer = new KushBetPlacer(kushClient, config.Kush, config.Thresholds);
        int matched = 0, pending = 0, skipped = 0, placed = 0;

        foreach (var (match, setting, decision) in passingMatches)
        {
            // Skip if already known (placed or pending)
            if (state.IsKnown(match.MatchKey))
            {
                Log.Debug("  SKIP (already known): {Match}", match);
                skipped++;
                continue;
            }

            try
            {
                var result = kushClient.FindEventAsync(match).GetAwaiter().GetResult();

                if (result.IsAccepted && result.KushEvent != null)
                {
                    matched++;
                    Log.Information("  MATCHED: {NbMatch} → {KushEvent} (confidence={Confidence:F3})",
                        match, result.KushEvent, result.Confidence);

                    // Try placing bet for each passing bet type
                    foreach (var bet in decision.PassingBets)
                    {
                        var betResult = betPlacer.PlaceAsync(
                            match, result.KushEvent, bet, setting).GetAwaiter().GetResult();

                        Log.Information("  BET: {Result}", betResult);

                        if (betResult.Success || betResult.DryRun)
                        {
                            placed++;
                            state.RecordBet(match.MatchKey, betResult.BetType,
                                betResult.KushEventId, betResult.OddsNb, betResult.OddsKush,
                                betResult.Stake, betResult.Ratio, betResult.DryRun);
                            // TODO step 10: TelegramNotifier.NotifyPlaced()
                            break; // One bet per match
                        }
                    }
                }
                else
                {
                    // Not found on Kush → enqueue pending
                    var betTypes = string.Join(",", decision.PassingBets.Select(d => d.BetType));
                    var enqueued = state.Enqueue(
                        match.MatchKey, match.League, match.TeamHome, match.TeamAway,
                        match.StartTimeUtc, match.NbSlug, betTypes);

                    if (enqueued)
                    {
                        pending++;
                        Log.Information("  PENDING: {Match} — {Reason}", match, result.Reason);
                        // TODO step 10: TelegramNotifier.NotifyMissing()
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
                state.Enqueue(match.MatchKey, match.League, match.TeamHome, match.TeamAway,
                    match.StartTimeUtc, match.NbSlug, betTypes);
                pending++;
            }
        }

        Log.Information("Kush matching done: {Matched} matched, {Placed} placed, {Pending} pending, {Skipped} skipped",
            matched, placed, pending, skipped);
    }

    static void ProcessPendingQueue(AppConfig config, StateStore state)
    {
        var duePending = state.GetDuePending();
        if (duePending.Count == 0)
        {
            Log.Debug("Pending queue: no due items");
            return;
        }

        Log.Information("Pending queue: {Count} due items to re-check", duePending.Count);

        using var kushClient = new KushClient(config.Kush, config.Proxies);
        var betPlacer = new KushBetPlacer(kushClient, config.Kush, config.Thresholds);
        int resolved = 0, placed = 0;

        foreach (var pm in duePending)
        {
            // Skip if match already started (past startTimeUtc)
            if (pm.StartTimeUtc < DateTime.UtcNow)
            {
                Log.Information("  EXPIRED: {Match} (started {Start:HH:mm})", pm.MatchKey, pm.StartTimeUtc);
                state.RemovePending(pm.MatchKey);
                continue;
            }

            try
            {
                // Create a temporary Match object for matching
                var tempMatch = new Match(pm.League, pm.TeamHome, pm.TeamAway,
                    pm.StartTimeUtc, pm.NbUrl, "soccer");

                var result = kushClient.FindEventAsync(tempMatch).GetAwaiter().GetResult();

                if (result.IsAccepted && result.KushEvent != null)
                {
                    resolved++;
                    Log.Information("  RESOLVED: {Match} → {KushEvent} (confidence={Confidence:F3})",
                        pm.MatchKey, result.KushEvent, result.Confidence);

                    // Try placing bet for each stored bet type
                    var betTypes = pm.BetType.Split(',', StringSplitOptions.RemoveEmptyEntries);
                    foreach (var bt in betTypes)
                    {
                        var fakeBet = new BetDecision { BetType = bt.Trim(), Passes = true };
                        var betResult = betPlacer.PlaceAsync(
                            tempMatch, result.KushEvent, fakeBet).GetAwaiter().GetResult();

                        Log.Information("  BET: {Result}", betResult);

                        if (betResult.Success || betResult.DryRun)
                        {
                            placed++;
                            state.RecordBet(pm.MatchKey, betResult.BetType,
                                betResult.KushEventId, betResult.OddsNb, betResult.OddsKush,
                                betResult.Stake, betResult.Ratio, betResult.DryRun);
                            // TODO step 10: TelegramNotifier.NotifyPlaced()
                            break;
                        }
                    }

                    state.RemovePending(pm.MatchKey);
                }
                else
                {
                    // Still not found — reschedule next check
                    var nextCheck = DateTime.UtcNow.AddMinutes(30);
                    state.UpdateNextCheck(pm.MatchKey, nextCheck);
                    Log.Debug("  STILL PENDING: {Match}, next check at {Next:HH:mm}",
                        pm.MatchKey, nextCheck);
                }
            }
            catch (Exception ex) when (ex is not OperationCanceledException)
            {
                Log.Warning(ex, "  ERROR re-checking {Match}", pm.MatchKey);
                state.UpdateNextCheck(pm.MatchKey, DateTime.UtcNow.AddMinutes(30));
            }
        }

        Log.Information("Pending queue: {Resolved}/{Total} resolved, {Placed} bets placed",
            resolved, duePending.Count, placed);
    }

    static List<LeagueSetting> LoadLeagues(AppConfig config)
    {
        var path = config.Files.LeaguesXlsxPath;
        if (!File.Exists(path))
        {
            Log.Warning("leagues.xlsx not found at {Path}, skipping league filter (all matches pass)", path);
            return [];
        }
        return LeagueLoader.Load(path);
    }

    static Dictionary<string, string>? LoadLeagueRenames()
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
