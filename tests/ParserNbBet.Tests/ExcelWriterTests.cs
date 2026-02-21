using ClosedXML.Excel;
using ClosedXML.Graphics;
using ParserNbBet.Excel;
using ParserNbBet.Nb;
using ParserNbBet.Decision;
using ParserNbBet.Kush;
using Xunit;

namespace ParserNbBet.Tests;

public class ExcelWriterTests : IDisposable
{
    private readonly string _tempDir;

    static ExcelWriterTests()
    {
        // Initialize ClosedXML graphic engine with a single font file
        // to avoid scanning C:\Windows\Fonts subdirectories (permission issues).
        var arialPath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Fonts), "arial.ttf");
        if (File.Exists(arialPath))
        {
            using var fs = File.OpenRead(arialPath);
            LoadOptions.DefaultGraphicEngine = DefaultGraphicEngine.CreateOnlyWithFonts(fs);
        }
    }

    public ExcelWriterTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), $"ExcelWriterTests_{Guid.NewGuid():N}");
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        try { Directory.Delete(_tempDir, true); } catch { }
    }

    private static ExcelRow MakeRow(string team1 = "Team A", string team2 = "Team B",
        string league = "EPL", string betType = "1X", bool passes = true)
    {
        return new ExcelRow
        {
            Date = new DateTime(2026, 2, 21),
            Time = "15:00",
            Sport = "soccer",
            League = league,
            TeamHome = team1,
            TeamAway = team2,
            Odds1Start = 2.10,
            Odds1End = 1.95,
            OddsXStart = 3.50,
            OddsXEnd = 3.40,
            Odds2Start = 3.00,
            Odds2End = 3.20,
            BetType = betType,
            Passes = passes,
            Reasons = "kf1<=8; kf1X>=1.5",
            KushMatched = true,
            OddsKush = 2.05,
            Ratio = 1.12,
            BetStatus = "placed",
            Stake = 100,
            NbUrl = "https://nb-bet.com/Results/test-slug",
            KushUrl = "https://kushvsporte.ru/event/123",
        };
    }

    [Fact]
    public void Save_CreatesFile_WithHeadersAndRows()
    {
        var writer = new ExcelWriter(_tempDir);
        writer.AddRow(MakeRow());
        writer.AddRow(MakeRow("Arsenal", "Chelsea"));

        var path = writer.Save(new DateTime(2026, 2, 21));

        Assert.NotNull(path);
        Assert.True(File.Exists(path));
        Assert.Contains("2026-02-21_results.xlsx", path);

        using var wb = new XLWorkbook(path);
        var ws = wb.Worksheets.First();
        Assert.Equal("Результаты", ws.Name);

        // Header row
        Assert.Equal("Дата", ws.Cell(1, 1).GetString());
        Assert.Equal("Команда 1", ws.Cell(1, 5).GetString());

        // Data rows
        Assert.Equal("21.02.2026", ws.Cell(2, 1).GetString());
        Assert.Equal("Team A", ws.Cell(2, 5).GetString());
        Assert.Equal("Arsenal", ws.Cell(3, 5).GetString());
    }

    [Fact]
    public void Save_NoRows_ReturnsNull()
    {
        var writer = new ExcelWriter(_tempDir);
        var path = writer.Save();
        Assert.Null(path);
    }

    [Fact]
    public void Save_CreatesOutputDirectory()
    {
        var subDir = Path.Combine(_tempDir, "sub", "output");
        var writer = new ExcelWriter(subDir);
        writer.AddRow(MakeRow());

        var path = writer.Save(new DateTime(2026, 2, 21));

        Assert.NotNull(path);
        Assert.True(Directory.Exists(subDir));
    }

    [Fact]
    public void Save_AppendsToExistingFile()
    {
        var writer1 = new ExcelWriter(_tempDir);
        writer1.AddRow(MakeRow("Team A", "Team B"));
        var path1 = writer1.Save(new DateTime(2026, 2, 21));

        var writer2 = new ExcelWriter(_tempDir);
        writer2.AddRow(MakeRow("Team C", "Team D"));
        var path2 = writer2.Save(new DateTime(2026, 2, 21));

        Assert.Equal(path1, path2);

        using var wb = new XLWorkbook(path2!);
        var ws = wb.Worksheets.First();
        // Row 1 = header, Row 2 = Team A, Row 3 = Team C
        Assert.Equal("Team A", ws.Cell(2, 5).GetString());
        Assert.Equal("Team C", ws.Cell(3, 5).GetString());
    }

    [Fact]
    public void RowCount_TracksAdded()
    {
        var writer = new ExcelWriter(_tempDir);
        Assert.Equal(0, writer.RowCount);

        writer.AddRow(MakeRow());
        Assert.Equal(1, writer.RowCount);

        writer.AddRows([MakeRow(), MakeRow()]);
        Assert.Equal(3, writer.RowCount);
    }

    [Fact]
    public void DefaultColumnMapper_Returns24Columns()
    {
        var mapper = new DefaultColumnMapper();
        var cols = mapper.GetColumns();
        Assert.Equal(24, cols.Count);
        Assert.Equal("Дата", cols[0].Header);
        Assert.Equal("Куш ссылка", cols[^1].Header);
    }

    [Fact]
    public void OddsMovement_CalculatedCorrectly()
    {
        var row = new ExcelRow
        {
            Odds1Start = 2.00,
            Odds1End = 1.80,
            Odds2Start = 3.00,
            Odds2End = 3.30,
        };

        // (2.00 - 1.80) / 2.00 = 0.10
        Assert.NotNull(row.OddsMovement1);
        Assert.Equal(0.10, row.OddsMovement1!.Value, 4);

        // (3.00 - 3.30) / 3.00 = -0.10
        Assert.NotNull(row.OddsMovement2);
        Assert.Equal(-0.10, row.OddsMovement2!.Value, 4);
    }

    [Fact]
    public void OddsMovement_NullWhenMissing()
    {
        var row = new ExcelRow { Odds1Start = 2.00, Odds1End = null };
        Assert.Null(row.OddsMovement1);
    }

    [Fact]
    public void OddsMovement_NullWhenStartIsZero()
    {
        var row = new ExcelRow { Odds1Start = 0, Odds1End = 1.5 };
        Assert.Null(row.OddsMovement1);
    }

    [Fact]
    public void BuildRow_CreatesFromMatchAndDecision()
    {
        var match = new Match("EPL", "Arsenal", "Chelsea",
            new DateTime(2026, 2, 21, 12, 0, 0, DateTimeKind.Utc), "test-slug", "soccer")
        {
            Odds1Start = 2.10, Odds1End = 1.95,
            OddsXStart = 3.50, OddsXEnd = 3.40,
            Odds2Start = 3.00, Odds2End = 3.20,
        };

        var decision = new BetDecision
        {
            BetType = "1X", Passes = true,
            Reasons = ["kf1<=8", "kf1X>=1.5"]
        };

        var row = ExcelWriter.BuildRow(match, decision, status: "pending");

        Assert.Equal("EPL", row.League);
        Assert.Equal("Arsenal", row.TeamHome);
        Assert.Equal("Chelsea", row.TeamAway);
        Assert.Equal("soccer", row.Sport);
        Assert.Equal("1X", row.BetType);
        Assert.True(row.Passes);
        Assert.Contains("kf1<=8", row.Reasons);
        Assert.Equal("pending", row.BetStatus);
        Assert.Equal(1.95, row.Odds1End);
    }

    [Fact]
    public void BuildRow_WithBetResult()
    {
        var match = new Match("EPL", "Arsenal", "Chelsea",
            new DateTime(2026, 2, 21, 12, 0, 0, DateTimeKind.Utc), "test-slug", "soccer");

        var betResult = new BetResult(true, false, "1X", 1.95, 2.05, 1.12, 100, "kush-123", "placed ok");

        var row = ExcelWriter.BuildRow(match, betResult: betResult);

        Assert.Equal(2.05, row.OddsKush);
        Assert.Equal(1.12, row.Ratio);
        Assert.Equal("placed", row.BetStatus);
        Assert.Equal(100, row.Stake);
    }

    [Fact]
    public void BuildRow_DryRunStatus()
    {
        var match = new Match("EPL", "Arsenal", "Chelsea",
            new DateTime(2026, 2, 21, 12, 0, 0, DateTimeKind.Utc), "test-slug", "soccer");

        var betResult = new BetResult(false, true, "1X", 1.95, 2.05, 1.12, 100, "kush-123", "dry run");

        var row = ExcelWriter.BuildRow(match, betResult: betResult);

        Assert.Equal("dry-run", row.BetStatus);
    }

    [Fact]
    public void Save_NumericOddsWrittenAsNumbers()
    {
        var writer = new ExcelWriter(_tempDir);
        writer.AddRow(MakeRow());

        var path = writer.Save(new DateTime(2026, 2, 21));

        using var wb = new XLWorkbook(path!);
        var ws = wb.Worksheets.First();

        // Column 7 = КФ1 нач (Odds1Start = 2.10)
        var cell = ws.Cell(2, 7);
        Assert.Equal(2.10, cell.GetDouble(), 2);
    }
}
