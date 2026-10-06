using System.Text.RegularExpressions;

namespace PoemSeed.LocalInterop.Pipes;

/// <summary>Conservative defense against obvious credential-shaped metadata; not a content classifier.</summary>
internal static class IdentityMetadata
{
    // Separate small non-backtracking automata avoid both pathological matching and
    // the runtime's combined-pattern automaton-size ceiling.
    private static readonly Regex[] CredentialShapes =
    [
        Guard(@"\b(?:api[ _-]?key|provider[ _-]?secret|access[ _-]?token|oauth[ _-]?token|password|vault[ _-]?secret|authorization|cookie|dsn)\s*[:=]\s*\S+"),
        Guard(@"\bsk[-_](?:proj[-_]|svcacct[-_])?[A-Za-z0-9_-]{16,}"),
        Guard(@"\bgh[pousr]_[A-Za-z0-9]{16,}"),
        Guard(@"\bgithub_pat_[A-Za-z0-9_]{16,}"),
        Guard(@"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
        Guard(@"\b(?:AKIA|ASIA)[A-Z0-9]{16}"),
        Guard(@"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
        Guard(@"\bBearer[ ._:-][A-Za-z0-9._~-]{12,}"),
    ];
    private static Regex Guard(string pattern) => new(pattern,
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking | RegexOptions.IgnoreCase);
    private static readonly Regex Opaque = new(@"\A[A-Za-z0-9][A-Za-z0-9._:-]*\z", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
    public static bool HasCredentialShape(string value) => CredentialShapes.Any(pattern => pattern.IsMatch(value));
    public static bool SafeOpaque(string? value, int maximum) => value is { Length: > 0 } && value.Length <= maximum &&
        Opaque.IsMatch(value) && !HasCredentialShape(value);
}
