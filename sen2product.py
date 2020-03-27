from snappy import ProductIO
from snappy import jpy
from snappy import GPF
from astropy.io import ascii
from subprocess import call
from os.path import exists
from os import mkdir
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import numpy as np


class Sen2Product:

    def __init__(self, pre, post=None):
        self.plots = "PixEx"
        self.path = "/".join(pre['name'].split('/')[: -2])
        self.path_pre = pre['name']
        self.product_pre = ProductIO.readProduct(self.path_pre)
        self.producttype_pre = pre['producttype']
        if post:
            if pre['tile_id'] == post['tile_id']:
                self.tile_id = pre['tile_id']
            else:
                raise
            self.path_post = post['name']
            self.product_post = ProductIO.readProduct(self.path_post)
            self.producttype_post = post['producttype']
        else:
            self.tile_id = pre['tile_id']

    def _sen2cor(self, name, which):
        attr = 'producttype_{}'.format(which)
        if '1C' in getattr(self, attr):
            #call(['/bin/bash', '-i', '-c', "L2A_Process {}".format(name),
            #'--resolution', '10'])
            call(["L2A_Process", '--resolution', '10', name])

            setattr(self, attr, getattr(self, attr).replace('1C', '2A'))

            attr = 'path_{}'.format(which)
            setattr(self, attr, getattr(self, attr).replace('1C', '2A'))

    def _resample(self, name):
        p = ProductIO.readProduct(name)  # path of the xml file

        GPF.getDefaultInstance().getOperatorSpiRegistry().loadOperatorSpis()
        HashMap = jpy.get_type('java.util.HashMap')

        parameters = HashMap()
        parameters.put('targetResolution', 10)
        parameters.put('upsampling', 'Nearest')
        parameters.put('downsampling', 'First')
        parameters.put('upsampling', 'Nearest')
        parameters.put('flagDownsampling', 'First')
        parameters.put('resampleOnPyramidLevels', True)

        product = GPF.createProduct('Resample', parameters, p)
        return product

    def _band_math(self, product, name, expression):

        GPF.getDefaultInstance().getOperatorSpiRegistry().loadOperatorSpis()
        HashMap = jpy.get_type('java.util.HashMap')

        BandDescriptor = jpy.get_type(
            'org.esa.snap.core.gpf.common.BandMathsOp$BandDescriptor')

        targetBand = BandDescriptor()
        targetBand.name = name
        targetBand.type = 'float32'
        targetBand.expression = expression

        bands = jpy.array(
            'org.esa.snap.core.gpf.common.BandMathsOp$BandDescriptor', 1)
        bands[0] = targetBand

        parameters = HashMap()
        parameters.put('targetBands', bands)

        productMap = HashMap()
        if isinstance(product, list):
            for ind in range(len(product)):
                print ('p{}'.format(ind + 1))
                productMap.put('p{}'.format(ind + 1), product[ind])
            result = GPF.createProduct('BandMaths', parameters, productMap)
        else:
            result = GPF.createProduct('BandMaths', parameters, product)

        return result

    def _extract_values(self, parameters, product):
        result = GPF.createProduct('PixEx', parameters, self.product_post)
        print(result)
        t = ascii.read("pixEx_S2_MSI_Level-2Ap_measurements.txt")
        return t.copy()

    def sen2cor(self):
        if hasattr(self, 'path_pre'):
            self._sen2cor(self.path_pre, 'pre')
        if hasattr(self, 'path_post'):
            self._sen2cor(self.path_post, 'post')

    def resample(self):
        if hasattr(self, 'path_pre'):
            self.product_pre = self._resample(self.path_pre)
        if hasattr(self, 'path_post'):
            self.product_post = self._resample(self.path_post)

    def ndvi(self):
        name = 'NDVI_'
        exprss = '(B8 - B4) / (B8 + B4)'
        product = self._band_math(self.product_pre, name, exprss)
        out = "/".join([self.path, 'NDVI.tif'])
        ProductIO.writeProduct(product, out, "GeoTIFF-BigTIFF")

    def ndwi(self):
        name = 'NDWI_'
        exprss = '(B3 - B8) / (B3 + B8)'
        product = self._band_math(self.product_pre, name, exprss)
        out = "/".join([self.path, 'NDWI.tif'])
        ProductIO.writeProduct(product, out, "GeoTIFF-BigTIFF")

    def nbr(self):
        if hasattr(self, 'path_post'):
            name = 'NBR'
            exprss = '(B8 - B12) / (B8 + B12)'
            product_pre = self._band_math(self.product_pre, name, exprss)
            product_post = self._band_math(self.product_post, name, exprss)
            print( list(product_pre.getBandNames()))
            print( list(product_post.getBandNames()))

            name = 'difNBR'
            exprss = '$p1.NBR - $p2.NBR'.format(product_pre, product_post)
            products = [product_pre, product_post]
            product = self._band_math(products, name, exprss)
            out = "/".join([self.path, 'NBR.tif'])
            ProductIO.writeProduct(product, out, "GeoTIFF-BigTIFF")

    def extract_values(self, file):
        if not exists(self.plots):
            mkdir(self.plots)
        coords = []
        with open(file, 'r') as f:
            for line in f:
                line = line.replace('\n', '')
                coords.append([float(x) for x in line.split(' ')])

        GPF.getDefaultInstance().getOperatorSpiRegistry().loadOperatorSpis()
        HashMap = jpy.get_type('java.util.HashMap')

        Coords = jpy.array('org.esa.snap.pixex.Coordinate', len(coords))
        Coord = jpy.get_type('org.esa.snap.pixex.Coordinate')
        for ind, coord in enumerate(coords):
            c = Coord('Coord{}'.format(ind), coord[0], coord[1], None)
            Coords[ind] = c

        parameters = HashMap()
        parameters.put('exportBands', True)
        parameters.put('exportTiePoints', False)
        parameters.put('exportMasks', False)
        parameters.put('coordinates', Coords)
        parameters.put('outputDir', '.')

        pre = self._extract_values(parameters, self.product_pre)
        post = self._extract_values(parameters, self.product_post)
        waves = pre.meta['comments'][-1].replace('\t', ' ')
        waves = waves.replace('Wavelength:', '').split(' ')
        waves = filter(lambda x: x != '', waves)
        waves = [float(x) for x in waves]
        waves = filter(lambda x: x != 0, waves)
        bands = ['B{}'.format(ind) for ind in range(1, 9)]
        bands += ['B8A', 'B9']
        bands += ['B{}'.format(ind) for ind in range(11, 13)]
        print( pre.colnames)
        print(post.colnames)

        for ind in range(len(pre)):
            f, ax = plt.subplots()
            ax.set_xlabel('Wavelength (nm)')
            ax.set_ylabel('dl')

            radiances = list(pre[bands][ind])
            ax.plot(waves, radiances, color='g', label='pre')
            ax.scatter(waves, radiances, color='g')

            radiances = list(post[bands][ind])
            ax.plot(waves, radiances, color='b', label='post')
            ax.scatter(waves, radiances, color='b')

            lat = pre['Latitude'][ind]
            lon = pre['Longitude'][ind]
            ax.set_title("{}, {}".format(lat, lon))
            plt.legend()
            save = "{}/{}.pdf".format(self.plots, pre['Name'][ind])
            f.savefig(save, bbox_inches="tight")
