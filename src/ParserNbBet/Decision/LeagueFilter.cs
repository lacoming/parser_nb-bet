using ParserNbBet.Nb;
using Serilog;

namespace ParserNbBet.Decision;

/// <summary>
/// Filters matches: keeps only those whose league appears in at least one <see cref="LeagueSetting"/>.
/// Uses the league name replacement dictionary (sl_chemps_zamen.json) to normalize NB league names
/// before comparison.
/// </summary>
public sealed class LeagueFilter
{
    private readonly List<LeagueSetting> _settings;
    private readonly Dictionary<string, string> _leagueRenames;

    /// <param name="settings">Strategies loaded from leagues.xlsx.</param>
    /// <param name="leagueRenames">
    /// Optional NB→Kush league name mapping (sl_chemps_zamen.json).
    /// Key = NB league name, Value = normalized Kush league name.
    /// </param>
    public LeagueFilter(List<LeagueSetting> settings, Dictionary<string, string>? leagueRenames = null)
    {
        _settings = settings;
        _leagueRenames = leagueRenames ?? [];
    }

    /// <summary>
    /// Returns only matches whose league (after rename) appears in at least one strategy.
    /// Also attaches the matching <see cref="LeagueSetting"/> via out parameter.
    /// </summary>
    public List<(Match Match, LeagueSetting Setting)> Filter(IReadOnlyList<Match> matches)
    {
        var result = new List<(Match, LeagueSetting)>();

        // Build a lookup: normalized league name → list of settings that include it
        var lookup = new Dictionary<string, List<LeagueSetting>>(StringComparer.OrdinalIgnoreCase);
        foreach (var s in _settings)
        {
            foreach (var league in s.Leagues)
            {
                if (!lookup.TryGetValue(league, out var list))
                {
                    list = [];
                    lookup[league] = list;
                }
                list.Add(s);
            }
        }

        foreach (var match in matches)
        {
            // Try renamed league name first, then original
            var normalizedLeague = NormalizeLeague(match.League);

            if (lookup.TryGetValue(normalizedLeague, out var settings))
            {
                // Pick the first matching strategy (could be multiple — take first)
                result.Add((match, settings[0]));
            }
        }

        Log.Information("LeagueFilter: {Passed}/{Total} matches passed league filter",
            result.Count, matches.Count);

        return result;
    }

    /// <summary>
    /// Normalize an NB league name using the rename dictionary.
    /// If no rename exists, returns the original trimmed name.
    /// </summary>
    public string NormalizeLeague(string nbLeagueName)
    {
        var trimmed = nbLeagueName.Trim();
        return _leagueRenames.TryGetValue(trimmed, out var renamed)
            ? renamed
            : trimmed;
    }
}
