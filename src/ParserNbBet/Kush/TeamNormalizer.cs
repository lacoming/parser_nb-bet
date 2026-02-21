using System.Globalization;
using System.Text;
using System.Text.RegularExpressions;

namespace ParserNbBet.Kush;

/// <summary>
/// Normalizes team/league names for fuzzy comparison:
/// lowercase, remove punctuation, normalize whitespace, optional transliteration.
/// </summary>
public static partial class TeamNormalizer
{
    // Cyrillic → Latin transliteration table
    private static readonly Dictionary<char, string> CyrToLat = new()
    {
        ['а'] = "a",  ['б'] = "b",  ['в'] = "v",  ['г'] = "g",  ['д'] = "d",
        ['е'] = "e",  ['ё'] = "yo", ['ж'] = "zh", ['з'] = "z",  ['и'] = "i",
        ['й'] = "y",  ['к'] = "k",  ['л'] = "l",  ['м'] = "m",  ['н'] = "n",
        ['о'] = "o",  ['п'] = "p",  ['р'] = "r",  ['с'] = "s",  ['т'] = "t",
        ['у'] = "u",  ['ф'] = "f",  ['х'] = "kh", ['ц'] = "ts", ['ч'] = "ch",
        ['ш'] = "sh", ['щ'] = "shch", ['ъ'] = "",  ['ы'] = "y",  ['ь'] = "",
        ['э'] = "e",  ['ю'] = "yu", ['я'] = "ya",
    };

    /// <summary>
    /// Normalize a team/league name for comparison.
    /// Steps: trim → lowercase → transliterate Cyrillic → remove diacritics → remove punctuation → collapse whitespace.
    /// </summary>
    public static string Normalize(string name)
    {
        if (string.IsNullOrWhiteSpace(name))
            return "";

        var s = name.Trim().ToLowerInvariant();

        // Transliterate Cyrillic characters
        var sb = new StringBuilder(s.Length);
        foreach (var ch in s)
        {
            if (CyrToLat.TryGetValue(ch, out var lat))
                sb.Append(lat);
            else
                sb.Append(ch);
        }
        s = sb.ToString();

        // Remove diacritics (e.g. é → e)
        s = RemoveDiacritics(s);

        // Remove punctuation: keep only letters, digits, spaces
        s = PunctuationRegex().Replace(s, " ");

        // Collapse whitespace
        s = WhitespaceRegex().Replace(s, " ").Trim();

        return s;
    }

    private static string RemoveDiacritics(string text)
    {
        var normalized = text.Normalize(NormalizationForm.FormD);
        var sb = new StringBuilder(normalized.Length);
        foreach (var ch in normalized)
        {
            if (CharUnicodeInfo.GetUnicodeCategory(ch) != UnicodeCategory.NonSpacingMark)
                sb.Append(ch);
        }
        return sb.ToString().Normalize(NormalizationForm.FormC);
    }

    [GeneratedRegex(@"[^\p{L}\p{N}\s]")]
    private static partial Regex PunctuationRegex();

    [GeneratedRegex(@"\s+")]
    private static partial Regex WhitespaceRegex();
}
