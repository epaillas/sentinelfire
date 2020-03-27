import numpy as np
import subprocess
import glob
import sentinelhub
import json
from sentinelhub import WebFeatureService, BBox, CRS, DataSource
from sentinelsat.sentinel import SentinelAPI, read_geojson, geojson_to_wkt
import datetime
import os
import sys
import argparse

class Sentinel2:

    def __init__(self, geojson, date, work_dir, delta_days,
                 user='epaillas', password='!Mcr184824'):

        self.geojson = geojson
        self.search_date = date
        self.region_name = self.geojson.split('.geojson')[-2].split('/')[-1]
        self.cloud_threshold = 5
        self.delta_days = delta_days

        print('\nSearching products for the following arguments:')
        print('\ngeojson: {}'.format(self.geojson))
        print('search_date: {}'.format(self.search_date))
        print('region_name: {}'.format(self.region_name))
        print('cloud_threshold: {}'.format(self.cloud_threshold))

        # make date directory
        self.date_dir = os.path.join(work_dir, self.search_date)

        if not os.path.exists(self.date_dir):
            os.makedirs(self.date_dir)

        # make region directory
        self.region_dir = os.path.join(self.date_dir,
                                       self.region_name)
        if not os.path.exists(self.region_dir):
            os.makedirs(self.region_dir)


        # initialize API
        self.user = user
        self.password = password
        self.api = SentinelAPI(self.user, self.password,
                               'https://scihub.copernicus.eu/dhus')

        # get footprint
        self.footprint = geojson_to_wkt(read_geojson(self.geojson))

        # get pre/post fire time intervals
        self.pre_interval, self.post_interval = self.get_date_interval(self.search_date)

        print('\nSearching pre-fire products...')
        self.pre_titles, self.pre_tiles, self.pre_dates = self.get_download_list(self.pre_interval, prefix='pre')
        print('\nSearching post-fire products...')
        self.post_titles, self.post_tiles, self.post_dates = self.get_download_list(self.post_interval, prefix='post')


        # check for missing observations
        if self.check_missing_obs() is True:
            sys.exit('Some observations are not present in pre and post lists. Aborting...')
            
        self.check_redownload()

        # build directories for the remaining tiles
        print('Building directories...')
        for tiles_set in [self.pre_tiles, self.post_tiles]:
            for tile in tiles_set:
                tile_dir = os.path.join(self.region_dir, tile)
                if not os.path.exists(tile_dir):
                    os.makedirs(tile_dir)

    def check_redownload(self):
        '''
        Checks if a certain tile has already
        been downloaded in another directory,
        in which case a symlink is created
        instead of re-downloading the product.
        '''

        global_tiles_handle = self.date_dir + '/*/*/'

        global_tiles_abs = glob.glob(global_tiles_handle)
        global_tiles = [i.split('/')[-2] for i in global_tiles_abs]

        count = 0
        for tiles_set in [self.pre_tiles, self.post_tiles]:
            for tile in tiles_set:
                if tile in global_tiles:
                    ind = np.where(tile == np.array(global_tiles))[0][0]
                    src = global_tiles_abs[ind]
                    dest = os.path.join(self.region_dir, tile)

                    count += 1

                    if not os.path.exists(dest):
                        os.symlink(src, dest)


    def check_missing_obs(self):
        missing = False
        for pre_tile in self.pre_tiles:
            if pre_tile not in self.post_tiles:
                missing = True

        for post_tile in self.post_tiles:
            if post_tile not in self.pre_tiles:
                missing = True

        return missing

    
    def download_tiles(self):

        for i in range(len(self.pre_tiles)):
            download_dir = os.path.join(self.region_dir, self.pre_tiles[i], 'pre')
            if not os.path.exists(download_dir):
                print('Downloading product: {}'.format(self.pre_titles[i]))
                self.download_tile_aws(self.pre_titles[i], download_dir)

            download_dir = os.path.join(self.region_dir, self.post_tiles[i], 'post')
            if not os.path.exists(download_dir):
                print('Downloading product: {}'.format(self.post_titles[i]))
                self.download_tile_aws(self.post_titles[i], download_dir)


    def download_tile_aws(self, title, download_dir):

        cmd = ['sentinelhub.aws',
            '--product',
            title,
            '-f',
            download_dir]

        subprocess.call(cmd)


    def get_bbox_from_geojson(self, geojson):
        '''
        Returns the bounding box of a region
        delimited by a GeoJSON file.
        '''
        with open(geojson) as f:
            data = json.load(f)
            for feature in data['features']:
                geo = feature['geometry']
                coords = geo['coordinates'][0]
                coords = np.asarray(coords)

                minx, maxx = coords[:,0].min(), coords[:,0].max()
                miny, maxy = coords[:,1].min(), coords[:,1].max()
                bbox = [minx, miny, maxx, maxy]

        return bbox

    def get_date_interval(self, date):
        search_date = datetime.datetime.strptime(date, '%Y%m%d')
        post_date = search_date + datetime.timedelta(days=self.delta_days)
        pre_date = search_date - datetime.timedelta(days=self.delta_days)

        pre_interval = ((pre_date - datetime.timedelta(days=60)).strftime('%Y%m%d'),
                        pre_date.strftime('%Y%m%d'))

        post_interval = (post_date.strftime('%Y%m%d'),
                        (post_date + datetime.timedelta(days=60)).strftime('%Y%m%d'))

        return pre_interval, post_interval

    def get_download_list(self, time_interval, prefix='pre'):


        products = self.api.query(self.footprint,
                                  date=time_interval,
                                  platformname='Sentinel-2',
                                  producttype='S2MSI1C')

        products_df = self.api.to_dataframe(products)

        titles = products_df['title'].values
        clouds = products_df['cloudcoverpercentage'].values
        dates = products_df['beginposition'].values
        dates = [str(date)[:10] for date in dates]
        tiles = [t.split('_')[-2][1:] for t in titles]

        tiles = np.array(tiles)
        dates = np.array(dates)
        clouds = np.array(clouds)
        titles = np.array(titles)

        if prefix == 'post':
            titles = titles[::-1]
            tiles = tiles[::-1]
            dates = dates[::-1]
            clouds = clouds[::-1]

        unique_tiles = np.unique(tiles).tolist()
        ntiles = len(unique_tiles)

        sorted_dict = {}

        for tile in unique_tiles:
            sorted_dict[tile] = {} 

            mask = tiles == tile
            sorted_dict[tile]['dates'] = dates[mask]
            sorted_dict[tile]['titles'] = titles[mask]
            sorted_dict[tile]['clouds'] = clouds[mask]

        download_idx = -1
        cloud_fraction = 100

        while cloud_fraction  > self.cloud_threshold:
            download_idx += 1

            try:
                cloud_fraction = np.sum([sorted_dict[tname]['clouds'][download_idx] 
                                        for tname in unique_tiles]) / ntiles

            except:
                print('None of the available observations satisfied cloud_threshold {}%. '.format(self.cloud_threshold))
                print('Raising cloud_threshold by 5 per cent.')
                self.cloud_threshold += 5
                download_idx = -1
                cloud_fraction = 100

        print('Cloud fraction of mosaic: {}'.format(cloud_fraction))

        tiles = unique_tiles
        titles = [sorted_dict[tname]['titles'][download_idx] for tname in unique_tiles]
        dates = [sorted_dict[tname]['dates'][download_idx] for tname in unique_tiles]
        clouds = [sorted_dict[tname]['clouds'][download_idx] for tname in unique_tiles]

        import csv
        logfile = os.path.join(self.region_dir, 'download_{}.log'.format(prefix))
        f = open(logfile, 'w')

        with f:
            writer = csv.writer(f)
            header = ['Title', 'Tile name', 'Date', 'Cloud fraction']
            writer.writerow(header)
            for i in range(len(tiles)):
                csv_data = [titles[i], tiles[i], dates[i], clouds[i]]
                writer.writerow(csv_data)
        f.close()


        return titles, tiles, dates

parser = argparse.ArgumentParser(description='')

parser.add_argument('--geojson', type=str, required=True, help='GeoJSON file of region to search.')
parser.add_argument('--date', type=str, required=True, help='Fire date in format YYYYMMDD')
parser.add_argument('--work_dir', type=str, required=True, help='Directory to place files.')
parser.add_argument('--delta_days', type=int, help='Number of days between the event and the pre/post fire observations.')

args = parser.parse_args() 

search = Sentinel2(geojson=args.geojson,
                   date=args.date,
                   work_dir=args.work_dir)

search.download_tiles()
