namespace ParserNbBet.Ui;

/// <summary>
/// Main status window + system tray icon.
/// UX rules:
///   - On start: window is visible.
///   - "Hide" button / menu → hide to tray.
///   - X (FormClosing) → dialog "Exit or Minimize?".
///   - Tray right-click: "Open window", "Exit".
/// </summary>
public sealed class MainForm : Form
{
    private readonly CliArgs _args;
    private NotifyIcon _tray = null!;
    private bool _forceClose;

    public MainForm(CliArgs args)
    {
        _args = args;
        InitializeComponent();
        InitializeTray();
    }

    // ── UI layout ────────────────────────────────────────────────────────────

    private Label _lblStatus = null!;
    private Button _btnHide  = null!;
    private Button _btnExit  = null!;

    private void InitializeComponent()
    {
        Text            = "parser_nb-bet";
        Size            = new Size(420, 260);
        MinimumSize     = new Size(420, 260);
        StartPosition   = FormStartPosition.CenterScreen;
        FormBorderStyle = FormBorderStyle.FixedSingle;
        MaximizeBox     = false;

        _lblStatus = new Label
        {
            Text      = "Статус: ожидание запуска…",
            Dock      = DockStyle.Top,
            Height    = 140,
            Padding   = new Padding(12),
            Font      = new Font("Segoe UI", 9f),
            TextAlign = ContentAlignment.TopLeft,
        };

        _btnHide = new Button
        {
            Text   = "Скрыть в трей",
            Width  = 130,
            Height = 32,
            Left   = 12,
            Top    = 160,
            Anchor = AnchorStyles.Bottom | AnchorStyles.Left,
        };
        _btnHide.Click += (_, _) => HideToTray();

        _btnExit = new Button
        {
            Text   = "Выход",
            Width  = 90,
            Height = 32,
            Left   = 152,
            Top    = 160,
            Anchor = AnchorStyles.Bottom | AnchorStyles.Left,
        };
        _btnExit.Click += (_, _) => ForceExit();

        Controls.AddRange(new Control[] { _lblStatus, _btnHide, _btnExit });

        FormClosing += OnFormClosing;
    }

    // ── Tray ─────────────────────────────────────────────────────────────────

    private void InitializeTray()
    {
        var menu = new ContextMenuStrip();
        menu.Items.Add("Открыть окно", null, (_, _) => ShowWindow());
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add("Выход",        null, (_, _) => ForceExit());

        _tray = new NotifyIcon
        {
            Text             = "parser_nb-bet",
            Icon             = LoadIcon(),
            ContextMenuStrip = menu,
            Visible          = false,
        };
        _tray.DoubleClick += (_, _) => ShowWindow();
    }

    private static Icon LoadIcon()
    {
        const string path = @"assets\icon.ico";
        return File.Exists(path) ? new Icon(path) : SystemIcons.Application;
    }

    // ── Actions ───────────────────────────────────────────────────────────────

    private void HideToTray()
    {
        Hide();
        _tray.Visible = true;
        _tray.ShowBalloonTip(2000, "parser_nb-bet", "Приложение свёрнуто в трей.", ToolTipIcon.Info);
    }

    private void ShowWindow()
    {
        Show();
        WindowState   = FormWindowState.Normal;
        _tray.Visible = false;
        Activate();
    }

    private void ForceExit()
    {
        _forceClose = true;
        _tray.Visible = false;
        _tray.Dispose();
        Application.Exit();
    }

    private void OnFormClosing(object? sender, FormClosingEventArgs e)
    {
        if (_forceClose) return;

        // Cancel the close and show dialog instead
        e.Cancel = true;

        using var dlg = new CloseDialog();
        var result = dlg.ShowDialog(this);
        if (result == DialogResult.Yes)
            ForceExit();       // "Выйти"
        else
            HideToTray();      // "Свернуть"
    }

    // ── Public status update (called from scheduler thread) ───────────────────

    public void UpdateStatus(string text)
    {
        if (InvokeRequired)
            Invoke(() => _lblStatus.Text = text);
        else
            _lblStatus.Text = text;
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing) { _tray?.Dispose(); }
        base.Dispose(disposing);
    }
}
