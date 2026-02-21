using ParserNbBet.Config;
using ParserNbBet.Scheduler;
using Serilog;

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
    private readonly AppConfig _config;
    private readonly CycleRunner _runner;
    private NotifyIcon _tray = null!;
    private bool _forceClose;

    private MskScheduler? _scheduler;
    private CancellationTokenSource? _cts;
    private Task? _daemonTask;

    public MainForm(CliArgs args, AppConfig config, CycleRunner runner)
    {
        _args = args;
        _config = config;
        _runner = runner;
        InitializeComponent();
        InitializeTray();
    }

    // ── UI layout ────────────────────────────────────────────────────────────

    private Label _lblStatus = null!;
    private Button _btnHide  = null!;
    private Button _btnExit  = null!;
    private Button _btnRunNow = null!;

    private void InitializeComponent()
    {
        Text            = "parser_nb-bet";
        Size            = new Size(420, 300);
        MinimumSize     = new Size(420, 300);
        StartPosition   = FormStartPosition.CenterScreen;
        FormBorderStyle = FormBorderStyle.FixedSingle;
        MaximizeBox     = false;

        _lblStatus = new Label
        {
            Text      = "Статус: инициализация…",
            Dock      = DockStyle.Top,
            Height    = 180,
            Padding   = new Padding(12),
            Font      = new Font("Segoe UI", 9f),
            TextAlign = ContentAlignment.TopLeft,
        };

        _btnRunNow = new Button
        {
            Text   = "Запустить сейчас",
            Width  = 150,
            Height = 32,
            Left   = 12,
            Top    = 200,
            Anchor = AnchorStyles.Bottom | AnchorStyles.Left,
        };
        _btnRunNow.Click += OnRunNowClick;

        _btnHide = new Button
        {
            Text   = "Скрыть в трей",
            Width  = 130,
            Height = 32,
            Left   = 170,
            Top    = 200,
            Anchor = AnchorStyles.Bottom | AnchorStyles.Left,
        };
        _btnHide.Click += (_, _) => HideToTray();

        _btnExit = new Button
        {
            Text   = "Выход",
            Width  = 90,
            Height = 32,
            Left   = 308,
            Top    = 200,
            Anchor = AnchorStyles.Bottom | AnchorStyles.Left,
        };
        _btnExit.Click += (_, _) => ForceExit();

        Controls.AddRange(new Control[] { _lblStatus, _btnRunNow, _btnHide, _btnExit });

        FormClosing += OnFormClosing;
        Load += OnFormLoad;
    }

    // ── Tray ─────────────────────────────────────────────────────────────────

    private void InitializeTray()
    {
        var menu = new ContextMenuStrip();
        menu.Items.Add("Открыть окно", null, (_, _) => ShowWindow());
        menu.Items.Add("Запустить сейчас", null, (_, _) => OnRunNowClick(this, EventArgs.Empty));
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

    // ── Lifecycle ─────────────────────────────────────────────────────────────

    private void OnFormLoad(object? sender, EventArgs e)
    {
        StartDaemon();
    }

    private void StartDaemon()
    {
        if (_config.Schedule.Enabled)
        {
            _cts = new CancellationTokenSource();
            _scheduler = new MskScheduler(_config.Schedule, ct => _runner.RunAsync(ct));

            _scheduler.NextRunComputed += nextUtc =>
            {
                var msk = TimeZoneInfo.ConvertTimeFromUtc(nextUtc,
                    TimeZoneInfo.FindSystemTimeZoneById("Russian Standard Time"));
                UpdateStatus($"Следующий запуск: {msk:yyyy-MM-dd HH:mm:ss} MSK");
            };

            _scheduler.CycleStarted += () =>
            {
                SetRunning(true);
                UpdateStatus("Цикл выполняется...");
            };

            _scheduler.CycleFinished += ok =>
            {
                SetRunning(false);
                var result = _runner.LastResult;
                if (result != null)
                {
                    var msk = TimeZoneInfo.ConvertTimeFromUtc(result.CompletedUtc,
                        TimeZoneInfo.FindSystemTimeZoneById("Russian Standard Time"));
                    UpdateStatus(
                        $"Последний цикл: {msk:HH:mm:ss} MSK ({(ok ? "OK" : "ошибка")})\n" +
                        $"  Матчей NB: {result.TotalMatches}\n" +
                        $"  После фильтра: {result.FilteredMatches}\n" +
                        $"  Прошли решение: {result.PassingMatches}\n" +
                        $"  Совпало на Куше: {result.KushMatched}\n" +
                        $"  Ставок: {result.BetsPlaced}\n" +
                        $"  В очереди: {result.Pending}\n" +
                        $"  dry-run: {_config.Kush.DryRun}");
                }
            };

            _daemonTask = Task.Run(() => _scheduler.RunDaemonAsync(_cts.Token));
            Log.Information("UI daemon started (schedule enabled)");
        }
        else
        {
            UpdateStatus("Планировщик отключён (schedule.enabled=false).\nИспользуйте кнопку 'Запустить сейчас'.");
        }
    }

    // ── Actions ───────────────────────────────────────────────────────────────

    private volatile bool _isRunning;

    private void SetRunning(bool running)
    {
        _isRunning = running;
        if (InvokeRequired)
            Invoke(() => _btnRunNow.Enabled = !running);
        else
            _btnRunNow.Enabled = !running;
    }

    private async void OnRunNowClick(object? sender, EventArgs e)
    {
        if (_isRunning)
        {
            MessageBox.Show(this, "Цикл уже выполняется.", "parser_nb-bet",
                MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }

        SetRunning(true);
        UpdateStatus("Ручной запуск цикла...");

        try
        {
            await Task.Run(() => _runner.RunAsync(CancellationToken.None));

            var result = _runner.LastResult;
            if (result != null)
            {
                var msk = TimeZoneInfo.ConvertTimeFromUtc(result.CompletedUtc,
                    TimeZoneInfo.FindSystemTimeZoneById("Russian Standard Time"));
                UpdateStatus(
                    $"Ручной цикл завершён: {msk:HH:mm:ss} MSK\n" +
                    $"  Матчей NB: {result.TotalMatches}\n" +
                    $"  Ставок: {result.BetsPlaced}\n" +
                    $"  В очереди: {result.Pending}");
            }
        }
        catch (Exception ex)
        {
            Log.Error(ex, "Manual cycle failed");
            UpdateStatus($"Ошибка ручного запуска: {ex.Message}");
        }
        finally
        {
            SetRunning(false);
        }
    }

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

        // Stop scheduler
        _scheduler?.Stop();
        _cts?.Cancel();

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
        if (disposing)
        {
            _scheduler?.Dispose();
            _cts?.Dispose();
            _tray?.Dispose();
        }
        base.Dispose(disposing);
    }
}
