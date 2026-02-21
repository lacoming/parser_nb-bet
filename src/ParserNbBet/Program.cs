using ParserNbBet.Config;
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

        // Show first 3 as examples
        foreach (var m in matches.Take(3))
        {
            Log.Information("  Example: {Match}", m);
        }

        // TODO step 06: league filter + decision engine
        // TODO step 08: kush matching
        // TODO step 12: scheduler integration

        Log.Information("Headless cycle complete.");
    }
}
