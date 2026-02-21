using ClosedXML.Excel;
using Serilog;

namespace ParserNbBet.Excel;

/// <summary>
/// Writes bet results to Excel (.xlsx) files using ClosedXML.
/// Creates one file per date in the configured output directory.
/// </summary>
public sealed class ExcelWriter
{
    private readonly string _outputDir;
    private readonly IColumnMapper _mapper;
    private readonly List<ExcelRow> _rows = [];

    public ExcelWriter(string outputDir, IColumnMapper? mapper = null)
    {
        _outputDir = outputDir;
        _mapper = mapper ?? new DefaultColumnMapper();
    }

    /// <summary>Number of rows added so far.</summary>
    public int RowCount => _rows.Count;

    /// <summary>Add a single row to the buffer.</summary>
    public void AddRow(ExcelRow row) => _rows.Add(row);

    /// <summary>Add multiple rows to the buffer.</summary>
    public void AddRows(IEnumerable<ExcelRow> rows) => _rows.AddRange(rows);

    /// <summary>
    /// Save buffered rows to an Excel file.
    /// File name: {yyyy-MM-dd}_results.xlsx (based on current date).
    /// If file already exists, appends rows after existing data.
    /// </summary>
    /// <returns>Full path to the saved file, or null if no rows to write.</returns>
    public string? Save(DateTime? dateOverride = null)
    {
        if (_rows.Count == 0)
        {
            Log.Debug("ExcelWriter: no rows to write, skipping");
            return null;
        }

        Directory.CreateDirectory(_outputDir);

        var date = dateOverride ?? DateTime.Now;
        var fileName = $"{date:yyyy-MM-dd}_results.xlsx";
        var filePath = Path.Combine(_outputDir, fileName);

        var columns = _mapper.GetColumns();

        XLWorkbook workbook;
        IXLWorksheet ws;
        int startRow;

        if (File.Exists(filePath))
        {
            // Append to existing file
            workbook = new XLWorkbook(filePath);
            ws = workbook.Worksheets.First();
            startRow = ws.LastRowUsed()?.RowNumber() + 1 ?? 2;
            Log.Information("ExcelWriter: appending {Count} rows to existing file {Path} at row {Row}",
                _rows.Count, filePath, startRow);
        }
        else
        {
            // Create new file with headers
            workbook = new XLWorkbook();
            ws = workbook.Worksheets.Add("Результаты");
            WriteHeaders(ws, columns);
            startRow = 2;
            Log.Information("ExcelWriter: creating new file {Path} with {Count} rows", filePath, _rows.Count);
        }

        WriteRows(ws, columns, startRow);
        ApplyFormatting(ws, columns, startRow);

        workbook.SaveAs(filePath);
        workbook.Dispose();

        Log.Information("ExcelWriter: saved {Path} ({RowCount} rows total)", filePath, startRow - 2 + _rows.Count);
        return filePath;
    }

    private static void WriteHeaders(IXLWorksheet ws, IReadOnlyList<ColumnDef> columns)
    {
        for (int i = 0; i < columns.Count; i++)
        {
            var col = columns[i];
            var cell = ws.Cell(1, i + 1);
            cell.Value = col.Header;
            cell.Style.Font.Bold = true;
            cell.Style.Font.FontName = "Times New Roman";
            cell.Style.Font.FontSize = 11;
            cell.Style.Alignment.Horizontal = XLAlignmentHorizontalValues.Center;
            cell.Style.Alignment.Vertical = XLAlignmentVerticalValues.Center;
            cell.Style.Alignment.WrapText = true;
            cell.Style.Border.OutsideBorder = XLBorderStyleValues.Thin;
            ws.Column(i + 1).Width = col.Width;
        }
    }

    private void WriteRows(IXLWorksheet ws, IReadOnlyList<ColumnDef> columns, int startRow)
    {
        for (int r = 0; r < _rows.Count; r++)
        {
            var row = _rows[r];
            for (int c = 0; c < columns.Count; c++)
            {
                var col = columns[c];
                var value = col.ValueExtractor(row);
                var cell = ws.Cell(startRow + r, c + 1);

                if (value is null)
                {
                    cell.Value = Blank.Value;
                }
                else if (value is double d)
                {
                    cell.Value = d;
                }
                else if (value is int n)
                {
                    cell.Value = n;
                }
                else
                {
                    cell.Value = value.ToString() ?? "";
                }
            }
        }
    }

    private static void ApplyFormatting(IXLWorksheet ws, IReadOnlyList<ColumnDef> columns, int startRow)
    {
        if (startRow <= 1) return;

        // Apply number formats to data cells
        var lastRow = ws.LastRowUsed()?.RowNumber() ?? startRow;
        for (int c = 0; c < columns.Count; c++)
        {
            var col = columns[c];
            if (col.NumberFormat == null) continue;

            var range = ws.Range(2, c + 1, lastRow, c + 1);
            range.Style.NumberFormat.Format = col.NumberFormat;
        }

        // Apply table style if this is a fresh file (startRow == 2 means we just wrote headers)
        if (startRow == 2 && lastRow >= 2)
        {
            var tableRange = ws.Range(1, 1, lastRow, columns.Count);
            var table = tableRange.CreateTable("Results");
            table.Theme = XLTableTheme.TableStyleMedium3;
        }
    }

    /// <summary>
    /// Helper: build an ExcelRow from match/decision/bet data.
    /// </summary>
    public static ExcelRow BuildRow(
        Nb.Match match,
        Decision.BetDecision? decision = null,
        Kush.BetResult? betResult = null,
        Kush.KushEvent? kushEvent = null,
        string status = "")
    {
        // Convert UTC to Moscow time for display
        var mskZone = TimeZoneInfo.FindSystemTimeZoneById("Russian Standard Time");
        var mskTime = TimeZoneInfo.ConvertTimeFromUtc(match.StartTimeUtc, mskZone);

        return new ExcelRow
        {
            Date = mskTime.Date,
            Time = mskTime.ToString("HH:mm"),
            Sport = match.Sport,
            League = match.League,
            TeamHome = match.TeamHome,
            TeamAway = match.TeamAway,

            Odds1Start = match.Odds1Start,
            Odds1End = match.Odds1End,
            OddsXStart = match.OddsXStart,
            OddsXEnd = match.OddsXEnd,
            Odds2Start = match.Odds2Start,
            Odds2End = match.Odds2End,

            BetType = decision?.BetType ?? "",
            Passes = decision?.Passes ?? false,
            Reasons = decision != null ? string.Join("; ", decision.Reasons) : "",

            KushMatched = kushEvent != null,
            OddsKush = betResult?.OddsKush,
            Ratio = betResult?.Ratio,

            BetStatus = status != "" ? status
                : betResult?.DryRun == true ? "dry-run"
                : betResult?.Success == true ? "placed"
                : betResult != null ? "failed"
                : "",
            Stake = betResult?.Stake,

            NbUrl = $"https://nb-bet.com/Results/{match.NbSlug}",
            KushUrl = kushEvent?.Url ?? "",
        };
    }
}
