namespace ParserNbBet.Decision;

/// <summary>
/// Result of evaluating a match against the ТЗ betting rules.
/// One match can produce multiple decisions (one per bet type: 1X, 1, 2, X).
/// </summary>
public sealed class BetDecision
{
    /// <summary>Bet type: "1X", "1", "2", "X".</summary>
    public string BetType { get; init; } = "";

    /// <summary>True if all conditions for this bet type are satisfied.</summary>
    public bool Passes { get; init; }

    /// <summary>Human-readable reasons explaining pass/fail.</summary>
    public List<string> Reasons { get; init; } = [];
}

/// <summary>
/// Aggregated decision for a match: which bet types pass, overall verdict.
/// </summary>
public sealed class MatchDecision
{
    public string MatchKey { get; init; } = "";

    /// <summary>Individual decisions per bet type.</summary>
    public List<BetDecision> Decisions { get; init; } = [];

    /// <summary>True if at least one bet type passes.</summary>
    public bool AnyPasses => Decisions.Exists(d => d.Passes);

    /// <summary>Returns only passing decisions.</summary>
    public IEnumerable<BetDecision> PassingBets => Decisions.Where(d => d.Passes);
}
