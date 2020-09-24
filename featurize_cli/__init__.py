import click


@click.group()
def cli():
    pass


@cli.group()
def instance():
    pass


@instance.command()
@click.option('-a', '--available', is_flag=True, default=False,
              help='Only return available instances.')
def ls(available):
    print(available)


@instance.command()
@click.argument('instance_id')
@click.option('-t', '--term', type=click.Choice(['daily', 'weekly', 'monthly'], case_sensitive=False))
def request(instance_id, term):
    print(f'request {instance_id} {term}')


@instance.command()
@click.argument('instance_id')
def release(instance_id):
    print(f'release {instance_id}')
