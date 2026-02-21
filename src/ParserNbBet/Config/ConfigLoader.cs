using System.Text.Json;

namespace ParserNbBet.Config;

public static class ConfigLoader
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        ReadCommentHandling = JsonCommentHandling.Skip,
        AllowTrailingCommas = true,
    };

    /// <summary>
    /// Load config from JSON file, apply env overrides, validate.
    /// Returns default config if file doesn't exist.
    /// </summary>
    public static AppConfig Load(string path)
    {
        AppConfig config;

        if (File.Exists(path))
        {
            var json = File.ReadAllText(path);
            config = JsonSerializer.Deserialize<AppConfig>(json, JsonOptions)
                     ?? new AppConfig();
        }
        else
        {
            config = new AppConfig();
        }

        ApplyEnvironmentOverrides(config);
        Validate(config);

        return config;
    }

    private static void ApplyEnvironmentOverrides(AppConfig config)
    {
        var tgToken = Environment.GetEnvironmentVariable("NB_TG_TOKEN");
        if (!string.IsNullOrEmpty(tgToken))
            config.Telegram.Token = tgToken;

        var dryRun = Environment.GetEnvironmentVariable("NB_DRY_RUN");
        if (dryRun == "1" || string.Equals(dryRun, "true", StringComparison.OrdinalIgnoreCase))
            config.Kush.DryRun = true;
    }

    /// <summary>
    /// Validate config values. Throws <see cref="ConfigValidationException"/> on errors.
    /// </summary>
    public static void Validate(AppConfig config)
    {
        var errors = new List<string>();

        // Schedule
        if (config.Schedule.IntervalHours < 1 || config.Schedule.IntervalHours > 24)
            errors.Add("schedule.interval_hours must be between 1 and 24.");
        if (config.Schedule.WindowDays < 1 || config.Schedule.WindowDays > 365)
            errors.Add("schedule.window_days must be between 1 and 365.");
        if (!TimeOnly.TryParse(config.Schedule.StartTimeMsk, out _))
            errors.Add($"schedule.start_time_msk '{config.Schedule.StartTimeMsk}' is not a valid time (expected HH:mm).");

        // Thresholds
        if (config.Thresholds.Roi < 0 || config.Thresholds.Roi > 1)
            errors.Add("thresholds.roi must be between 0 and 1.");
        if (config.Thresholds.DefaultRatio <= 1)
            errors.Add("thresholds.default_ratio must be > 1.");
        if (config.Thresholds.BigLeagueRatio <= 1)
            errors.Add("thresholds.big_league_ratio must be > 1.");

        // Kush
        if (config.Kush.DefaultStake < 1)
            errors.Add("kush.default_stake must be >= 1.");
        if (config.Kush.MatchTimeToleranceHours < 0)
            errors.Add("kush.match_time_tolerance_hours must be >= 0.");
        if (config.Kush.MinConfidence < 0 || config.Kush.MinConfidence > 1)
            errors.Add("kush.min_confidence must be between 0 and 1.");

        // NB
        if (config.Nb.TimeoutSeconds < 1)
            errors.Add("nb.timeout_seconds must be >= 1.");
        if (config.Nb.Retries < 0)
            errors.Add("nb.retries must be >= 0.");

        // Logging
        if (config.Logging.FileSizeLimitBytes < 1024)
            errors.Add("logging.file_size_limit_bytes must be >= 1024.");
        if (config.Logging.RetainedFileCount < 1)
            errors.Add("logging.retained_file_count must be >= 1.");

        // Telegram rate limit
        if (config.Telegram.RateLimitSeconds < 0)
            errors.Add("telegram.rate_limit_seconds must be >= 0.");

        if (errors.Count > 0)
            throw new ConfigValidationException(errors);
    }
}

public sealed class ConfigValidationException : Exception
{
    public IReadOnlyList<string> Errors { get; }

    public ConfigValidationException(IReadOnlyList<string> errors)
        : base("Config validation failed:\n" + string.Join("\n", errors.Select(e => $"  - {e}")))
    {
        Errors = errors;
    }
}
