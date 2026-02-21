using ParserNbBet.Config;
using Serilog;
using Serilog.Events;

namespace ParserNbBet.Logging;

public static class LoggingSetup
{
    /// <summary>
    /// Configure Serilog with file sink (rotation) + console sink.
    /// Call once at application startup. Sets <see cref="Log.Logger"/>.
    /// </summary>
    public static void Initialize(AppConfig config)
    {
        var logsDir = config.Files.LogsDir;
        Directory.CreateDirectory(logsDir);

        var logPath = Path.Combine(logsDir, "parser.log");

        var level = ParseLevel(config.Logging.Level);

        Log.Logger = new LoggerConfiguration()
            .MinimumLevel.Is(level)
            .WriteTo.Console(
                outputTemplate: config.Logging.OutputTemplate)
            .WriteTo.File(
                path: logPath,
                outputTemplate: config.Logging.OutputTemplate,
                fileSizeLimitBytes: config.Logging.FileSizeLimitBytes,
                retainedFileCountLimit: config.Logging.RetainedFileCount,
                rollOnFileSizeLimit: true,
                shared: false)
            .Enrich.FromLogContext()
            .CreateLogger();
    }

    private static LogEventLevel ParseLevel(string level)
    {
        return Enum.TryParse<LogEventLevel>(level, ignoreCase: true, out var parsed)
            ? parsed
            : LogEventLevel.Information;
    }
}
