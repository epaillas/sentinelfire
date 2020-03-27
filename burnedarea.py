import glob
import rasterio
from rasterio.mask import mask
from rasterio.merge import merge
import numpy as np
import geopandas as gpd
from shapely.geometry import box, Polygon
from fiona.crs import from_epsg
import argparse
import sys
import os


class BurnedArea():

    def __init__(self, region, date, work_dir,
                nbr_threshold, ndwi_threshold):

        self.region = region
        self.date = date
        self.work_dir = work_dir
        self.date_dir = os.path.join(work_dir, date)
        self.region_dir = os.path.join(self.date_dir, region)
        self.geojson = self.work_dir + region + '.geojson'
        self.nbr_threshold = nbr_threshold
        self.ndwi_threshold = ndwi_threshold

        nbr_mosaic_fname = self.region_dir + '/NBR_mosaic.tif'
        ndwi_mosaic_fname = self.region_dir + '/NDWI_mosaic.tif'

        df = gpd.read_file(self.geojson)
        self.polygon = df['geometry'][0]

        # check if mosaic exists, create otherwise
        nbr_mosaic_fname = self.region_dir + '/NBR_mosaic.tif'
        ndwi_mosaic_fname = self.region_dir + '/NDWI_mosaic.tif'

        if ~os.path.isfile(nbr_mosaic_fname) or ~os.path.isfile(ndwi_mosaic_fname):
            print('Building mosaic...')
            self.BuildMosaic()

        # read mosaic and crop it to match GeoJSON
        nbr_mosaic = rasterio.open(nbr_mosaic_fname)
        ndwi_mosaic = rasterio.open(ndwi_mosaic_fname)

        print('Cropping according to GeoJSON polygon...')
        # NBR
        geo = gpd.GeoDataFrame({'geometry': self.polygon}, index=[
                                0], crs=from_epsg(4326))
        geo = geo.to_crs(crs=nbr_mosaic.crs.data)
        coords = self.getFeatures(geo)
        masked_nbr_mosaic, out_transform = mask(
            dataset=nbr_mosaic, shapes=coords, crop=False, nodata=np.nan)

        # NDWI
        geo = gpd.GeoDataFrame({'geometry': self.polygon}, index=[
                                0], crs=from_epsg(4326))
        geo = geo.to_crs(crs=ndwi_mosaic.crs.data)
        coords = self.getFeatures(geo)
        masked_ndwi_mosaic, out_transform = mask(
            dataset=ndwi_mosaic, shapes=coords, crop=False, nodata=np.nan)

        burned_area, total_area = self.GetBurnedArea(nbr=masked_nbr_mosaic[0],
                                                ndwi=masked_ndwi_mosaic[0])

        print('Total area covered: {} ha'.format(total_area))
        print('Burned area: {} ha'.format(burned_area))
        print('Burned fraction: {}'.format(burned_area * 1./total_area))

    def BuildMosaic(self):
        '''
        Builds a mosaic out of 
        NBR and NDWI from different
        tiles.
        '''
        nbr_tiles = glob.glob(self.region_dir + '/*/NBR.tif')
        ndwi_tiles = glob.glob(self.region_dir + '/*/NDWI.tif')

        nbr_mosaic, nbr_meta = self.MergeRasters(dataset=nbr_tiles)
        ndwi_mosaic, ndwi_meta = self.MergeRasters(dataset=ndwi_tiles)

        out_nbr = self.region_dir + '/NBR_mosaic.tif'
        with rasterio.open(out_nbr, 'w', **nbr_meta) as dest:
            dest.write(nbr_mosaic)

        out_ndwi = self.region_dir + '/NDWI_mosaic.tif'
        with rasterio.open(out_ndwi, 'w', **ndwi_meta) as dest:
            dest.write(ndwi_mosaic)

    def MergeRasters(self, dataset):
        '''
        Merges a set or rasters
        to build a mosaic.
        '''
        src_files_to_mosaic = []

        for raster in dataset:
            src = rasterio.open(raster)
            src_files_to_mosaic.append(src)
            
        mosaic, out_trans = merge(src_files_to_mosaic)

        out_meta = src.meta.copy()
        out_meta.update({"driver": "GTiff",
                        "height": mosaic.shape[1],
                        "width": mosaic.shape[2],
                        "transform": out_trans,
                        "crs": src.crs,
                        "dtype": src.dtypes[0]
                        }
                        )

        return mosaic, out_meta

    def GetBurnedArea(self, nbr, ndwi):

        water_mask = ndwi < self.ndwi_threshold
        burned_mask = nbr > self.nbr_threshold

        corrected_burned_mask = np.logical_and(water_mask, burned_mask)
        corrected_burned_mask = corrected_burned_mask[~np.isnan(corrected_burned_mask)]
        burned_area = np.sum(corrected_burned_mask.flatten())

        nbr = nbr[~np.isnan(nbr)]
        total_area = len(nbr.flatten())

        burned_area *= 10**2 * 1e-4
        total_area *= 10**2 * 1e-4        

        return burned_area, total_area

    def getFeatures(self, gdf):
        """Function to parse features from GeoDataFrame in such a manner that rasterio wants them"""
        import json
        return [json.loads(gdf.to_json())['features'][0]['geometry']]





parser = argparse.ArgumentParser(description='')

parser.add_argument('--region', type=str, required=True, help='GeoJSON file of region to search.')
parser.add_argument('--date', type=str, required=True, help='Fire date in format YYYYMMDD')
parser.add_argument('--work_dir', type=str, required=True, help='Directory to place files.')
parser.add_argument('--nbr_threshold', type=float, default=0.3, help='Threshold to define a burned pixel.')
parser.add_argument('--ndwi_threshold', type=float, default=0.0, help='Threshold to define a water pixel.')

args = parser.parse_args() 

burned = BurnedArea(region=args.region,
                   date=args.date,
                   work_dir=args.work_dir,
                   nbr_threshold=args.nbr_threshold,
                   ndwi_threshold=args.ndwi_threshold)


