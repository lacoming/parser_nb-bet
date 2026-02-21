using ParserNbBet.Config;
using ParserNbBet.Kush;
using ParserNbBet.Nb;
using ParserNbBet.Telegram;
using Xunit;

namespace ParserNbBet.Tests;

public class TelegramNotifierTests
{
    // --- Escape tests ---

    [Fact]
    public void Escape_EmptyString_ReturnsEmpty()
    {
        Assert.Equal("", TelegramNotifier.Escape(""));
    }

    [Fact]
    public void Escape_PlainText_Unchanged()
    {
        Assert.Equal("Hello World", TelegramNotifier.Escape("Hello World"));
    }

    [Fact]
    public void Escape_SpecialChars_AreEscaped()
    {
        // _ * [ ] ( ) ~ ` > # + - = | { } . !
        Assert.Equal("a\\_b\\*c\\[d\\]e", TelegramNotifier.Escape("a_b*c[d]e"));
        Assert.Equal("1\\.0", TelegramNotifier.Escape("1.0"));
        Assert.Equal("test\\!", TelegramNotifier.Escape("test!"));
        Assert.Equal("a\\-b\\+c\\=d", TelegramNotifier.Escape("a-b+c=d"));
    }

    [Fact]
    public void Escape_MixedContent_PreservesText()
    {
        var result = TelegramNotifier.Escape("FC Barcelona (Spain) - La Liga");
        Assert.Equal("FC Barcelona \\(Spain\\) \\- La Liga", result);
    }

    // --- FormatPlaced tests ---

    [Fact]
    public void FormatPlaced_ContainsKeyInfo()
    {
        var match = CreateTestMatch();
        var bet = new BetResult(true, false, "1X", 2.10, 2.30, 1.12, 100, "ev123", "ratio OK");

        var text = TelegramNotifier.FormatPlaced("✅ СТАВКА", match, bet);

        Assert.Contains("СТАВКА", text);
        Assert.Contains("Premier League", text);
        Assert.Contains("Arsenal", text);
        Assert.Contains("Chelsea", text);
        Assert.Contains("1X", text);
        Assert.Contains("2.10", text.Replace("\\", "")); // escaped for MarkdownV2
        Assert.Contains("2.30", text.Replace("\\", ""));
        Assert.Contains("1.1200", text.Replace("\\", "")); // ratio
        Assert.Contains("100", text); // stake
    }

    [Fact]
    public void FormatPlaced_DryRun_HasPrefix()
    {
        var match = CreateTestMatch();
        var bet = new BetResult(false, true, "2", 1.80, 2.00, 1.11, 50, "ev456", "dry-run");

        var text = TelegramNotifier.FormatPlaced("🧪 DRY-RUN", match, bet);

        Assert.Contains("DRY-RUN", text);
    }

    // --- FormatMissing tests ---

    [Fact]
    public void FormatMissing_ContainsTeamsAndReason()
    {
        var match = CreateTestMatch();

        var text = TelegramNotifier.FormatMissing(match, "no events for league");

        Assert.Contains("НЕТ НА КУШЕ", text);
        Assert.Contains("Arsenal", text);
        Assert.Contains("Chelsea", text);
        Assert.Contains("очередь", text);
        Assert.Contains("no events for league", text);
    }

    // --- FormatCriticalError tests ---

    [Fact]
    public void FormatCriticalError_ContainsExceptionInfo()
    {
        var ex = new InvalidOperationException("connection refused");

        var text = TelegramNotifier.FormatCriticalError("NB fetch", ex);

        Assert.Contains("КРИТИЧЕСКАЯ ОШИБКА", text);
        Assert.Contains("NB fetch", text);
        Assert.Contains("InvalidOperationException", text);
        Assert.Contains("connection refused", text);
    }

    // --- FormatCycleSummary tests ---

    [Fact]
    public void FormatCycleSummary_ContainsCounts()
    {
        var text = TelegramNotifier.FormatCycleSummary(100, 50, 20, 15, 10, 5, false);

        Assert.Contains("ИТОГИ ЦИКЛА", text);
        Assert.Contains("100", text);
        Assert.Contains("50", text);
        Assert.Contains("20", text);
        Assert.Contains("15", text);
        Assert.Contains("10", text);
        Assert.Contains("5", text);
    }

    [Fact]
    public void FormatCycleSummary_DryRun_Indicated()
    {
        var text = TelegramNotifier.FormatCycleSummary(10, 5, 2, 1, 1, 0, true);

        Assert.Contains("dry", text, StringComparison.OrdinalIgnoreCase);
    }

    // --- IsConfigured tests ---

    [Fact]
    public void IsConfigured_NoToken_ReturnsFalse()
    {
        var config = new TelegramConfig { Token = "", ChatIds = [123] };
        using var notifier = new TelegramNotifier(config);
        Assert.False(notifier.IsConfigured);
    }

    [Fact]
    public void IsConfigured_NoChatIds_ReturnsFalse()
    {
        var config = new TelegramConfig { Token = "123:abc", ChatIds = [] };
        using var notifier = new TelegramNotifier(config);
        Assert.False(notifier.IsConfigured);
    }

    [Fact]
    public void IsConfigured_TokenAndChats_ReturnsTrue()
    {
        var config = new TelegramConfig { Token = "123:abc", ChatIds = [111, 222] };
        using var notifier = new TelegramNotifier(config);
        Assert.True(notifier.IsConfigured);
    }

    // --- Rate-limiting test ---

    [Fact]
    public async Task NotifyPlaced_NotConfigured_DoesNotThrow()
    {
        var config = new TelegramConfig { Token = "", ChatIds = [] };
        using var notifier = new TelegramNotifier(config);

        var match = CreateTestMatch();
        var bet = new BetResult(true, false, "1", 2.0, 2.1, 1.1, 100, "ev1", "ok");

        // Should return immediately without error
        await notifier.NotifyPlacedAsync(match, bet);
    }

    // --- CliArgs test ---

    [Fact]
    public void CliArgs_TestTelegram_Parsed()
    {
        var args = CliArgs.Parse(["--once", "--test-telegram", "--dry-run"]);
        Assert.True(args.TestTelegram);
        Assert.True(args.Once);
        Assert.True(args.DryRun);
    }

    [Fact]
    public void CliArgs_NoTestTelegram_DefaultFalse()
    {
        var args = CliArgs.Parse(["--once"]);
        Assert.False(args.TestTelegram);
    }

    // --- Helper ---

    private static Match CreateTestMatch()
    {
        return new Match("Premier League", "Arsenal", "Chelsea",
            new DateTime(2026, 3, 15, 18, 0, 0, DateTimeKind.Utc), "arsenal-chelsea", "soccer")
        {
            Odds1End = 2.10,
            OddsXEnd = 3.20,
            Odds2End = 3.50,
        };
    }
}
