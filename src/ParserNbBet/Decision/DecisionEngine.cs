using System.Globalization;
using ParserNbBet.Nb;
using Serilog;

namespace ParserNbBet.Decision;

/// <summary>
/// Applies ТЗ betting rules to a match and returns which bet types pass.
///
/// Rules from ТЗ:
///
/// When kf1 > kf2 (home favourite):
///   1X: kf1 ≤ 8, kf1X ≥ 1.5, kf2 ≥ 1.4
///   1:  kf1 ≤ 8, kf2 ≥ 1.4
///   2:  kf2 ≥ 1.5
///   X:  kf1 ≤ 8, kf1X ≥ 1.5, kf2 ≥ 1.4
///
/// When kf2 > kf1 (away favourite):
///   2: kf2 ≤ 8, kf1 ≥ 1.4
///   1: kf1 ≥ 1.5
///
/// Where:
///   kf1 = Odds1End (P1 end odds)
///   kf2 = Odds2End (P2 end odds)
///   kf1X = Odds1XEnd = min(Odds1End, OddsXEnd)
/// </summary>
public static class DecisionEngine
{
    /// <summary>
    /// Evaluate a single match against all applicable bet type rules.
    /// </summary>
    public static MatchDecision Evaluate(Match match)
    {
        var decisions = new List<BetDecision>();

        var kf1 = match.Odds1End;
        var kf2 = match.Odds2End;
        var kfX = match.OddsXEnd;
        var kf1X = match.Odds1XEnd; // min(kf1, kfX)

        // Need at least kf1 and kf2 to decide
        if (!kf1.HasValue || !kf2.HasValue)
        {
            return new MatchDecision
            {
                MatchKey = match.MatchKey,
                Decisions =
                [
                    new BetDecision
                    {
                        BetType = "skip",
                        Passes = false,
                        Reasons = ["Missing odds: kf1 or kf2 is null"]
                    }
                ]
            };
        }

        if (kf1.Value > kf2.Value)
        {
            // Home favourite branch
            decisions.Add(Evaluate1X_HomeFav(kf1.Value, kf2.Value, kf1X));
            decisions.Add(Evaluate1_HomeFav(kf1.Value, kf2.Value));
            decisions.Add(Evaluate2_HomeFav(kf2.Value));
            decisions.Add(EvaluateX_HomeFav(kf1.Value, kf2.Value, kf1X));
        }
        else if (kf2.Value > kf1.Value)
        {
            // Away favourite branch
            decisions.Add(Evaluate2_AwayFav(kf2.Value, kf1.Value));
            decisions.Add(Evaluate1_AwayFav(kf1.Value));
        }
        else
        {
            // kf1 == kf2: equal odds — no clear favourite, skip
            decisions.Add(new BetDecision
            {
                BetType = "skip",
                Passes = false,
                Reasons = [$"kf1 == kf2 ({F(kf1.Value)}), no clear favourite"]
            });
        }

        var result = new MatchDecision
        {
            MatchKey = match.MatchKey,
            Decisions = decisions
        };

        if (result.AnyPasses)
        {
            Log.Debug("DecisionEngine: {MatchKey} — passing bets: {Bets}",
                match.MatchKey,
                string.Join(", ", result.PassingBets.Select(d => d.BetType)));
        }

        return result;
    }

    // ── Home favourite (kf1 > kf2) ──────────────────────────

    private static BetDecision Evaluate1X_HomeFav(double kf1, double kf2, double? kf1X)
    {
        var reasons = new List<string>();
        bool passes = true;

        if (kf1 > 8)
        {
            reasons.Add($"FAIL: kf1={F(kf1)} > 8");
            passes = false;
        }
        else
            reasons.Add($"OK: kf1={F(kf1)} ≤ 8");

        if (!kf1X.HasValue)
        {
            reasons.Add("FAIL: kf1X is null (missing kfX)");
            passes = false;
        }
        else if (kf1X.Value < 1.5)
        {
            reasons.Add($"FAIL: kf1X={F(kf1X.Value)} < 1.5");
            passes = false;
        }
        else
            reasons.Add($"OK: kf1X={F(kf1X.Value)} ≥ 1.5");

        if (kf2 < 1.4)
        {
            reasons.Add($"FAIL: kf2={F(kf2)} < 1.4");
            passes = false;
        }
        else
            reasons.Add($"OK: kf2={F(kf2)} ≥ 1.4");

        return new BetDecision { BetType = "1X", Passes = passes, Reasons = reasons };
    }

