using ParserNbBet.Config;
using Xunit;

namespace ParserNbBet.Tests;

public class ConfigTests
{
    [Fact]
    public void Load_DefaultConfig_WhenFileDoesNotExist()
    {
        var config = ConfigLoader.Load("nonexistent_config_12345.json");

        Assert.Equal("08:00", config.Schedule.StartTimeMsk);
        Assert.Equal(4, config.Schedule.IntervalHours);
        Assert.True(config.Kush.DryRun);
        Assert.Equal("Information", config.Logging.Level);
    }

    [Fact]
    public void Load_ParsesJsonCorrectly()
    {
        var tmpFile = Path.GetTempFileName();
        try
        {
            var json = """
                {
                  "schedule": { "interval_hours": 6, "window_days": 7 },
                  "thresholds": { "roi": 0.10, "default_ratio": 1.15 },
                  "nb": { "timeout_seconds": 60 }
                }
                """;
            File.WriteAllText(tmpFile, json);

            var config = ConfigLoader.Load(tmpFile);

            Assert.Equal(6, config.Schedule.IntervalHours);
            Assert.Equal(7, config.Schedule.WindowDays);
            Assert.Equal(0.10, config.Thresholds.Roi);
            Assert.Equal(1.15, config.Thresholds.DefaultRatio);
            Assert.Equal(60, config.Nb.TimeoutSeconds);
            // Defaults preserved for unset fields
            Assert.Equal("08:00", config.Schedule.StartTimeMsk);
            Assert.True(config.Kush.DryRun);
        }
        finally
        {
            File.Delete(tmpFile);
        }
    }

    [Fact]
    public void Validate_ThrowsOnInvalidIntervalHours()
    {
        var config = new AppConfig();
        config.Schedule.IntervalHours = 0;

        var ex = Assert.Throws<ConfigValidationException>(() => ConfigLoader.Validate(config));
        Assert.Contains("interval_hours", ex.Message);
    }

    [Fact]
    public void Validate_ThrowsOnInvalidRoi()
    {
        var config = new AppConfig();
        config.Thresholds.Roi = 2.0;

        var ex = Assert.Throws<ConfigValidationException>(() => ConfigLoader.Validate(config));
        Assert.Contains("roi", ex.Message);
    }

    [Fact]
    public void Validate_ThrowsOnRatioLessThanOne()
    {
        var config = new AppConfig();
        config.Thresholds.DefaultRatio = 0.9;

        var ex = Assert.Throws<ConfigValidationException>(() => ConfigLoader.Validate(config));
        Assert.Contains("default_ratio", ex.Message);
    }

    [Fact]
    public void Validate_ThrowsOnInvalidStartTime()
    {
        var config = new AppConfig();
        config.Schedule.StartTimeMsk = "not-a-time";

        var ex = Assert.Throws<ConfigValidationException>(() => ConfigLoader.Validate(config));
        Assert.Contains("start_time_msk", ex.Message);
    }

    [Fact]
    public void Validate_PassesWithDefaultConfig()
    {
        var config = new AppConfig();
        // Should not throw
        ConfigLoader.Validate(config);
    }

    [Fact]
    public void Validate_MultipleErrors_AreCollected()
    {
        var config = new AppConfig();
        config.Schedule.IntervalHours = 0;
        config.Thresholds.Roi = -1;
        config.Nb.TimeoutSeconds = 0;

        var ex = Assert.Throws<ConfigValidationException>(() => ConfigLoader.Validate(config));
        Assert.True(ex.Errors.Count >= 3);
    }
}
