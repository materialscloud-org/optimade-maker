import click

from .scan_records import scan_records


@click.group()
def cli():
    pass


@cli.command()
def scan():
    scan_records()
