using System.Text;
using System.Text.Json;

namespace AINovelStudio.DesktopHost;

internal sealed class HostControlRuntime
{
    private readonly Uri expectedOrigin;
    private readonly string runtimeInstanceId;
    private readonly TextWriter writer;
    private readonly Action<string>? observer;
    private readonly bool startupPingEnabled;
    private bool startupPingSent;
    private bool webViewPingSent;
    private const int CredentialMaxUtf8Bytes = 1024;
    private const int CredentialFrameMaxBytes = 4096;

    private static bool IsSupportedCredentialProvider(string? provider) => provider is
        "deepseek" or "openai" or "claude" or "gemini" or "ddshub" or "custom";

    internal HostControlRuntime(string frontendOrigin, string runtimeInstanceId, TextWriter writer,
        Action<string>? observer = null, bool startupPingEnabled = true)
    {
        expectedOrigin = new Uri(frontendOrigin);
        this.runtimeInstanceId = runtimeInstanceId;
        this.writer = writer;
        this.observer = observer;
        this.startupPingEnabled = startupPingEnabled;
    }

    internal void EmitStartupPing()
    {
        if (!startupPingEnabled || startupPingSent) return;
        startupPingSent = true;
        WriteA2Ping();
    }

    internal bool HandleWebMessage(string sourceValue, string json)
    {
        if (!IsExpectedSource(sourceValue) || string.IsNullOrEmpty(json)
            || Encoding.UTF8.GetByteCount(json) > 1024) return false;
        try
        {
            using var document = JsonDocument.Parse(json);
            if (document.RootElement.ValueKind != JsonValueKind.Object) return false;
            var root = document.RootElement;
            if (root.EnumerateObject().Count() != 2
                || !root.TryGetProperty("protocol", out var protocol) || !root.TryGetProperty("type", out var type)
                || protocol.ValueKind != JsonValueKind.String || type.ValueKind != JsonValueKind.String
                || protocol.GetString() != "ai-novel-webview/v1" || type.GetString() != "PING"
                || webViewPingSent) return false;
            webViewPingSent = true;
            observer?.Invoke("WEBVIEW_PING_ACCEPTED");
            WriteA2Ping();
            observer?.Invoke("A2_PING_EMITTED_FROM_WEBVIEW");
            return true;
        }
        catch (JsonException) { return false; }
    }

    internal bool HandleWebCredentialMessage(string sourceValue, string json)
    {
        if (!IsExpectedSource(sourceValue) || string.IsNullOrEmpty(json)
            || Encoding.UTF8.GetByteCount(json) > CredentialFrameMaxBytes) return false;
        try
        {
            using var document = JsonDocument.Parse(json);
            if (document.RootElement.ValueKind != JsonValueKind.Object) return false;
            var root = document.RootElement;
            if (!root.TryGetProperty("protocol", out var protocol)
                || !root.TryGetProperty("type", out var type)
                || !root.TryGetProperty("provider", out var provider)
                || protocol.ValueKind != JsonValueKind.String || type.ValueKind != JsonValueKind.String
                || provider.ValueKind != JsonValueKind.String
                || protocol.GetString() != "ai-novel-webview-credential/v1"
                || !IsSupportedCredentialProvider(provider.GetString())) return false;

            var providerId = provider.GetString()!;

            return type.GetString() switch
            {
                "SET_PROVIDER_CREDENTIAL" => HandleWebCredentialSet(root, providerId),
                "CLEAR_PROVIDER_CREDENTIAL" => root.EnumerateObject().Count() == 3
                    && ClearProviderCredential(providerId),
                _ => false,
            };
        }
        catch (JsonException) { return false; }
    }

    private bool HandleWebCredentialSet(JsonElement root, string provider)
    {
        if (root.EnumerateObject().Count() != 4
            || !root.TryGetProperty("credential", out var credential)
            || credential.ValueKind != JsonValueKind.String) return false;
        return EmitProviderCredential(provider, credential.GetString()!);
    }

    private bool IsExpectedSource(string sourceValue) =>
        Uri.TryCreate(sourceValue, UriKind.Absolute, out var source)
        && source.Scheme == expectedOrigin.Scheme && source.Host == expectedOrigin.Host && source.Port == expectedOrigin.Port
        && source.AbsolutePath == "/" && string.IsNullOrEmpty(source.Query)
        && string.IsNullOrEmpty(source.Fragment) && string.IsNullOrEmpty(source.UserInfo);

    // Credential transport is deliberately separate from the frozen PING protocol.
    internal bool EmitProviderCredential(string provider, string credential)
    {
        if (!IsSupportedCredentialProvider(provider) || string.IsNullOrEmpty(credential)
            || Encoding.UTF8.GetByteCount(credential) > CredentialMaxUtf8Bytes
            || credential.IndexOfAny(new[] { '\0', '\r', '\n' }) >= 0) return false;
        var frame = JsonSerializer.Serialize(new { protocol = "packaged-host-credential/v1", type = "SET_PROVIDER_CREDENTIAL", runtime_instance_id = runtimeInstanceId, provider, credential });
        if (Encoding.UTF8.GetByteCount(frame) > CredentialFrameMaxBytes) return false;
        writer.WriteLine("AI_NOVEL_HOST_CREDENTIAL_V1\t" + frame); writer.Flush();
        return true;
    }

    internal bool ClearProviderCredential(string provider)
    {
        if (!IsSupportedCredentialProvider(provider)) return false;
        var frame = JsonSerializer.Serialize(new { protocol = "packaged-host-credential/v1", type = "CLEAR_PROVIDER_CREDENTIAL", runtime_instance_id = runtimeInstanceId, provider });
        writer.WriteLine("AI_NOVEL_HOST_CREDENTIAL_V1\t" + frame); writer.Flush();
        return true;
    }

    private void WriteA2Ping()
    {
        var payload = JsonSerializer.Serialize(new HostControlPing("packaged-host-control/v1", "PING", runtimeInstanceId));
        writer.WriteLine("AI_NOVEL_HOST_CONTROL_V1\t" + payload);
        writer.Flush();
    }
}
