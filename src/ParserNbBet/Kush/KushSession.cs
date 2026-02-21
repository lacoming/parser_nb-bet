using System.Net;
using ParserNbBet.Config;
using Polly;
using Polly.Retry;
using Serilog;

namespace ParserNbBet.Kush;

/// <summary>
/// Manages HTTP session with kushvsporte.ru: CSRF tokens, cookies, retry.
/// Shared between KushClient (event search) and KushBetPlacer (step 09).
/// </summary>
public sealed class KushSession : IDisposable
{
    private static readonly ILogger Logger = Log.ForContext<KushSession>();

    private readonly HttpClient _http;
    private readonly HttpClientHandler _handler;
    private readonly KushConfig _config;
    private readonly ResiliencePipeline<HttpResponseMessage> _retryPipeline;

    private string? _csrfToken;
    private bool _isLoggedIn;

    public string BaseUrl => _config.BaseUrl.TrimEnd('/');
    public bool IsLoggedIn => _isLoggedIn;

    public KushSession(KushConfig config, ProxyConfig? proxyConfig = null)
    {
        _config = config;

        _handler = new HttpClientHandler
        {
            UseCookies = true,
            CookieContainer = new CookieContainer(),
            AllowAutoRedirect = true,
        };

        if (proxyConfig is { Enabled: true })
        {
            var proxyUrl = LoadFirstProxy(proxyConfig.File);
            if (proxyUrl != null)
            {
                _handler.Proxy = new WebProxy(proxyUrl);
                _handler.UseProxy = true;
                Logger.Information("Kush: using proxy {Proxy}", proxyUrl);
            }
        }

        _http = new HttpClient(_handler)
        {
            Timeout = TimeSpan.FromSeconds(30)
        };

        // Base headers for all requests (from legacy)
        _http.DefaultRequestHeaders.Add("User-Agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0");
        _http.DefaultRequestHeaders.Add("Accept-Language", "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3");
        _http.DefaultRequestHeaders.Add("Connection", "keep-alive");
        _http.DefaultRequestHeaders.Add("Sec-GPC", "1");

        _retryPipeline = new ResiliencePipelineBuilder<HttpResponseMessage>()
            .AddRetry(new RetryStrategyOptions<HttpResponseMessage>
            {
                MaxRetryAttempts = 3,
                Delay = TimeSpan.FromSeconds(2),
                ShouldHandle = new PredicateBuilder<HttpResponseMessage>()
                    .Handle<HttpRequestException>()
                    .Handle<TaskCanceledException>()
                    .HandleResult(r => r.StatusCode >= HttpStatusCode.InternalServerError),
                OnRetry = args =>
                {
                    Logger.Warning("Kush request retry {Attempt}/3", args.AttemptNumber + 1);
                    return ValueTask.CompletedTask;
                }
            })
            .Build();
    }

    /// <summary>
    /// Initialize session: load main page, extract CSRF token + cookies.
    /// Must be called before any other operation.
    /// </summary>
    public async Task InitializeAsync(string sport = "football", int day = 0, CancellationToken ct = default)
    {
        var url = $"{BaseUrl}/centerbet/{sport}?day={day}&_pjax=#center-bet";
        Logger.Debug("Kush: initializing session from {Url}", url);

        var request = new HttpRequestMessage(HttpMethod.Get, url);
        request.Headers.Add("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8");
        request.Headers.Add("Sec-Fetch-Dest", "document");
        request.Headers.Add("Sec-Fetch-Mode", "navigate");
        request.Headers.Add("Sec-Fetch-Site", "none");
        request.Headers.Add("Sec-Fetch-User", "?1");
        request.Headers.Add("Upgrade-Insecure-Requests", "1");

        var response = await _retryPipeline.ExecuteAsync(
            async token => await _http.SendAsync(request, token), ct);
        response.EnsureSuccessStatusCode();

        var html = await response.Content.ReadAsStringAsync(ct);

        // Extract CSRF token from <meta name="csrf-token" content="..."/>
        var doc = new HtmlAgilityPack.HtmlDocument();
        doc.LoadHtml(html);
        var metaCsrf = doc.DocumentNode.SelectSingleNode("//meta[@name='csrf-token']");
        _csrfToken = metaCsrf?.GetAttributeValue("content", null);

        if (string.IsNullOrEmpty(_csrfToken))
            Logger.Warning("Kush: could not extract CSRF token from page");
        else
            Logger.Debug("Kush: CSRF token acquired ({Length} chars)", _csrfToken.Length);
    }

