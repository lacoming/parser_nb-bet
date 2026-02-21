using ParserNbBet.Config;
using Serilog;

namespace ParserNbBet.Scheduler;

/// <summary>
/// Computes next run times based on MSK start time + interval,
/// and runs a loop using PeriodicTimer with graceful shutdown.
/// </summary>
public sealed class MskScheduler : IDisposable
{
    private static readonly TimeZoneInfo MskZone =
        TimeZoneInfo.FindSystemTimeZoneById("Russian Standard Time");

    private readonly ScheduleConfig _config;
    private readonly Func<CancellationToken, Task> _cycleAction;
    private CancellationTokenSource? _cts;

    /// <summary>Fires when the next-run time is computed (for UI).</summary>
    public event Action<DateTime>? NextRunComputed;

    /// <summary>Fires when a cycle starts.</summary>
    public event Action? CycleStarted;

    /// <summary>Fires when a cycle finishes (bool = success).</summary>
    public event Action<bool>? CycleFinished;

    public MskScheduler(ScheduleConfig config, Func<CancellationToken, Task> cycleAction)
    {
        _config = config ?? throw new ArgumentNullException(nameof(config));
        _cycleAction = cycleAction ?? throw new ArgumentNullException(nameof(cycleAction));
    }

    /// <summary>
    /// Runs a single cycle (for --once mode).
    /// </summary>
    public async Task RunOnceAsync(CancellationToken ct = default)
    {
        CycleStarted?.Invoke();
        bool ok = false;
        try
        {
            await _cycleAction(ct);
            ok = true;
        }
        finally
        {
            CycleFinished?.Invoke(ok);
        }
    }

    /// <summary>
    /// Runs the daemon loop: compute next slot, wait, execute cycle, repeat.
    /// </summary>
    public async Task RunDaemonAsync(CancellationToken ct = default)
    {
        _cts = CancellationTokenSource.CreateLinkedTokenSource(ct);
        var token = _cts.Token;

        Log.Information("Daemon started. Schedule: start={Start} MSK, interval={Interval}h",
            _config.StartTimeMsk, _config.IntervalHours);

        while (!token.IsCancellationRequested)
        {
            var nowUtc = DateTime.UtcNow;
            var nextUtc = ComputeNextRunUtc(nowUtc, _config);

            Log.Information("Next run at {NextMsk} MSK ({NextUtc} UTC)",
                TimeZoneInfo.ConvertTimeFromUtc(nextUtc, MskZone).ToString("yyyy-MM-dd HH:mm:ss"),
                nextUtc.ToString("yyyy-MM-dd HH:mm:ss"));

            NextRunComputed?.Invoke(nextUtc);

            var delay = nextUtc - nowUtc;
            if (delay > TimeSpan.Zero)
            {
                try
                {
                    await Task.Delay(delay, token);
                }
                catch (OperationCanceledException)
                {
                    break;
                }
            }

            if (token.IsCancellationRequested) break;

            // Execute cycle
            CycleStarted?.Invoke();
            bool ok = false;
            try
            {
                Log.Information("Cycle starting...");
                await _cycleAction(token);
                ok = true;
                Log.Information("Cycle complete.");
            }
            catch (OperationCanceledException)
            {
                Log.Information("Cycle cancelled.");
                break;
            }
            catch (Exception ex)
            {
                Log.Error(ex, "Cycle failed");
            }
            finally
            {
                CycleFinished?.Invoke(ok);
            }
        }

        Log.Information("Daemon stopped.");
    }

    /// <summary>
    /// Request graceful shutdown.
    /// </summary>
    public void Stop()
    {
        _cts?.Cancel();
    }

    /// <summary>
    /// Computes the next run time (UTC) based on MSK schedule config.
    /// Schedule slots are: startTimeMsk, startTimeMsk + interval, startTimeMsk + 2*interval, ...
    /// Returns the nearest future slot.
    /// </summary>
    public static DateTime ComputeNextRunUtc(DateTime nowUtc, ScheduleConfig config)
    {
        var nowMsk = TimeZoneInfo.ConvertTimeFromUtc(nowUtc, MskZone);

        // Parse start time
        var parts = config.StartTimeMsk.Split(':');
        int startHour = int.Parse(parts[0]);
        int startMinute = parts.Length > 1 ? int.Parse(parts[1]) : 0;

        var intervalHours = config.IntervalHours;

        // Generate all slots for today and tomorrow, find the next one
        for (int dayOffset = 0; dayOffset <= 1; dayOffset++)
        {
            var day = nowMsk.Date.AddDays(dayOffset);
            var slot = new DateTime(day.Year, day.Month, day.Day, startHour, startMinute, 0);

            while (slot.Hour < 24)
            {
                if (slot > nowMsk)
                {
                    // Convert back to UTC
                    return TimeZoneInfo.ConvertTimeToUtc(
                        DateTime.SpecifyKind(slot, DateTimeKind.Unspecified), MskZone);
                }

                slot = slot.AddHours(intervalHours);
                // If we go past midnight, break to next day
                if (slot.Date > day.Date)
                    break;
            }
        }

        // Fallback: first slot tomorrow (should not happen with dayOffset=1 above)
        var tomorrow = nowMsk.Date.AddDays(1);
        var fallback = new DateTime(tomorrow.Year, tomorrow.Month, tomorrow.Day, startHour, startMinute, 0);
        return TimeZoneInfo.ConvertTimeToUtc(
            DateTime.SpecifyKind(fallback, DateTimeKind.Unspecified), MskZone);
    }

    public void Dispose()
    {
        _cts?.Cancel();
        _cts?.Dispose();
    }
}
