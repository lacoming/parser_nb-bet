using Microsoft.Data.Sqlite;

namespace ParserNbBet.State;

/// <summary>
/// SQLite-backed persistent state: pending match queue + dedup by match_key.
/// </summary>
public sealed class StateStore : IDisposable
{
    private readonly SqliteConnection _conn;

    public StateStore(string dbPath = "state.db")
    {
        var dir = Path.GetDirectoryName(dbPath);
        if (!string.IsNullOrEmpty(dir))
            Directory.CreateDirectory(dir);

        _conn = new SqliteConnection($"Data Source={dbPath}");
        _conn.Open();
        InitSchema();
    }

    private void InitSchema()
    {
        using var cmd = _conn.CreateCommand();
        cmd.CommandText = """
            CREATE TABLE IF NOT EXISTS pending_matches (
                match_key       TEXT PRIMARY KEY,
                league          TEXT NOT NULL,
                team_home       TEXT NOT NULL,
                team_away       TEXT NOT NULL,
                start_time_utc  TEXT NOT NULL,
                nb_url          TEXT NOT NULL DEFAULT '',
                bet_type        TEXT NOT NULL DEFAULT '',
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                next_check_at   TEXT NOT NULL DEFAULT (datetime('now')),
                attempts        INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS placed_bets (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                match_key       TEXT NOT NULL,
                bet_type        TEXT NOT NULL,
                kush_event_id   TEXT NOT NULL DEFAULT '',
                odds_nb         REAL NOT NULL DEFAULT 0,
                odds_kush       REAL NOT NULL DEFAULT 0,
                stake           REAL NOT NULL DEFAULT 0,
                ratio           REAL NOT NULL DEFAULT 0,
                placed_at       TEXT NOT NULL DEFAULT (datetime('now')),
                dry_run         INTEGER NOT NULL DEFAULT 1
            );

            CREATE INDEX IF NOT EXISTS idx_pending_next_check
                ON pending_matches(next_check_at);
            """;
        cmd.ExecuteNonQuery();
    }

    /// <summary>
    /// Enqueue a match to the pending queue. Returns false if already exists (dedup).
    /// </summary>
    public bool Enqueue(string matchKey, string league, string teamHome, string teamAway,
        DateTime startTimeUtc, string nbUrl, string betType)
    {
        using var cmd = _conn.CreateCommand();
        cmd.CommandText = """
            INSERT OR IGNORE INTO pending_matches
                (match_key, league, team_home, team_away, start_time_utc, nb_url, bet_type)
            VALUES
                (@key, @league, @home, @away, @start, @url, @bet)
            """;
        cmd.Parameters.AddWithValue("@key", matchKey);
        cmd.Parameters.AddWithValue("@league", league);
        cmd.Parameters.AddWithValue("@home", teamHome);
        cmd.Parameters.AddWithValue("@away", teamAway);
        cmd.Parameters.AddWithValue("@start", startTimeUtc.ToString("o"));
        cmd.Parameters.AddWithValue("@url", nbUrl);
        cmd.Parameters.AddWithValue("@bet", betType);

        return cmd.ExecuteNonQuery() > 0;
    }

    /// <summary>
    /// Get all pending matches whose next_check_at is due.
    /// </summary>
    public IReadOnlyList<PendingMatch> GetDuePending()
    {
        using var cmd = _conn.CreateCommand();
        cmd.CommandText = """
            SELECT match_key, league, team_home, team_away, start_time_utc,
                   nb_url, bet_type, created_at, next_check_at, attempts
            FROM pending_matches
            WHERE next_check_at <= datetime('now')
            ORDER BY next_check_at
            """;

        var list = new List<PendingMatch>();
        using var reader = cmd.ExecuteReader();
        while (reader.Read())
        {
            list.Add(new PendingMatch(
                MatchKey: reader.GetString(0),
                League: reader.GetString(1),
                TeamHome: reader.GetString(2),
                TeamAway: reader.GetString(3),
                StartTimeUtc: DateTime.Parse(reader.GetString(4)),
                NbUrl: reader.GetString(5),
                BetType: reader.GetString(6),
                CreatedAt: DateTime.Parse(reader.GetString(7)),
                NextCheckAt: DateTime.Parse(reader.GetString(8)),
                Attempts: reader.GetInt32(9)
            ));
        }

        return list;
    }

    /// <summary>
    /// Update next_check_at and increment attempts for a pending match.
    /// </summary>
    public void UpdateNextCheck(string matchKey, DateTime nextCheckAt)
    {
        using var cmd = _conn.CreateCommand();
        cmd.CommandText = """
            UPDATE pending_matches
            SET next_check_at = @next, attempts = attempts + 1
            WHERE match_key = @key
            """;
        cmd.Parameters.AddWithValue("@key", matchKey);
        cmd.Parameters.AddWithValue("@next", nextCheckAt.ToString("o"));
        cmd.ExecuteNonQuery();
    }

    /// <summary>
    /// Remove a match from the pending queue (e.g. after placing or expiring).
    /// </summary>
    public bool RemovePending(string matchKey)
    {
        using var cmd = _conn.CreateCommand();
        cmd.CommandText = "DELETE FROM pending_matches WHERE match_key = @key";
        cmd.Parameters.AddWithValue("@key", matchKey);
        return cmd.ExecuteNonQuery() > 0;
    }

    /// <summary>
    /// Record a placed bet.
    /// </summary>
    public void RecordBet(string matchKey, string betType, string kushEventId,
        double oddsNb, double oddsKush, double stake, double ratio, bool dryRun)
    {
        using var cmd = _conn.CreateCommand();
        cmd.CommandText = """
            INSERT INTO placed_bets
                (match_key, bet_type, kush_event_id, odds_nb, odds_kush, stake, ratio, dry_run)
            VALUES
                (@key, @bet, @eid, @onb, @ok, @stake, @ratio, @dry)
            """;
        cmd.Parameters.AddWithValue("@key", matchKey);
        cmd.Parameters.AddWithValue("@bet", betType);
        cmd.Parameters.AddWithValue("@eid", kushEventId);
        cmd.Parameters.AddWithValue("@onb", oddsNb);
        cmd.Parameters.AddWithValue("@ok", oddsKush);
        cmd.Parameters.AddWithValue("@stake", stake);
        cmd.Parameters.AddWithValue("@ratio", ratio);
        cmd.Parameters.AddWithValue("@dry", dryRun ? 1 : 0);
        cmd.ExecuteNonQuery();
    }

    /// <summary>
    /// Check if a match_key already exists in pending or placed_bets.
    /// </summary>
    public bool IsKnown(string matchKey)
    {
        using var cmd = _conn.CreateCommand();
        cmd.CommandText = """
            SELECT 1 FROM pending_matches WHERE match_key = @key
            UNION ALL
            SELECT 1 FROM placed_bets WHERE match_key = @key
            LIMIT 1
            """;
        cmd.Parameters.AddWithValue("@key", matchKey);
        return cmd.ExecuteScalar() is not null;
    }

    /// <summary>
    /// Count pending matches.
    /// </summary>
    public int PendingCount()
    {
        using var cmd = _conn.CreateCommand();
        cmd.CommandText = "SELECT COUNT(*) FROM pending_matches";
        return Convert.ToInt32(cmd.ExecuteScalar());
    }

    public void Dispose()
    {
        _conn.Dispose();
    }
}

public sealed record PendingMatch(
    string MatchKey,
    string League,
    string TeamHome,
    string TeamAway,
    DateTime StartTimeUtc,
    string NbUrl,
    string BetType,
    DateTime CreatedAt,
    DateTime NextCheckAt,
    int Attempts
);