    /// <summary>
    /// Login to kushvsporte.ru (required for placing bets in step 09).
    /// </summary>
    public async Task<bool> LoginAsync(CancellationToken ct = default)
    {
        if (string.IsNullOrEmpty(_config.Login) || string.IsNullOrEmpty(_config.Password))
        {
            Logger.Warning("Kush: login/password not configured, skipping auth");
            return false;
        }

        // Step 1: Load main page for login form CSRF
        var mainPageRequest = new HttpRequestMessage(HttpMethod.Get, BaseUrl);
        mainPageRequest.Headers.Add("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8");

        var mainResp = await _retryPipeline.ExecuteAsync(
            async token => await _http.SendAsync(mainPageRequest, token), ct);
        mainResp.EnsureSuccessStatusCode();

        var mainHtml = await mainResp.Content.ReadAsStringAsync(ct);
        var doc = new HtmlAgilityPack.HtmlDocument();
        doc.LoadHtml(mainHtml);

        // Extract _csrf from login form hidden input
        var csrfInput = doc.DocumentNode.SelectSingleNode("//form[@id='login-widget-form']//input[@name='_csrf']");
        var formCsrf = csrfInput?.GetAttributeValue("value", null);

        if (string.IsNullOrEmpty(formCsrf))
        {
            Logger.Error("Kush: could not extract login form CSRF token");
            return false;
        }

        // Step 2: POST login
        var loginUrl = $"{BaseUrl}/users/login";
        var loginContent = new FormUrlEncodedContent(new[]
        {
            new KeyValuePair<string, string>("login-form[login]", _config.Login),
            new KeyValuePair<string, string>("login-form[password]", _config.Password),
            new KeyValuePair<string, string>("login-form[rememberMe]", "0"),
            new KeyValuePair<string, string>("_csrf", formCsrf),
        });

        var loginRequest = new HttpRequestMessage(HttpMethod.Post, loginUrl)
        {
            Content = loginContent
        };
        loginRequest.Headers.Add("Referer", BaseUrl);

        var loginResp = await _http.SendAsync(loginRequest, ct);

        // Check: successful login typically redirects to main page
        _isLoggedIn = loginResp.IsSuccessStatusCode &&
                      !loginResp.RequestMessage?.RequestUri?.AbsolutePath.Contains("/users/login", StringComparison.OrdinalIgnoreCase) == true;

        if (_isLoggedIn)
            Logger.Information("Kush: logged in as {Login}", _config.Login);
        else
            Logger.Warning("Kush: login may have failed (status={Status}, url={Url})",
                loginResp.StatusCode, loginResp.RequestMessage?.RequestUri);

        return _isLoggedIn;
    }

    /// <summary>
    /// POST an AJAX request with CSRF headers.
    /// </summary>
    public async Task<string> PostAjaxAsync(string url, Dictionary<string, string> formData,
        string? referer = null, CancellationToken ct = default)
    {
        var request = new HttpRequestMessage(HttpMethod.Post, url)
        {
            Content = new FormUrlEncodedContent(formData)
        };

        request.Headers.Add("Accept", "*/*");
        request.Headers.Add("X-Requested-With", "XMLHttpRequest");
        request.Headers.Add("Origin", BaseUrl);
        request.Headers.Add("Sec-Fetch-Dest", "empty");
        request.Headers.Add("Sec-Fetch-Mode", "cors");
        request.Headers.Add("Sec-Fetch-Site", "same-origin");

        if (!string.IsNullOrEmpty(_csrfToken))
            request.Headers.Add("X-CSRF-Token", _csrfToken);

        if (!string.IsNullOrEmpty(referer))
            request.Headers.Add("Referer", referer);

        var response = await _retryPipeline.ExecuteAsync(
            async token => await _http.SendAsync(request, token), ct);
        response.EnsureSuccessStatusCode();

        return await response.Content.ReadAsStringAsync(ct);
    }

    /// <summary>
    /// GET a page with PJAX headers (for coupon forms in step 09).
    /// </summary>
    public async Task<string> GetPjaxAsync(string url, string? referer = null, CancellationToken ct = default)
    {
        var request = new HttpRequestMessage(HttpMethod.Get, url);
        request.Headers.Add("Accept", "text/html, */*; q=0.01");
        request.Headers.Add("X-Requested-With", "XMLHttpRequest");
        request.Headers.Add("X-PJAX", "true");
        request.Headers.Add("X-PJAX-Container", "#coupon");
        request.Headers.Add("Origin", BaseUrl);
        request.Headers.Add("Sec-Fetch-Dest", "empty");
        request.Headers.Add("Sec-Fetch-Mode", "cors");
        request.Headers.Add("Sec-Fetch-Site", "same-origin");

        if (!string.IsNullOrEmpty(_csrfToken))
            request.Headers.Add("X-CSRF-Token", _csrfToken);

        if (!string.IsNullOrEmpty(referer))
            request.Headers.Add("Referer", referer);

        var response = await _retryPipeline.ExecuteAsync(
            async token => await _http.SendAsync(request, token), ct);
        response.EnsureSuccessStatusCode();

        return await response.Content.ReadAsStringAsync(ct);
    }

    /// <summary>
    /// Expose CSRF token for KushBetPlacer (step 09).
    /// </summary>
    public string? CsrfToken => _csrfToken;

    public void Dispose() => _http.Dispose();

    private static string? LoadFirstProxy(string filePath)
    {
        if (!File.Exists(filePath))
            return null;

        foreach (var line in File.ReadLines(filePath))
        {
            var trimmed = line.Trim();
            if (trimmed.Length > 0 && !trimmed.StartsWith('#'))
                return trimmed;
        }

        return null;
    }
}
