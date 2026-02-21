namespace ParserNbBet.Kush;

/// <summary>
/// Result of a bet placement attempt.
/// </summary>
public sealed class BetResult
{
    public bool Success { get; }
    public bool DryRun { get; }
    public string BetType { get; }
    public double OddsNb { get; }
    public double OddsKush { get; }
    public double Ratio { get; }
    public double Stake { get; }
    public string KushEventId { get; }
    public string Reason { get; }

    public BetResult(bool success, bool dryRun, string betType,
                     double oddsNb, double oddsKush, double ratio,
                     double stake, string kushEventId, string reason)
    {
        Success = success;
        DryRun = dryRun;
        BetType = betType;
        OddsNb = oddsNb;
        OddsKush = oddsKush;
        Ratio = ratio;
        Stake = stake;
        KushEventId = kushEventId;
        Reason = reason;
    }

    public static BetResult Failed(string reason, string betType = "", string kushEventId = "") =>
        new(false, false, betType, 0, 0, 0, 0, kushEventId, reason);

    public override string ToString() =>
        DryRun
            ? $"[DRY-RUN] {BetType}: ratio={Ratio:F4} kush={OddsKush:F2} nb={OddsNb:F2} stake={Stake} — {Reason}"
            : $"[{(Success ? "OK" : "FAIL")}] {BetType}: ratio={Ratio:F4} kush={OddsKush:F2} nb={OddsNb:F2} stake={Stake} — {Reason}";
}
