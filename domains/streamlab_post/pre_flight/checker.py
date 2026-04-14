"""
PreFlightChecker — Phase 6 pre-stream readiness check runner.

Runs all six checks in order and collects a flat list of result dicts.
credentials_check returns a list; all others return a single dict.
The checker flattens everything into one ordered list for the entry point.

Result dict shape:
  {
    "name":    str,               # check identifier
    "status":  "ok"|"warn"|"fail",
    "message": str,               # human-readable detail line
  }
"""

from pathlib import Path

from domains.streamlab_post.pre_flight.checks import (
    obs_check,
    config_check,
    path_check,
    inbox_check,
    process_check,
    credentials_check,
)


class PreFlightChecker:
    """
    Orchestrate all six pre-flight checks and return a flat result list.

    No dependencies on engine/graph/ — domain-layer only.
    """

    def run(
        self,
        dry_run: bool = False,
        config_path: str | Path | None = None,
    ) -> list[dict]:
        """
        Execute all checks.

        Args:
            dry_run:     Skip live connections and API calls; return mock ok.
            config_path: Override session_config.yaml path (used in tests).

        Returns:
            Ordered list of result dicts. Credentials check contributes
            multiple rows (one per sub-check).
        """
        results: list[dict] = []

        # Hard-failure checks — order matters: bail early if OBS is down,
        # but we always run ALL checks and collect every result.
        results.append(obs_check.run(dry_run=dry_run))
        results.append(config_check.run(dry_run=dry_run, config_path=config_path))
        results.append(path_check.run(dry_run=dry_run, config_path=config_path))
        results.append(inbox_check.run(dry_run=dry_run))
        results.append(process_check.run(dry_run=dry_run))

        # Soft-warning checks — credentials_check returns a list.
        cred_results = credentials_check.run(dry_run=dry_run, config_path=config_path)
        results.extend(cred_results)

        return results
