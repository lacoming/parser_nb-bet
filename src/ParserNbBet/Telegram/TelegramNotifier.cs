using System.Globalization;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using ParserNbBet.Config;
using ParserNbBet.Kush;
using ParserNbBet.Nb;
using Serilog;

namespace ParserNbBet.Telegram;

/// <summary>
/// Sends notifications to Telegram chats via Bot API (sendMessage).
/// Supports rate-limiting, multiple chats, and markdown formatting.
/// </summary>
public sealed class TelegramNotifier : IDisposable
{
    private readonly TelegramConfig _config;
    private readonly HttpClient _http;
    private readonly SemaphoreSlim _rateLimiter = new(1, 1);
    private DateTime _lastSendUtc = DateTime.MinValue;

    private static readonly ILogger Logger = Log.ForContext<TelegramNotifier>();

    public TelegramNotifier(TelegramConfig config, HttpClient? httpClient = null)
    {
        _config = config;
        _http = httpClient ?? new HttpClient { Timeout = TimeSpan.FromSeconds(30) };
    }

    /// <summary>Whether Telegram notifications are configured (token + at least one chat).</summary>
    public bool IsConfigured =>
        !string.IsNullOrWhiteSpace(_config.Token) && _config.ChatIds.Count > 0;

    // --- Public notification methods ---

    /// <summary>Notify: bet placed (or dry-run).</summary>
    public async Task NotifyPlacedAsync(Match match, BetResult bet)
    {
        if (!IsConfigured) return;

        var prefix = bet.DryRun ? "🧪 DRY-RUN" : "✅ СТАВКА";
        var text = FormatPlaced(prefix, match, bet);
        await SendToAllAsync(text);
    }

    /// <summary>Notify: match not found on Kush (enqueued to pending).</summary>
    public async Task NotifyMissingAsync(Match match, string reason)
    {
        if (!IsConfigured) return;

        var text = FormatMissing(match, reason);
        await SendToAllAsync(text);
    }

    /// <summary>Notify: critical error.</summary>
    public async Task NotifyCriticalErrorAsync(string context, Exception ex)
    {
        if (!IsConfigured) return;

        var text = FormatCriticalError(context, ex);
        // Send to dev chat only (if configured), otherwise all chats
        if (_config.DevChatId != 0)
        {
            await SendMessageAsync(_config.DevChatId, text);
        }
        else
        {
            await SendToAllAsync(text);
        }
    }

    /// <summary>Notify: cycle summary.</summary>
    public async Task NotifyCycleSummaryAsync(int totalNb, int afterFilter, int afterDecision,
        int matched, int placed, int pending, bool isDryRun)
    {
        if (!IsConfigured) return;

        var text = FormatCycleSummary(totalNb, afterFilter, afterDecision,
            matched, placed, pending, isDryRun);
        await SendToAllAsync(text);
    }

    /// <summary>Send a test message to verify configuration.</summary>
    public async Task<bool> SendTestAsync()
    {
        if (!IsConfigured)
        {
            Logger.Warning("Telegram not configured (missing token or chat_ids)");
            return false;
        }

        var text = "🔔 parser\\_nb\\-bet: тестовое сообщение\\. Бот работает\\!";
        return await SendToAllAsync(text);
    }

    // --- Message formatting (static, testable) ---

    public static string FormatPlaced(string prefix, Match match, BetResult bet)
    {
        var c = CultureInfo.InvariantCulture;
        var sb = new StringBuilder();
        sb.AppendLine($"{prefix}");
        sb.AppendLine();
        sb.AppendLine($"⚽ *{Escape(match.League)}*");
        sb.AppendLine($"{Escape(match.TeamHome)} — {Escape(match.TeamAway)}");
        sb.AppendLine(c, $"🕐 {match.StartTimeUtc:dd\\.MM\\.yyyy HH:mm} UTC");
        sb.AppendLine();
        sb.AppendLine($"📊 Тип: *{Escape(bet.BetType)}*");
        sb.AppendLine(c, $"Кф НБ: {bet.OddsNb:F2} → Кф Куш: {bet.OddsKush:F2}");
        sb.AppendLine(c, $"Ratio: {bet.Ratio:F4}");
        sb.AppendLine(c, $"Сумма: {bet.Stake:F0}");

        if (!string.IsNullOrWhiteSpace(bet.Reason))
            sb.AppendLine($"💬 {Escape(bet.Reason)}");

        return sb.ToString().TrimEnd();
    }

    public static string FormatMissing(Match match, string reason)
    {
        var sb = new StringBuilder();
        sb.AppendLine("⚠️ НЕТ НА КУШЕ");
        sb.AppendLine();
        sb.AppendLine($"⚽ *{Escape(match.League)}*");
        sb.AppendLine($"{Escape(match.TeamHome)} — {Escape(match.TeamAway)}");
        sb.AppendLine($"🕐 {match.StartTimeUtc:dd\\.MM\\.yyyy HH:mm} UTC");
        sb.AppendLine();
        sb.AppendLine($"📋 Добавлено в очередь ожидания");

        if (!string.IsNullOrWhiteSpace(reason))
            sb.AppendLine($"💬 {Escape(reason)}");

        return sb.ToString().TrimEnd();
    }

