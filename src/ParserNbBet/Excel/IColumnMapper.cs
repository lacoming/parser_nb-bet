namespace ParserNbBet.Excel;

/// <summary>
/// Defines column layout for Excel output.
/// Implement this interface to customize which columns appear and in what order.
/// </summary>
public interface IColumnMapper
{
    /// <summary>
    /// Returns ordered list of column definitions.
    /// </summary>
    IReadOnlyList<ColumnDef> GetColumns();
}

/// <summary>
/// Definition of a single Excel column.
/// </summary>
public sealed class ColumnDef
{
    /// <summary>Column header text.</summary>
    public string Header { get; }

    /// <summary>Column width in Excel units.</summary>
    public double Width { get; }

    /// <summary>Function to extract value from an ExcelRow.</summary>
    public Func<ExcelRow, object?> ValueExtractor { get; }

    /// <summary>Optional number format (e.g. "0.00" for odds, "0.00%" for percentages).</summary>
    public string? NumberFormat { get; }

    public ColumnDef(string header, double width, Func<ExcelRow, object?> valueExtractor, string? numberFormat = null)
    {
        Header = header;
        Width = width;
        ValueExtractor = valueExtractor;
        NumberFormat = numberFormat;
    }
}
