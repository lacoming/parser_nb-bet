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
///   - Tray right-click: "Open window", "Run now", "Pause/Resume", "Open logs", "Exit".
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
    private volatile bool _isPaused;

    public MainForm(CliArgs args, AppConfig config, CycleRunner runner)
    {
        _args = args;
        _config = config;
        _runner = runner;
        InitializeComponent();
        InitializeTray();
    }

    // ── UI controls ─────────────────────────────────────────────────────────

    private Label _lblTitle = null!;
    private Label _lblNextRun = null!;
    private Label _lblLastResult = null!;
    private TextBox _txtLog = null!;
    private Button _btnRunNow = null!;
    private Button _btnPause = null!;
    private Button _btnHide = null!;
    private Button _btnExit = null!;

    // ── Tray menu items (to update text) ────────────────────────────────────
    private ToolStripMenuItem _trayPause = null!;

    private void InitializeComponent()
    {
        Text = "parser_nb-bet";
        Size = new Size(600, 520);
        MinimumSize = new Size(500, 420);
        StartPosition = FormStartPosition.CenterScreen;
        MaximizeBox = false;
        Font = new Font("Segoe UI", 9f);

        // ── Status panel (top) ──────────────────────────────────────────────

        var statusPanel = new Panel
        {
            Dock = DockStyle.Top,
            Height = 80,
            Padding = new Padding(12, 8, 12, 4),
        };

        _lblTitle = new Label
        {
            Text = "parser_nb-bet",
            Font = new Font("Segoe UI", 12f, FontStyle.Bold),
            AutoSize = true,
            Left = 12,
            Top = 8,
        };

        _lblNextRun = new Label
        {
            Text = "Статус: инициализация…",
            AutoSize = true,
            Left = 12,
            Top = 34,
            ForeColor = Color.FromArgb(60, 60, 60),
        };

        _lblLastResult = new Label
        {
            Text = "",
            AutoSize = true,
            Left = 12,
            Top = 54,
            ForeColor = Color.FromArgb(80, 80, 80),
        };

        statusPanel.Controls.AddRange([_lblTitle, _lblNextRun, _lblLastResult]);

        // ── Log viewer (center) ─────────────────────────────────────────────

        _txtLog = new TextBox
        {
            Multiline = true,
            ReadOnly = true,
            ScrollBars = ScrollBars.Vertical,
            Dock = DockStyle.Fill,
            BackColor = Color.FromArgb(20, 20, 20),
            ForeColor = Color.FromArgb(200, 200, 200),
            Font = new Font("Consolas", 8.5f),
            WordWrap = false,
        };

        // ── Button panel (bottom) ───────────────────────────────────────────

        var buttonPanel = new FlowLayoutPanel
        {
            Dock = DockStyle.Bottom,
            Height = 44,
            Padding = new Padding(8, 6, 8, 6),
            FlowDirection = FlowDirection.LeftToRight,
        };

        _btnRunNow = new Button { Text = "Запустить", Width = 100, Height = 30 };
        _btnRunNow.Click += OnRunNowClick;

        _btnPause = new Button { Text = "Пауза", Width = 80, Height = 30 };
        _btnPause.Click += OnPauseClick;

        _btnHide = new Button { Text = "Скрыть в трей", Width = 110, Height = 30 };
        _btnHide.Click += (_, _) => HideToTray();

        _btnExit = new Button { Text = "Выход", Width = 80, Height = 30 };
        _btnExit.Click += (_, _) => ForceExit();

        buttonPanel.Controls.AddRange([_btnRunNow, _btnPause, _btnHide, _btnExit]);

        // ── Separator ───────────────────────────────────────────────────────

        var sep = new Panel
        {
            Dock = DockStyle.Top,
            Height = 1,
            BackColor = Color.FromArgb(200, 200, 200),
        };

        // ── Assemble ────────────────────────────────────────────────────────

        Controls.Add(_txtLog);       // Fill (center)
        Controls.Add(sep);           // Top separator under status
        Controls.Add(statusPanel);   // Top
        Controls.Add(buttonPanel);   // Bottom

        FormClosing += OnFormClosing;
        Load += OnFormLoad;
    }

    // ── Tray ────────────────────────────────────────────────────────────────

    private void InitializeTray()
    {
        var menu = new ContextMenuStrip();
        menu.Items.Add("Открыть окно", null, (_, _) => ShowWindow());
        menu.Items.Add("Запустить сейчас", null, (_, _) => OnRunNowClick(this, EventArgs.Empty));
        _trayPause = new ToolStripMenuItem("Пауза", null, (_, _) => OnPauseClick(this, EventArgs.Empty));
        menu.Items.Add(_trayPause);
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add("Открыть логи", null, (_, _) => OpenLogsFolder());
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add("Выход", null, (_, _) => ForceExit());

        _tray = new NotifyIcon
        {
            Text = "parser_nb-bet",
            Icon = LoadIcon(),
            ContextMenuStrip = menu,
            Visible = false,
        };
        _tray.DoubleClick += (_, _) => ShowWindow();
    }

    private static Icon LoadIcon()
    {
        const string path = @"assets\icon.ico";
        return File.Exists(path) ? new Icon(path) : SystemIcons.Application;
    }

    // ── Public: append log line (called from UiLogSink via any thread) ──────

    private const int MaxLogLines = 500;

    public void AppendLog(string line)
    {
        if (IsDisposed) return;

        if (InvokeRequired)
        {
            try { BeginInvoke(() => AppendLogInternal(line)); }
            catch (ObjectDisposedException) { }
            catch (InvalidOperationException) { }
        }
        else
        {
            AppendLogInternal(line);
        }
    }

    private void AppendLogInternal(string line)
    {
        if (_txtLog.IsDisposed) return;

        _txtLog.AppendText(line + Environment.NewLine);

        // Trim if too many lines
        if (_txtLog.Lines.Length > MaxLogLines)
        {
            var lines = _txtLog.Lines;
            var trimmed = lines.Skip(lines.Length - MaxLogLines + 100).ToArray();
            _txtLog.Lines = trimmed;
            _txtLog.SelectionStart = _txtLog.TextLength;
            _txtLog.ScrollToCaret();
        }
    }

    // ── Lifecycle ───────────────────────────────────────────────────────────

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
                UpdateNextRun($"Следующий запуск: {msk:dd.MM.yyyy HH:mm} MSK");
            };

            _scheduler.CycleStarted += () =>
            {
                SetRunning(true);
                UpdateNextRun("Цикл выполняется…");
            };

            _scheduler.CycleFinished += ok =>
            {
                SetRunning(false);
                ShowLastResult(ok);
            };

            _daemonTask = Task.Run(() => _scheduler.RunDaemonAsync(_cts.Token));
            Log.Information("UI daemon started (schedule enabled)");
        }
        else
        {
            UpdateNextRun("Планировщик отключён (schedule.enabled=false)");
            _btnPause.Enabled = false;
        }
    }

    // ── Actions ─────────────────────────────────────────────────────────────

    private volatile bool _isRunning;

    private void SetRunning(bool running)
    {
        _isRunning = running;
        SafeInvoke(() =>
        {
            _btnRunNow.Enabled = !running;
            _btnPause.Enabled = !running && _config.Schedule.Enabled;
        });
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
        UpdateNextRun("Ручной запуск цикла…");

        try
        {
            await Task.Run(() => _runner.RunAsync(CancellationToken.None));
            ShowLastResult(true);
        }
        catch (Exception ex)
        {
            Log.Error(ex, "Manual cycle failed");
            UpdateLastResult($"Ошибка: {ex.Message}");
        }
        finally
        {
            SetRunning(false);
        }
    }

    private void OnPauseClick(object? sender, EventArgs e)
    {
        if (_scheduler == null) return;

        if (!_isPaused)
        {
            _scheduler.Stop();
            _isPaused = true;
            _btnPause.Text = "Возобновить";
            _trayPause.Text = "Возобновить";
            UpdateNextRun("Планировщик приостановлен");
            Log.Information("Scheduler paused by user");
        }
        else
        {
            // Restart daemon
            _cts?.Dispose();
            _cts = new CancellationTokenSource();
            _scheduler = new MskScheduler(_config.Schedule, ct => _runner.RunAsync(ct));

            _scheduler.NextRunComputed += nextUtc =>
            {
                var msk = TimeZoneInfo.ConvertTimeFromUtc(nextUtc,
                    TimeZoneInfo.FindSystemTimeZoneById("Russian Standard Time"));
                UpdateNextRun($"Следующий запуск: {msk:dd.MM.yyyy HH:mm} MSK");
            };
            _scheduler.CycleStarted += () =>
            {
                SetRunning(true);
                UpdateNextRun("Цикл выполняется…");
            };
            _scheduler.CycleFinished += ok =>
            {
                SetRunning(false);
                ShowLastResult(ok);
            };

            _daemonTask = Task.Run(() => _scheduler.RunDaemonAsync(_cts.Token));
            _isPaused = false;
            _btnPause.Text = "Пауза";
            _trayPause.Text = "Пауза";
            Log.Information("Scheduler resumed by user");
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
        WindowState = FormWindowState.Normal;
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

    private static void OpenLogsFolder()
    {
        var logsDir = Path.GetFullPath("logs");
        if (Directory.Exists(logsDir))
        {
            System.Diagnostics.Process.Start("explorer.exe", logsDir);
        }
        else
        {
            MessageBox.Show($"Папка логов не найдена:\n{logsDir}", "parser_nb-bet",
                MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
    }

    // ── Status updates (thread-safe) ────────────────────────────────────────

    private void UpdateNextRun(string text)
    {
        SafeInvoke(() => _lblNextRun.Text = text);
    }

    private void UpdateLastResult(string text)
    {
        SafeInvoke(() => _lblLastResult.Text = text);
    }

    private void ShowLastResult(bool ok)
    {
        var result = _runner.LastResult;
        if (result == null) return;

        var msk = TimeZoneInfo.ConvertTimeFromUtc(result.CompletedUtc,
            TimeZoneInfo.FindSystemTimeZoneById("Russian Standard Time"));

        var status = ok ? "OK" : "ошибка";
        var text = $"Последний цикл: {msk:HH:mm:ss} ({status}) | " +
                   $"NB: {result.TotalMatches} → фильтр: {result.FilteredMatches} → " +
                   $"решение: {result.PassingMatches} | Куш: {result.KushMatched} | " +
                   $"Ставок: {result.BetsPlaced} | Очередь: {result.Pending}" +
                   (_config.Kush.DryRun ? " [dry-run]" : "");

        UpdateLastResult(text);
    }

    private void SafeInvoke(Action action)
    {
        if (IsDisposed) return;
        if (InvokeRequired)
        {
            try { Invoke(action); }
            catch (ObjectDisposedException) { }
            catch (InvalidOperationException) { }
        }
        else
        {
            action();
        }
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
