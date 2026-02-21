using ParserNbBet.Kush;
using Xunit;

namespace ParserNbBet.Tests;

public class TeamNormalizerTests
{
    [Fact]
    public void Normalize_Lowercase()
    {
        Assert.Equal("manchester united", TeamNormalizer.Normalize("Manchester United"));
    }

    [Fact]
    public void Normalize_RemovesPunctuation()
    {
        Assert.Equal("f c barcelona", TeamNormalizer.Normalize("F.C. Barcelona!"));
    }

    [Fact]
    public void Normalize_CollapsesWhitespace()
    {
        Assert.Equal("real madrid", TeamNormalizer.Normalize("  Real   Madrid  "));
    }

    [Fact]
    public void Normalize_TransliteratesCyrillic()
    {
        // Спартак → spartak
        Assert.Equal("spartak", TeamNormalizer.Normalize("Спартак"));
    }

    [Fact]
    public void Normalize_CyrillicFullTeamName()
    {
        // ЦСКА Москва → Ц=ts, С=s, К=k, А=a → tsska moskva
        var result = TeamNormalizer.Normalize("ЦСКА Москва");
        Assert.Equal("tsska moskva", result);
    }

    [Fact]
    public void Normalize_RemovesDiacritics()
    {
        Assert.Equal("atletico madrid", TeamNormalizer.Normalize("Atlético Madrid"));
    }

    [Fact]
    public void Normalize_EmptyString()
    {
        Assert.Equal("", TeamNormalizer.Normalize(""));
    }

    [Fact]
    public void Normalize_NullOrWhitespace()
    {
        Assert.Equal("", TeamNormalizer.Normalize("   "));
    }

    [Fact]
    public void Normalize_MixedCyrillicAndLatin()
    {
        // ФК Arsenal → fk arsenal
        var result = TeamNormalizer.Normalize("ФК Arsenal");
        Assert.Equal("fk arsenal", result);
    }

    [Fact]
    public void Normalize_SpecialCharsInTeamName()
    {
        // Dots removed → "S" and "C" become separate tokens
        Assert.Equal("al ahli s c", TeamNormalizer.Normalize("Al-Ahli S.C."));
    }
}
