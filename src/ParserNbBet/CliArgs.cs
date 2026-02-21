namespace ParserNbBet;

/// <summary>
/// Parsed command-line arguments.
/// </summary>
public sealed record CliArgs(
    bool Once,
    bool Daemon,
    bool DryRun,
    bool TestTelegram,
    string ConfigPath
)
{
    public static CliArgs Parse(string[] args)
    {
        bool once         = args.Contains("--once",          StringComparer.OrdinalIgnoreCase);
        bool daemon       = args.Contains("--daemon",        StringComparer.OrdinalIgnoreCase);
        bool dryRun       = args.Contains("--dry-run",       StringComparer.OrdinalIgnoreCase);
        bool testTelegram = args.Contains("--test-telegram", StringComparer.OrdinalIgnoreCase);

        string configPath = "config.json";
        for (int i = 0; i < args.Length - 1; i++)
        {
            if (string.Equals(args[i], "--config", StringComparison.OrdinalIgnoreCase))
            {
                configPath = args[i + 1];
                break;
            }
        }

        return new CliArgs(once, daemon, dryRun, testTelegram, configPath);
    }
}