    public static string FormatCriticalError(string context, Exception ex)
    {
        var sb = new StringBuilder();
        sb.AppendLine("🚨 КРИТИЧЕСКАЯ ОШИБКА");
        sb.AppendLine();
        sb.AppendLine($"📍 {Escape(context)}");
        sb.AppendLine($"❌ {Escape(ex.GetType().Name)}: {Escape(ex.Message)}");
        return sb.ToString().TrimEnd();
    }

    public static string FormatCycleSummary(int totalNb, int afterFilter, int afterDecision,
        int matched, int placed, int pending, bool isDryRun)
    {
        var sb = new StringBuilder();
        sb.AppendLine(isDryRun ? "📊 ИТОГИ ЦИКЛА \\(dry\\-run\\)" : "📊 ИТОГИ ЦИКЛА");
        sb.AppendLine();
        sb.AppendLine($"Матчей NB: {totalNb}");
        sb.AppendLine($"После фильтра лиг: {afterFilter}");
        sb.AppendLine($"Прошли условия: {afterDecision}");
        sb.AppendLine($"Найдено на Куше: {matched}");
        sb.AppendLine($"Ставок: {placed}");
        sb.AppendLine($"В ожидании: {pending}");
        return sb.ToString().TrimEnd();
    }

    /// <summary>
    /// Escape special chars for Telegram MarkdownV2.
    /// </summary>
    public static string Escape(string text)
    {
        if (string.IsNullOrEmpty(text)) return text;

        // MarkdownV2 requires escaping: _ * [ ] ( ) ~ ` > # + - = | { } . !
        var sb = new StringBuilder(text.Length + 8);
        foreach (var c in text)
        {
            if ("_*[]()~`>#+-=|{}.!".Contains(c))
                sb.Append('\\');
            sb.Append(c);
        }
        return sb.ToString();
    }

    // --- HTTP sending ---

    private async Task<bool> SendToAllAsync(string text)
    {
        var allOk = true;
        foreach (var chatId in _config.ChatIds)
        {
            var ok = await SendMessageAsync(chatId, text);
            if (!ok) allOk = false;
        }
        return allOk;
    }

    internal async Task<bool> SendMessageAsync(long chatId, string text)
    {
        await RateLimitAsync();

        var url = $"https://api.telegram.org/bot{_config.Token}/sendMessage";
        var payload = new TelegramSendMessageRequest
        {
            ChatId = chatId,
            Text = text,
            ParseMode = "MarkdownV2",
            DisableWebPagePreview = true,
        };

        try
        {
            var response = await _http.PostAsJsonAsync(url, payload);
            var body = await response.Content.ReadAsStringAsync();

            if (!response.IsSuccessStatusCode)
            {
                Logger.Warning("Telegram send failed: {Status} {Body}", (int)response.StatusCode, body);

                // If MarkdownV2 parsing fails, retry as plain text
                if (body.Contains("can't parse entities"))
                {
                    Logger.Debug("Retrying as plain text...");
                    payload.ParseMode = null;
                    payload.Text = StripMarkdown(text);
                    response = await _http.PostAsJsonAsync(url, payload);
                    if (response.IsSuccessStatusCode)
                    {
                        Logger.Debug("Plain text retry succeeded for chat {ChatId}", chatId);
                        return true;
                    }
                }

                return false;
            }

            Logger.Debug("Telegram sent to {ChatId}", chatId);
            return true;
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            Logger.Warning(ex, "Telegram send error for chat {ChatId}", chatId);
            return false;
        }
    }

    private async Task RateLimitAsync()
    {
        await _rateLimiter.WaitAsync();
        try
        {
            var elapsed = DateTime.UtcNow - _lastSendUtc;
            var delay = TimeSpan.FromSeconds(_config.RateLimitSeconds) - elapsed;
            if (delay > TimeSpan.Zero)
            {
                Logger.Debug("Telegram rate-limit: waiting {Delay:F1}s", delay.TotalSeconds);
                await Task.Delay(delay);
            }
            _lastSendUtc = DateTime.UtcNow;
        }
        finally
        {
            _rateLimiter.Release();
        }
    }

    private static string StripMarkdown(string text)
    {
        // Remove MarkdownV2 escape backslashes
        return text.Replace("\\", "");
    }

    public void Dispose()
    {
        _rateLimiter.Dispose();
        _http.Dispose();
    }
}

// --- Internal DTOs for Telegram API ---

internal sealed class TelegramSendMessageRequest
{
    [JsonPropertyName("chat_id")]
    public long ChatId { get; set; }

    [JsonPropertyName("text")]
    public string Text { get; set; } = "";

    [JsonPropertyName("parse_mode")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? ParseMode { get; set; }

    [JsonPropertyName("disable_web_page_preview")]
    public bool DisableWebPagePreview { get; set; }
}
