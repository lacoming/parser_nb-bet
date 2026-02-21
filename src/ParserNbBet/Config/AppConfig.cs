using System.Text.Json.Serialization;

namespace ParserNbBet.Config;

public sealed class AppConfig
{
    [JsonPropertyName("schedule")]
    public ScheduleConfig Schedule { get; set; } = new();

    [JsonPropertyName("telegram")]
    public TelegramConfig Telegram { get; set; } = new();

    [JsonPropertyName("proxies")]
    public ProxyConfig Proxies { get; set; } = new();

    [JsonPropertyName("thresholds")]
    public ThresholdConfig Thresholds { get; set; } = new();

    [JsonPropertyName("files")]
    public FilesConfig Files { get; set; } = new();

    [JsonPropertyName("ui")]
    public UiConfig Ui { get; set; } = new();

    [JsonPropertyName("kush")]
    public KushConfig Kush { get; set; } = new();

    [JsonPropertyName("nb")]
    public NbConfig Nb { get; set; } = new();

    [JsonPropertyName("logging")]
    public LoggingConfig Logging { get; set; } = new();
}

public sealed class ScheduleConfig
{
    [JsonPropertyName("start_time_msk")]
    public string StartTimeMsk { get; set; } = "08:00";

    [JsonPropertyName("interval_hours")]
    public int IntervalHours { get; set; } = 4;

    [JsonPropertyName("window_days")]
    public int WindowDays { get; set; } = 14;

    [JsonPropertyName("enabled")]
    public bool Enabled { get; set; } = true;
}

public sealed class TelegramConfig
{
    [JsonPropertyName("token")]
    public string Token { get; set; } = "";

    [JsonPropertyName("chat_ids")]
    public List<long> ChatIds { get; set; } = [];

    [JsonPropertyName("dev_chat_id")]
    public long DevChatId { get; set; }

    [JsonPropertyName("rate_limit_seconds")]
    public double RateLimitSeconds { get; set; } = 1.0;
}

public sealed class ProxyConfig
{
    [JsonPropertyName("enabled")]
    public bool Enabled { get; set; }

    [JsonPropertyName("file")]
    public string File { get; set; } = "proxies.txt";

    [JsonPropertyName("rotate")]
    public bool Rotate { get; set; } = true;
}

public sealed class ThresholdConfig
{
    [JsonPropertyName("roi")]
    public double Roi { get; set; } = 0.05;

    [JsonPropertyName("default_ratio")]
    public double DefaultRatio { get; set; } = 1.10;

    [JsonPropertyName("big_league_ratio")]
    public double BigLeagueRatio { get; set; } = 1.05;

    [JsonPropertyName("big_leagues")]
    public List<string> BigLeagues { get; set; } = [];
}

public sealed class FilesConfig
{
    [JsonPropertyName("leagues_xlsx_path")]
    public string LeaguesXlsxPath { get; set; } = "leagues.xlsx";

    [JsonPropertyName("output_dir")]
    public string OutputDir { get; set; } = "output";

    [JsonPropertyName("logs_dir")]
    public string LogsDir { get; set; } = "logs";
}

public sealed class UiConfig
{
    [JsonPropertyName("tray_enabled")]
    public bool TrayEnabled { get; set; } = true;

    [JsonPropertyName("icon_path")]
    public string IconPath { get; set; } = "assets/icon.ico";
}

public sealed class KushConfig
{
    [JsonPropertyName("base_url")]
    public string BaseUrl { get; set; } = "https://kushvsporte.ru/";

    [JsonPropertyName("login")]
    public string Login { get; set; } = "";

    [JsonPropertyName("password")]
    public string Password { get; set; } = "";

    [JsonPropertyName("dry_run")]
    public bool DryRun { get; set; } = true;

    [JsonPropertyName("default_stake")]
    public int DefaultStake { get; set; } = 100;

    [JsonPropertyName("match_time_tolerance_hours")]
    public int MatchTimeToleranceHours { get; set; } = 2;

    [JsonPropertyName("min_confidence")]
    public double MinConfidence { get; set; } = 0.80;
}

public sealed class NbConfig
{
    [JsonPropertyName("base_url")]
    public string BaseUrl { get; set; } = "https://app.nb-bet.com";

    [JsonPropertyName("timeout_seconds")]
    public int TimeoutSeconds { get; set; } = 30;

    [JsonPropertyName("retries")]
    public int Retries { get; set; } = 3;

    [JsonPropertyName("retry_delay_seconds")]
    public int RetryDelaySeconds { get; set; } = 5;
}

public sealed class LoggingConfig
{
    [JsonPropertyName("level")]
    public string Level { get; set; } = "Information";

    [JsonPropertyName("file_size_limit_bytes")]
    public long FileSizeLimitBytes { get; set; } = 10_485_760;

    [JsonPropertyName("retained_file_count")]
    public int RetainedFileCount { get; set; } = 5;

    [JsonPropertyName("output_template")]
    public string OutputTemplate { get; set; } =
        "{Timestamp:yyyy-MM-dd HH:mm:ss.fff} [{Level:u3}] {SourceContext}: {Message:lj}{NewLine}{Exception}";
}
