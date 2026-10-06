using System.Buffers.Binary;
using System.Text;
using System.Text.Json;

namespace PoemSeed.LocalInterop.Pipes;

/// <summary>Frozen V1 length-prefix framing only; canonical DTO/authority checks belong to the adapter.</summary>
public static class PipeFrames
{
    public const int MaximumFrameBytes = 1_048_576;
    public const int MaximumJsonDepth = 24;
    private static readonly UTF8Encoding StrictUtf8 = new(false, true);

    public static byte[] Encode(string json)
    {
        ArgumentNullException.ThrowIfNull(json);
        // Check before parsing/encoding to avoid unbounded caller-controlled allocation.
        if (json.Length is 0 or > MaximumFrameBytes || StrictUtf8.GetByteCount(json) > MaximumFrameBytes)
            throw new InvalidDataException("Frame exceeds the bounded transport contract.");
        Validate(json);
        return StrictUtf8.GetBytes(json);
    }

    public static async Task<string> ReadAsync(Stream stream, TimeSpan timeout, CancellationToken cancellationToken = default)
    {
        using var deadline = Deadline(timeout, cancellationToken);
        byte[] prefix = new byte[4];
        await stream.ReadExactlyAsync(prefix, deadline.Token).ConfigureAwait(false);
        uint length = BinaryPrimitives.ReadUInt32LittleEndian(prefix);
        if (length is 0 or > MaximumFrameBytes)
            throw new InvalidDataException("Frame exceeds the bounded transport contract.");
        byte[] body = new byte[(int)length];
        await stream.ReadExactlyAsync(body, deadline.Token).ConfigureAwait(false);
        string json = StrictUtf8.GetString(body);
        Validate(json);
        return json;
    }

    public static Task WriteAsync(Stream stream, string json, TimeSpan timeout, CancellationToken cancellationToken = default) =>
        WriteEncodedAsync(stream, Encode(json), timeout, cancellationToken);

    internal static async Task WriteEncodedAsync(Stream stream, byte[] body, TimeSpan timeout, CancellationToken cancellationToken)
    {
        using var deadline = Deadline(timeout, cancellationToken);
        byte[] prefix = new byte[4];
        BinaryPrimitives.WriteUInt32LittleEndian(prefix, (uint)body.Length);
        await stream.WriteAsync(prefix, deadline.Token).ConfigureAwait(false);
        await stream.WriteAsync(body, deadline.Token).ConfigureAwait(false);
        await stream.FlushAsync(deadline.Token).ConfigureAwait(false);
    }

    internal static CancellationTokenSource Deadline(TimeSpan timeout, CancellationToken cancellationToken)
    {
        if (timeout <= TimeSpan.Zero || timeout > TimeSpan.FromMinutes(2))
            throw new ArgumentOutOfRangeException(nameof(timeout));
        var source = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        source.CancelAfter(timeout);
        return source;
    }

    private static void Validate(string json)
    {
        using var parsed = JsonDocument.Parse(json, new JsonDocumentOptions
        {
            MaxDepth = MaximumJsonDepth,
            CommentHandling = JsonCommentHandling.Disallow,
            AllowTrailingCommas = false,
        });
        if (parsed.RootElement.ValueKind != JsonValueKind.Object)
            throw new InvalidDataException("Protocol frame must be a JSON object.");
        // Reject duplicate keys instead of letting different DTO readers disagree.
        RejectDuplicates(parsed.RootElement);
    }

    private static void RejectDuplicates(JsonElement node)
    {
        if (node.ValueKind == JsonValueKind.Object)
        {
            var names = new HashSet<string>(StringComparer.Ordinal);
            foreach (var member in node.EnumerateObject())
            {
                if (!names.Add(member.Name)) throw new InvalidDataException("Duplicate JSON member.");
                RejectDuplicates(member.Value);
            }
        }
        else if (node.ValueKind == JsonValueKind.Array)
            foreach (var child in node.EnumerateArray()) RejectDuplicates(child);
    }
}
