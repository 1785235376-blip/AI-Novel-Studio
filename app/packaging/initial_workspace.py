from __future__ import annotations


class InitialWorkspaceProvisioningDenied(PermissionError):
    pass


class PackagedInitialWorkspaceProvisioner:
    """Narrow adapter over repository-owned atomic first-workspace provisioning."""

    def __init__(self, repository):
        self.repository = repository

    def provision(self, actor):
        try:
            return self.repository.provision_initial_workspace(
                actor_id=actor.actor_id,
                workspace_id=actor.workspace_id,
                workspace_name="我的创作空间",
                actor_display_name="本机作者",
            )
        except (FileExistsError, KeyError, PermissionError, ValueError) as exc:
            raise InitialWorkspaceProvisioningDenied("initial workspace state is not eligible") from exc
