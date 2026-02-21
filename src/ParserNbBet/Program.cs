using System.Text.Json;
using ParserNbBet.Config;
using ParserNbBet.Decision;
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
        int passCount = 0;
        foreach (var (match, setting) in filtered)
        {
            var decision = DecisionEngine.Evaluate(match);
            if (decision.AnyPasses)
            {
                passCount++;
                var bets = string.Join(", ", decision.PassingBets.Select(d => d.BetType));
                Log.Information("  PASS: {Match} -> bets: {Bets}", match, bets);
            }
        }
        Log.Information("After decision: {PassCount}/{FilteredCount} matches pass", passCount, filtered.Count);

        // TODO step 08: kush matching
        // TODO step 12: scheduler integration

        Log.Information("Headless cycle complete.");
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
