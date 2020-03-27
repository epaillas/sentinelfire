from sen2product import Sen2Product
from os.path import join, exists
from os import listdir
import os
import glob
import click

@click.command()
@click.option(
    '--tileid', '-tileid',
    help="Tile ID"
)
def main(tileid):
    click.echo("{}".format(tileid))
    pre = join(tileid, 'pre')
    if exists(pre):
        pre = glob.glob(pre + '/*')
        pre = pre[1] if len(
            pre) > 1 else pre[0] if len(pre) > 0 else ''
    else:
        pre = None
    name = pre.split('_')[1]
    pre = {'name': join(tileid, 'pre', pre)}
    pre['producttype'] = '2A' if '2A' in name else '1C'
    pre['tile_id'] = pre['name'].split('_')[-2].split('.')[0]

    post = join(tileid, 'post')
    name = ''
    if exists(post):
        post = glob.glob(post + '/*')
        post = post[1] if len(
            post) > 1 else post[0] if len(post) > 0 else ''
    else:
        post = ''
    if post != '':
        name = post.split('_')[1]
        post = {'name': join(tileid, 'post', post)}
    else:
        post = {'name': '_'}

    post['producttype'] = '2A' if '2A' in name else '1C'
    post['tile_id'] = post['name'].split('_')[-2].split('.')[0]

    print('1: {}'.format(pre['tile_id']))
    print('2: {}'.format(post['tile_id']))

    if post['name'] != '':
        sen2 = Sen2Product(pre, post)
    else:
        sen2 = Sen2Product(pre)
    
    click.echo('Resample...')
    sen2.resample()


    if not exists(join(tileid, 'NBR.tif')):
        click.echo('NBR...')
        sen2.nbr()

    if not exists(join(tileid, 'NDWI.tif')):
        click.echo('NDWI...')
        sen2.ndwi()

    if not exists(join(tileid, 'NDVI.tif')):
        click.echo('NDVI...')
        sen2.ndvi()

    del sen2


if __name__ == '__main__':
    main()