    private static BetDecision Evaluate1_HomeFav(double kf1, double kf2)
    {
        var reasons = new List<string>();
        bool passes = true;

        if (kf1 > 8)
        {
            reasons.Add($"FAIL: kf1={F(kf1)} > 8");
            passes = false;
        }
        else
            reasons.Add($"OK: kf1={F(kf1)} ≤ 8");

        if (kf2 < 1.4)
        {
            reasons.Add($"FAIL: kf2={F(kf2)} < 1.4");
            passes = false;
        }
        else
            reasons.Add($"OK: kf2={F(kf2)} ≥ 1.4");

        return new BetDecision { BetType = "1", Passes = passes, Reasons = reasons };
    }

    private static BetDecision Evaluate2_HomeFav(double kf2)
    {
        var reasons = new List<string>();
        bool passes = true;

        if (kf2 < 1.5)
        {
            reasons.Add($"FAIL: kf2={F(kf2)} < 1.5");
            passes = false;
        }
        else
            reasons.Add($"OK: kf2={F(kf2)} ≥ 1.5");

        return new BetDecision { BetType = "2", Passes = passes, Reasons = reasons };
    }

    private static BetDecision EvaluateX_HomeFav(double kf1, double kf2, double? kf1X)
    {
        // Same conditions as 1X per ТЗ
        var reasons = new List<string>();
        bool passes = true;

        if (kf1 > 8)
        {
            reasons.Add($"FAIL: kf1={F(kf1)} > 8");
            passes = false;
        }
        else
            reasons.Add($"OK: kf1={F(kf1)} ≤ 8");

        if (!kf1X.HasValue)
        {
            reasons.Add("FAIL: kf1X is null (missing kfX)");
            passes = false;
        }
        else if (kf1X.Value < 1.5)
        {
            reasons.Add($"FAIL: kf1X={F(kf1X.Value)} < 1.5");
            passes = false;
        }
        else
            reasons.Add($"OK: kf1X={F(kf1X.Value)} ≥ 1.5");

        if (kf2 < 1.4)
        {
            reasons.Add($"FAIL: kf2={F(kf2)} < 1.4");
            passes = false;
        }
        else
            reasons.Add($"OK: kf2={F(kf2)} ≥ 1.4");

        return new BetDecision { BetType = "X", Passes = passes, Reasons = reasons };
    }

    // ── Away favourite (kf2 > kf1) ──────────────────────────

    private static BetDecision Evaluate2_AwayFav(double kf2, double kf1)
    {
        var reasons = new List<string>();
        bool passes = true;

        if (kf2 > 8)
        {
            reasons.Add($"FAIL: kf2={F(kf2)} > 8");
            passes = false;
        }
        else
            reasons.Add($"OK: kf2={F(kf2)} ≤ 8");

        if (kf1 < 1.4)
        {
            reasons.Add($"FAIL: kf1={F(kf1)} < 1.4");
            passes = false;
        }
        else
            reasons.Add($"OK: kf1={F(kf1)} ≥ 1.4");

        return new BetDecision { BetType = "2", Passes = passes, Reasons = reasons };
    }

    private static BetDecision Evaluate1_AwayFav(double kf1)
    {
        var reasons = new List<string>();
        bool passes = true;

        if (kf1 < 1.5)
        {
            reasons.Add($"FAIL: kf1={F(kf1)} < 1.5");
            passes = false;
        }
        else
            reasons.Add($"OK: kf1={F(kf1)} ≥ 1.5");

        return new BetDecision { BetType = "1", Passes = passes, Reasons = reasons };
    }

    private static string F(double value) => value.ToString("F2", CultureInfo.InvariantCulture);
}
