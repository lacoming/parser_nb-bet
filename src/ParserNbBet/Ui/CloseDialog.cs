namespace ParserNbBet.Ui;

/// <summary>
/// Modal dialog shown when user clicks X on the main window.
/// DialogResult.Yes  → Exit
/// DialogResult.No   → Minimize to tray
/// </summary>
public sealed class CloseDialog : Form
{
    public CloseDialog()
    {
        Text            = "parser_nb-bet";
        Size            = new Size(320, 140);
        FormBorderStyle = FormBorderStyle.FixedDialog;
        StartPosition   = FormStartPosition.CenterParent;
        MaximizeBox     = false;
        MinimizeBox     = false;
        ControlBox      = false;

        var label = new Label
        {
            Text      = "Выйти из приложения или свернуть в трей?",
            Left      = 12, Top    = 16,
            Width     = 290, Height = 40,
            TextAlign = ContentAlignment.MiddleCenter,
            Font      = new Font("Segoe UI", 9f),
        };

        var btnExit = new Button
        {
            Text         = "Выйти",
            DialogResult = DialogResult.Yes,
            Left         = 30,  Top = 70,
            Width        = 110, Height = 32,
        };

        var btnMinimize = new Button
        {
            Text         = "Свернуть",
            DialogResult = DialogResult.No,
            Left         = 170, Top = 70,
            Width        = 110, Height = 32,
        };

        AcceptButton = btnExit;
        CancelButton = btnMinimize;
        Controls.AddRange(new Control[] { label, btnExit, btnMinimize });
    }
}
