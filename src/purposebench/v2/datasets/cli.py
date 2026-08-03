"""V2-only command line entrypoints for official protected-public assets."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from purposebench.v2.datasets.cfpb_complaints import (
    download_cfpb_complaints,
    transform_cfpb_complaints,
)
from purposebench.v2.datasets.hmda import (
    HMDAQuery,
    download_hmda,
    transform_hmda,
)

app = typer.Typer(
    help=("Download and transform official public research assets under explicit v2 paths.")
)


def _csv_strings(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _csv_ints(value: str) -> tuple[int, ...]:
    return tuple(int(item) for item in _csv_strings(value))


@app.command("download-hmda")
def download_hmda_command(
    year: Annotated[int, typer.Option(min=2018)],
    raw_output: Annotated[Path, typer.Option()],
    manifest_output: Annotated[Path, typer.Option()],
    states: Annotated[
        str,
        typer.Option(help="Comma-separated two-letter state codes."),
    ] = "",
    leis: Annotated[
        str,
        typer.Option(help="Comma-separated institution LEIs."),
    ] = "",
    actions_taken: Annotated[
        str,
        typer.Option(help="Optional comma-separated HMDA action codes."),
    ] = "",
    overwrite: Annotated[bool, typer.Option()] = False,
) -> None:
    manifest = download_hmda(
        HMDAQuery(
            year=year,
            states=_csv_strings(states),
            leis=_csv_strings(leis),
            actions_taken=_csv_ints(actions_taken),
        ),
        raw_output_path=raw_output,
        manifest_output_path=manifest_output,
        overwrite=overwrite,
    )
    typer.echo(manifest.model_dump_json(indent=2))


@app.command("download-cfpb")
def download_cfpb_command(
    raw_output: Annotated[Path, typer.Option()],
    manifest_output: Annotated[Path, typer.Option()],
    overwrite: Annotated[bool, typer.Option()] = False,
    resume: Annotated[bool, typer.Option()] = False,
) -> None:
    manifest = download_cfpb_complaints(
        raw_output_path=raw_output,
        manifest_output_path=manifest_output,
        overwrite=overwrite,
        resume=resume,
    )
    typer.echo(manifest.model_dump_json(indent=2))


@app.command("transform-hmda")
def transform_hmda_command(
    raw_path: Annotated[Path, typer.Option()],
    source_manifest: Annotated[Path, typer.Option()],
    transformed_output: Annotated[Path, typer.Option()],
    manifest_output: Annotated[Path, typer.Option()],
    sample_size: Annotated[int, typer.Option(min=1)],
    seed: Annotated[int, typer.Option()] = 20260802,
    overwrite: Annotated[bool, typer.Option()] = False,
) -> None:
    manifest = transform_hmda(
        raw_path=raw_path,
        source_manifest_path=source_manifest,
        transformed_output_path=transformed_output,
        manifest_output_path=manifest_output,
        sample_size=sample_size,
        seed=seed,
        overwrite=overwrite,
    )
    typer.echo(manifest.model_dump_json(indent=2))


@app.command("transform-cfpb")
def transform_cfpb_command(
    raw_path: Annotated[Path, typer.Option()],
    source_manifest: Annotated[Path, typer.Option()],
    transformed_output: Annotated[Path, typer.Option()],
    manifest_output: Annotated[Path, typer.Option()],
    sample_size: Annotated[int, typer.Option(min=1)],
    seed: Annotated[int, typer.Option()] = 20260802,
    overwrite: Annotated[bool, typer.Option()] = False,
) -> None:
    manifest = transform_cfpb_complaints(
        raw_path=raw_path,
        source_manifest_path=source_manifest,
        transformed_output_path=transformed_output,
        manifest_output_path=manifest_output,
        sample_size=sample_size,
        seed=seed,
        overwrite=overwrite,
    )
    typer.echo(manifest.model_dump_json(indent=2))


if __name__ == "__main__":
    app()
