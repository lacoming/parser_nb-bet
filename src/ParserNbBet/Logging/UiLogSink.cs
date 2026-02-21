using Serilog.Core;
using Serilog.Events;

namespace ParserNbBet.Logging;

/// <summary>
/// Serilog sink that forwards formatted log lines to a callback.
/// Used by MainForm to display logs in a TextBox.
/// </summary>
public sealed class UiLogSink : ILogEventSink
{
    private readonly Action<string> _writeLine;
    private readonly string _outputTemplate;

    public UiLogSink(Action<string> writeLine, string? outputTemplate = null)
    {
        _writeLine = writeLine ?? throw new ArgumentNullException(nameof(writeLine));
        _outputTemplate = outputTemplate ?? "{Timestamp:HH:mm:ss} [{Level:u3}] {Message:lj}";
    }

    public void Emit(LogEvent logEvent)
    {
        var msg = logEvent.RenderMessage();
        var level = logEvent.Level switch
        {
            LogEventLevel.Verbose     => "VRB",
            LogEventLevel.Debug       => "DBG",
            LogEventLevel.Information => "INF",
            LogEventLevel.Warning     => "WRN",
            LogEventLevel.Error       => "ERR",
            LogEventLevel.Fatal       => "FTL",
            _                         => "???"
        };

        var line = $"{logEvent.Timestamp:HH:mm:ss} [{level}] {msg}";

        if (logEvent.Exception != null)
            line += $" | {logEvent.Exception.GetType().Name}: {logEvent.Exception.Message}";

        _writeLine(line);
    }
}
