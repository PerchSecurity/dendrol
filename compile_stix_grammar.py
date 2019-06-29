#!/usr/bin/env python
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Union

import click
import requests
from tqdm import tqdm
from ww import f


@click.command()
@click.option('-o', '--output',
              type=click.Path(exists=True, file_okay=False, resolve_path=True),
              default='./dendrol/lang/',
              help='Directory to save the generated Python modules into')
@click.option('--force-antlr-download',
              default=False,
              help='Force the ANTLR .jar to be downloaded, even if it already exists')
@click.option('--progress',
              default=True)
def compile_stix_grammar(output, force_antlr_download      , progress      ):
    output = Path(output)

    if not is_java_installed():
        click.echo('Java could not be found. It is required to run the ANTLR '
                   'compiler. Please install it, and ensure the "java" '
                   'executable is on your PATH.', color='red')
        sys.exit(2)

    jar_path = get_antlr_jar_path(output)
    will_download_antlr = False

    if force_antlr_download:
        will_download_antlr = True

    elif not is_antlr_jar_saved(output):
        will_download_antlr = True
        click.echo(f('ANTLR .jar not found at: {jar_path}'), color='orange')

    if will_download_antlr:
        click.echo(f('Downloading ANTLR .jar to: {jar_path}'))
        save_antlr_jar(directory=output, display_progress=progress)

    compile_grammar(output_dir=output)
    click.echo(f('Successfully compiled grammar to: {output}'), color='green')


def is_java_installed()        :
    """Simple check to detect existence of Java."""
    try:
        retcode = subprocess.check_call(
            ['java', '-version'],
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, OSError):
        return False
    else:
        return retcode == 0


def compile_grammar(output_dir       = None)        :
    """Generate lexer, parser, listener, and visitor classes for the STIX grammar

    If output_dir is not passed, the directory of this module is used.
    """
    jar_path = get_antlr_jar_path(output_dir)

    retcode = subprocess.check_call(
        cwd=output_dir,
        env={'CLASSPATH': str(jar_path)},
        args=[
            'java',
            'org.antlr.v4.Tool',
            '-Dlanguage=Python3',
            '-visitor',
            '-listener',
            '-package', get_antlr_jar_path.__module__,
            '-o', output_dir,
            'STIXPattern.g4',
        ],
    )
    return retcode == 0


def save_antlr_jar(directory      , display_progress=False)        :
    """Download and save the ANTLR .jar
    """
    path = get_antlr_jar_path(directory)
    content = stream_antlr_jar()

    if display_progress:
        url = get_antlr_jar_download_url()
        head_res = requests.head(url)
        head_res.raise_for_status()
        file_size = int(head_res.headers['Content-Length'])

        pbar = tqdm(
            iterable=content,
            total=file_size,
            unit='B',
            unit_scale=True,
            desc=path.name,
        )
        content = _iter_with_progress(pbar)

    with path.open('wb') as fp:
        for chunk in content:
            fp.write(chunk)

    return path


def _iter_with_progress(pbar):
    for chunk in pbar:
        if chunk:
            pbar.update(len(chunk))
        yield chunk
    pbar.close()


def stream_antlr_jar(chunk_size=1024)                   :
    """Retrieve the ANTLR .jar in chunks from the internet
    """
    url = get_antlr_jar_download_url()
    response = requests.get(url, stream=True)
    response.raise_for_status()

    for chunk in response.iter_content(chunk_size=chunk_size):
        yield chunk


def get_antlr_jar_path(directory      )        :
    return directory / 'antlr-4.7.1-complete.jar'


def is_antlr_jar_saved(directory      )        :
    return get_antlr_jar_path(directory).exists()


def get_antlr_jar_download_url()       :
    return 'https://www.antlr.org/download/antlr-4.7.1-complete.jar'


if __name__ == '__main__':
    compile_stix_grammar()
