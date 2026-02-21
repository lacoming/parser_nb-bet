using ParserNbBet.Ui;

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

        // Headless --once mode: no WinForms, just run cycle and exit
        if (parsed.Once)
        {
            RunHeadless(parsed);
            return;
        }

        // WinForms application (--daemon or default interactive)
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.SetHighDpiMode(HighDpiMode.SystemAware);

        Application.Run(new MainForm(parsed));
    }

    static void RunHeadless(CliArgs args)
    {
        // Stub — will be implemented in Step 04 (config) + Step 12 (scheduler)
        Console.WriteLine("parser_nb-bet starting...");
        Console.WriteLine($"  mode:     once");
        Console.WriteLine($"  dry-run:  {args.DryRun}");
        Console.WriteLine($"  config:   {args.ConfigPath}");
        Console.WriteLine("boot ok");
    }
}
