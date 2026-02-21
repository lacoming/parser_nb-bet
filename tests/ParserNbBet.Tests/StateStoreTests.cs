using ParserNbBet.State;
using Xunit;

namespace ParserNbBet.Tests;

public class StateStoreTests : IDisposable
{
    private readonly string _dbPath;
    private readonly StateStore _store;

    public StateStoreTests()
    {
        _dbPath = Path.Combine(Path.GetTempPath(), $"test_state_{Guid.NewGuid():N}.db");
        _store = new StateStore(_dbPath);
    }

    public void Dispose()
    {
        _store.Dispose();
        // SQLite connection pooling keeps the file locked; clear the pool first.
        Microsoft.Data.Sqlite.SqliteConnection.ClearAllPools();
        if (File.Exists(_dbPath))
            File.Delete(_dbPath);
    }

    [Fact]
    public void Init_CreatesDatabase()
    {
        Assert.True(File.Exists(_dbPath));
        Assert.Equal(0, _store.PendingCount());
    }

    [Fact]
    public void Enqueue_AddsPendingMatch()
    {
        var result = _store.Enqueue(
            "EPL|Arsenal|Chelsea|20260301", "EPL", "Arsenal", "Chelsea",
            new DateTime(2026, 3, 1, 15, 0, 0, DateTimeKind.Utc), "/match/1", "1X");

        Assert.True(result);
        Assert.Equal(1, _store.PendingCount());
    }

    [Fact]
    public void Enqueue_Dedup_ReturnsFalse()
    {
        var key = "EPL|Arsenal|Chelsea|20260301";
        _store.Enqueue(key, "EPL", "Arsenal", "Chelsea",
            new DateTime(2026, 3, 1, 15, 0, 0, DateTimeKind.Utc), "/match/1", "1X");

        var result = _store.Enqueue(key, "EPL", "Arsenal", "Chelsea",
            new DateTime(2026, 3, 1, 15, 0, 0, DateTimeKind.Utc), "/match/1", "1X");

        Assert.False(result);
        Assert.Equal(1, _store.PendingCount());
    }

    [Fact]
    public void IsKnown_ReturnsTrueForPending()
    {
        var key = "La Liga|Barca|Real|20260305";
        _store.Enqueue(key, "La Liga", "Barca", "Real",
            new DateTime(2026, 3, 5, 20, 0, 0, DateTimeKind.Utc), "/match/2", "2");

        Assert.True(_store.IsKnown(key));
        Assert.False(_store.IsKnown("unknown|key|here|20260101"));
    }

    [Fact]
    public void RemovePending_RemovesMatch()
    {
        var key = "EPL|Arsenal|Chelsea|20260301";
        _store.Enqueue(key, "EPL", "Arsenal", "Chelsea",
            new DateTime(2026, 3, 1, 15, 0, 0, DateTimeKind.Utc), "/match/1", "1X");

        var removed = _store.RemovePending(key);

        Assert.True(removed);
        Assert.Equal(0, _store.PendingCount());
    }

    [Fact]
    public void GetDuePending_ReturnsOnlyDueMatches()
    {
        // This match is due now (default next_check_at = now)
        _store.Enqueue("key1", "EPL", "A", "B",
            DateTime.UtcNow.AddDays(1), "/1", "1X");

        // Set next match to far future
        _store.Enqueue("key2", "EPL", "C", "D",
            DateTime.UtcNow.AddDays(2), "/2", "2");
        _store.UpdateNextCheck("key2", DateTime.UtcNow.AddHours(24));

        var due = _store.GetDuePending();

        Assert.Single(due);
        Assert.Equal("key1", due[0].MatchKey);
    }

    [Fact]
    public void RecordBet_AndIsKnown()
    {
        var key = "Serie A|Inter|Milan|20260310";
        _store.RecordBet(key, "1", "kush123", 2.1, 2.3, 100, 1.12, true);

        Assert.True(_store.IsKnown(key));
    }
}
