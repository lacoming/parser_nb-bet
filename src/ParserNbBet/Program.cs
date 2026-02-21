using ParserNbBet.Config;
using ParserNbBet.Logging;
using ParserNbBet.Scheduler;
using ParserNbBet.State;
using ParserNbBet.Telegram;
using ParserNbBet.Ui;
using Serilog;

namespace ParserNbBet;

/// <summary>
/// Entry point.
/// Usage:
///   parser_nb-bet.exe --once      — one cycle then exit (no UI)
///   parser_nb-bet.exe --daemon    — run on schedule (no UI, headless)
///   parser_nb-bet.exe             — open UI window + daemon scheduler
///
/// Optional flags:
///   --dry-run                     — no real bets placed
///   --config path/to/config.json  — custom config path
///   --test-telegram               — send test message and exit
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

        // Determine if we need UI log sink
        bool isUiMode = !parsed.Once && !parsed.Daemon && !parsed.TestTelegram;
        MainForm? mainForm = null;
        UiLogSink? uiSink = null;

        if (isUiMode)
        {
            // Pre-create MainForm so the UiLogSink can reference it.
            // WinForms initialization must happen before Application.Run.
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.SetHighDpiMode(HighDpiMode.SystemAware);

            // We'll create the form after state/telegram init, but set up the sink callback first.
            // Use a buffer that the form will drain once created.
            var logBuffer = new System.Collections.Concurrent.ConcurrentQueue<string>();
            uiSink = new UiLogSink(line => logBuffer.Enqueue(line));

            LoggingSetup.Initialize(config, uiSink);

            try
            {
                Log.Information("parser_nb-bet starting...");
                Log.Information("  mode:     ui");
                Log.Information("  dry-run:  {DryRun}", config.Kush.DryRun);
                Log.Information("  config:   {ConfigPath}", parsed.ConfigPath);

                using var state = new StateStore();
                Log.Information("  state:    ok (pending={PendingCount})", state.PendingCount());
                Log.Information("boot ok");

                using var telegram = new TelegramNotifier(config.Telegram);
                if (telegram.IsConfigured)
                    Log.Information("  telegram: configured ({Count} chats)", config.Telegram.ChatIds.Count);
                else
                    Log.Information("  telegram: not configured");

                var runner = new CycleRunner(config, state, telegram);
                mainForm = new MainForm(parsed, config, runner);

                // Rewire sink to write directly to form + drain buffer
                uiSink = new UiLogSink(line => mainForm.AppendLog(line));
                LoggingSetup.Initialize(config, uiSink);

                // Drain buffered lines
                while (logBuffer.TryDequeue(out var buffered))
                    mainForm.AppendLog(buffered);

                Application.Run(mainForm);
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

            return;
        }

        // Headless modes: initialize logging without UI sink
        LoggingSetup.Initialize(config);

        try
        {
            Log.Information("parser_nb-bet starting...");
            Log.Information("  mode:     {Mode}", parsed.Once ? "once" : parsed.TestTelegram ? "test-telegram" : "daemon");
            Log.Information("  dry-run:  {DryRun}", config.Kush.DryRun);
            Log.Information("  config:   {ConfigPath}", parsed.ConfigPath);

            // Verify state store can initialize
            using var state = new StateStore();
            Log.Information("  state:    ok (pending={PendingCount})", state.PendingCount());

            Log.Information("boot ok");

            // Telegram notifier (shared across modes)
            using var telegram = new TelegramNotifier(config.Telegram);
            if (telegram.IsConfigured)
                Log.Information("  telegram: configured ({Count} chats)", config.Telegram.ChatIds.Count);
            else
                Log.Information("  telegram: not configured (skipping notifications)");

            // Handle --test-telegram
            if (parsed.TestTelegram)
            {
                var ok = telegram.SendTestAsync().GetAwaiter().GetResult();
                Log.Information("Telegram test: {Result}", ok ? "sent" : "failed");
                return;
            }

            // Create cycle runner (shared logic for all modes)
            var runner = new CycleRunner(config, state, telegram);

            // ── --once: single headless cycle ──────────────────────────────────
            if (parsed.Once)
            {
                var scheduler = new MskScheduler(config.Schedule, ct => runner.RunAsync(ct));
                scheduler.RunOnceAsync().GetAwaiter().GetResult();
                return;
            }

            // ── --daemon: headless scheduled loop ──────────────────────────────
            if (parsed.Daemon)
            {
                RunHeadlessDaemon(config, runner);
                return;
            }
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

    /// <summary>
    /// Headless daemon: scheduler loop with Ctrl+C graceful shutdown.
    /// </summary>
    static void RunHeadlessDaemon(AppConfig config, CycleRunner runner)
    {
        using var cts = new CancellationTokenSource();

        Console.CancelKeyPress += (_, e) =>
        {
            e.Cancel = true;
            Log.Information("Ctrl+C received, shutting down...");
            cts.Cancel();
        };

        var scheduler = new MskScheduler(config.Schedule, ct => runner.RunAsync(ct));

        scheduler.NextRunComputed += nextUtc =>
        {
            var msk = TimeZoneInfo.ConvertTimeFromUtc(nextUtc,
                TimeZoneInfo.FindSystemTimeZoneById("Russian Standard Time"));
            Console.WriteLine($"Next run: {msk:yyyy-MM-dd HH:mm:ss} MSK");
        };

        try
        {
            scheduler.RunDaemonAsync(cts.Token).GetAwaiter().GetResult();
        }
        catch (OperationCanceledException)
        {
            Log.Information("Daemon shutdown complete.");
        }
    }
}
