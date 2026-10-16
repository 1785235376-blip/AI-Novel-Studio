namespace PoemSeed.LocalInterop.Pipes;

/// <summary>
/// Return verified registration evidence bound to this connected process's loaded
/// product image. A path match or a signed file currently at that path is insufficient.
/// Missing loaded-image / replacement-race proof must fail closed (LOCAL_REQUIRED).
/// </summary>
public interface IInstalledProductVerifier
{
    ValueTask<InstallationEvidence?> VerifyAsync(PeerVerificationTarget target, PeerClaims claims, CancellationToken cancellationToken);
}

/// <summary>
/// Bind verified publisher evidence to the connected process's loaded image/payload,
/// not a later replacement at ExecutablePath. Return UNAVAILABLE if this cannot be proved.
/// </summary>
public interface ISignedExecutableVerifier
{
    ValueTask<SignatureEvidence> VerifyAsync(PeerVerificationTarget target, CancellationToken cancellationToken);
}

public sealed record InstallationEvidence(string ProductId, string InstallationId, string ExecutablePathHash,
    string PublisherIdentity, string ProductVersion, string ProtocolVersion, bool UserApproved, bool Revoked, bool ConnectedImageVerified = false);
public enum SignatureStatus { UNAVAILABLE, INVALID, VALID }
public sealed record SignatureEvidence(SignatureStatus Status, string? PublisherIdentity, bool ConnectedImageVerified = false);
public sealed record AttestationResult(PeerIdentity Identity, string Reason, string EvidenceStatus)
{
    // Authentication remains distinct from protocol session/capability/content authorization.
    public bool Authenticated => Identity.AttestationState == AttestationState.TRUSTED_INSTALLATION;
}

/// <summary>No embedded allowlist, publisher assumption, or hash-only authentication.</summary>
public sealed class InteropPeerAttestation(IInstalledProductVerifier? installations = null, ISignedExecutableVerifier? signatures = null)
{
    public async ValueTask<AttestationResult> VerifyAsync(PeerVerificationTarget target, PeerClaims claims, CancellationToken cancellationToken = default)
    {
        // Never retain invalid peer strings in identity, diagnostics, or audit state.
        if (!claims.IsWellFormed())
            return new(target.Identity with { AttestationState = AttestationState.REJECTED },
                "INVALID_OR_UNSUPPORTED_CLAIMS", "CONTRACT_VERIFIED");
        var identity = target.Identity with
        {
            ProductId = claims.ProductId, InstanceId = claims.InstanceId, ProductVersion = claims.ProductVersion,
        };
        AttestationResult Result(AttestationState state, string reason, string evidence = "CONTRACT_VERIFIED") =>
            new(identity with { AttestationState = state }, reason, evidence);
        cancellationToken.ThrowIfCancellationRequested();
        if (installations is null) return Result(AttestationState.REJECTED, "INSTALLATION_PROOF_UNAVAILABLE", "LOCAL_REQUIRED");
        var record = await installations.VerifyAsync(target, claims, cancellationToken).ConfigureAwait(false);
        cancellationToken.ThrowIfCancellationRequested();
        if (record is null) return Result(AttestationState.REJECTED, "UNREGISTERED_INSTALLATION");
        if (!IdentityMetadata.SafeOpaque(record.InstallationId, 128) || !IdentityMetadata.SafeOpaque(record.PublisherIdentity, 256))
            return Result(AttestationState.REJECTED, "INVALID_INSTALLATION_IDENTITY_METADATA");
        if (!record.ConnectedImageVerified)
            return Result(AttestationState.REJECTED, "LOADED_IMAGE_BINDING_UNAVAILABLE", "LOCAL_REQUIRED");
        if (record.Revoked || record.ProductId != claims.ProductId || record.ProductVersion != claims.ProductVersion ||
            record.ProtocolVersion != claims.ProtocolVersion || record.ExecutablePathHash != identity.ExecutablePathHash ||
            string.IsNullOrWhiteSpace(record.InstallationId) || string.IsNullOrWhiteSpace(record.PublisherIdentity))
            return Result(AttestationState.REJECTED, "INSTALLATION_MISMATCH_OR_REVOKED");
        if (signatures is null) return Result(AttestationState.KNOWN_PRODUCT, "SIGNATURE_PROOF_UNAVAILABLE", "LOCAL_REQUIRED");
        var signed = await signatures.VerifyAsync(target, cancellationToken).ConfigureAwait(false);
        cancellationToken.ThrowIfCancellationRequested();
        if (signed.PublisherIdentity is not null && !IdentityMetadata.SafeOpaque(signed.PublisherIdentity, 256))
            return Result(AttestationState.REJECTED, "INVALID_PUBLISHER_IDENTITY_METADATA");
        if (signed.Status == SignatureStatus.UNAVAILABLE)
            return Result(AttestationState.KNOWN_PRODUCT, "SIGNATURE_PROOF_UNAVAILABLE", "LOCAL_REQUIRED");
        if (signed.Status != SignatureStatus.VALID || signed.PublisherIdentity != record.PublisherIdentity)
            return Result(AttestationState.REJECTED, "SIGNATURE_OR_PUBLISHER_MISMATCH");
        if (!signed.ConnectedImageVerified)
            return Result(AttestationState.KNOWN_PRODUCT, "LOADED_IMAGE_BINDING_UNAVAILABLE", "LOCAL_REQUIRED");
        return record.UserApproved
            ? Result(AttestationState.TRUSTED_INSTALLATION, "APPROVED_INSTALLATION_AND_PUBLISHER_VERIFIED")
            : Result(AttestationState.SIGNED_PRODUCT, "USER_APPROVAL_REQUIRED");
    }
}
