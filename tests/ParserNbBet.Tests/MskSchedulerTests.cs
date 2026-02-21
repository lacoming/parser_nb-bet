using ParserNbBet.Config;
using ParserNbBet.Scheduler;
using Xunit;

namespace ParserNbBet.Tests;

public class MskSchedulerTests
{
    private static readonly TimeZoneInfo MskZone =
        TimeZoneInfo.FindSystemTimeZoneById("Russian Standard Time");

    private static ScheduleConfig DefaultConfig(string start = "08:00", int interval = 4) => new()
    {
        StartTimeMsk = start,
        IntervalHours = interval,
        WindowDays = 14,
        Enabled = true
    };

    // Helper: create a UTC datetime from MSK hour/minute
    private static DateTime MskToUtc(int year, int month, int day, int hour, int minute)
    {
        var msk = new DateTime(year, month, day, hour, minute, 0, DateTimeKind.Unspecified);
        return TimeZoneInfo.ConvertTimeToUtc(msk, MskZone);
    }

    [Fact]
    public void NextSlot_BeforeFirstSlot_ReturnsFirstSlot()
    {
        // 06:30 MSK → next should be 08:00 MSK
        var now = MskToUtc(2026, 2, 21, 6, 30);
        var next = MskScheduler.ComputeNextRunUtc(now, DefaultConfig());
        var nextMsk = TimeZoneInfo.ConvertTimeFromUtc(next, MskZone);

        Assert.Equal(8, nextMsk.Hour);
        Assert.Equal(0, nextMsk.Minute);
        Assert.Equal(21, nextMsk.Day);
    }

    [Fact]
    public void NextSlot_AfterFirstBeforeSecond_ReturnsSecondSlot()
    {
        // 09:00 MSK → next should be 12:00 MSK (08:00 + 4h)
        var now = MskToUtc(2026, 2, 21, 9, 0);
        var next = MskScheduler.ComputeNextRunUtc(now, DefaultConfig());
        var nextMsk = TimeZoneInfo.ConvertTimeFromUtc(next, MskZone);

        Assert.Equal(12, nextMsk.Hour);
        Assert.Equal(0, nextMsk.Minute);
    }

    [Fact]
    public void NextSlot_AfterSecondBeforeThird_ReturnsThirdSlot()
    {
        // 13:00 MSK → next should be 16:00 MSK (08:00 + 8h)
        var now = MskToUtc(2026, 2, 21, 13, 0);
        var next = MskScheduler.ComputeNextRunUtc(now, DefaultConfig());
        var nextMsk = TimeZoneInfo.ConvertTimeFromUtc(next, MskZone);

        Assert.Equal(16, nextMsk.Hour);
        Assert.Equal(0, nextMsk.Minute);
    }

    [Fact]
    public void NextSlot_AfterLastSlot_ReturnsFirstSlotNextDay()
    {
        // 23:00 MSK → next should be 08:00 MSK next day
        var now = MskToUtc(2026, 2, 21, 23, 0);
        var next = MskScheduler.ComputeNextRunUtc(now, DefaultConfig());
        var nextMsk = TimeZoneInfo.ConvertTimeFromUtc(next, MskZone);

        Assert.Equal(8, nextMsk.Hour);
        Assert.Equal(0, nextMsk.Minute);
        Assert.Equal(22, nextMsk.Day);
    }

    [Fact]
    public void NextSlot_ExactlyOnSlot_ReturnsNextSlot()
    {
        // Exactly 08:00 MSK → should not return 08:00, but 12:00
        var now = MskToUtc(2026, 2, 21, 8, 0);
        var next = MskScheduler.ComputeNextRunUtc(now, DefaultConfig());
        var nextMsk = TimeZoneInfo.ConvertTimeFromUtc(next, MskZone);

        Assert.Equal(12, nextMsk.Hour);
    }

    [Fact]
    public void NextSlot_CustomStartTime_Respected()
    {
        // Start at 10:00, interval 6h. At 09:30 → next = 10:00
        var config = DefaultConfig("10:00", 6);
        var now = MskToUtc(2026, 2, 21, 9, 30);
        var next = MskScheduler.ComputeNextRunUtc(now, config);
        var nextMsk = TimeZoneInfo.ConvertTimeFromUtc(next, MskZone);

        Assert.Equal(10, nextMsk.Hour);
        Assert.Equal(0, nextMsk.Minute);
    }

    [Fact]
    public void NextSlot_CustomInterval_Respected()
    {
        // Start at 06:00, interval 3h. At 07:00 → next = 09:00
        var config = DefaultConfig("06:00", 3);
        var now = MskToUtc(2026, 2, 21, 7, 0);
        var next = MskScheduler.ComputeNextRunUtc(now, config);
        var nextMsk = TimeZoneInfo.ConvertTimeFromUtc(next, MskZone);

        Assert.Equal(9, nextMsk.Hour);
        Assert.Equal(0, nextMsk.Minute);
    }

    [Fact]
    public void NextSlot_StartTimeWithMinutes()
    {
        // Start at 08:30, interval 4h. At 08:00 → next = 08:30
        var config = DefaultConfig("08:30", 4);
        var now = MskToUtc(2026, 2, 21, 8, 0);
        var next = MskScheduler.ComputeNextRunUtc(now, config);
        var nextMsk = TimeZoneInfo.ConvertTimeFromUtc(next, MskZone);

        Assert.Equal(8, nextMsk.Hour);
        Assert.Equal(30, nextMsk.Minute);
    }

    [Fact]
    public async Task RunOnce_ExecutesCycleAction()
    {
        bool executed = false;
        var scheduler = new MskScheduler(DefaultConfig(), _ =>
        {
            executed = true;
            return Task.CompletedTask;
        });

        await scheduler.RunOnceAsync();
        Assert.True(executed);
    }

    [Fact]
    public async Task RunOnce_FiresEvents()
    {
        bool started = false, finished = false;
        bool? success = null;
        var scheduler = new MskScheduler(DefaultConfig(), _ => Task.CompletedTask);
        scheduler.CycleStarted += () => started = true;
        scheduler.CycleFinished += ok => { finished = true; success = ok; };

        await scheduler.RunOnceAsync();
        Assert.True(started);
        Assert.True(finished);
        Assert.True(success);
    }

    [Fact]
    public async Task RunOnce_FailedCycle_ReportsFailure()
    {
        bool? success = null;
        var scheduler = new MskScheduler(DefaultConfig(), _ => throw new InvalidOperationException("test"));
        scheduler.CycleFinished += ok => success = ok;

        await Assert.ThrowsAsync<InvalidOperationException>(() => scheduler.RunOnceAsync());
        Assert.False(success);
    }

    [Fact]
    public async Task RunDaemon_PreCancelledToken_ExitsImmediately()
    {
        using var cts = new CancellationTokenSource();
        cts.Cancel();

        var config = DefaultConfig("00:00", 1);
        var scheduler = new MskScheduler(config, _ => Task.CompletedTask);

        // Pre-cancelled token — daemon should exit immediately
        await scheduler.RunDaemonAsync(cts.Token);
    }

    [Fact]
    public async Task RunDaemon_CancelAfterStart_StopsWaiting()
    {
        using var cts = new CancellationTokenSource(TimeSpan.FromMilliseconds(200));
        var scheduler = new MskScheduler(DefaultConfig(), _ => Task.CompletedTask);

        // Will wait for next slot but CTS cancels after 200ms
        await scheduler.RunDaemonAsync(cts.Token);
        // If we reach here, graceful shutdown worked
    }
}
