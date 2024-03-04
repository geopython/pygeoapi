# =================================================================
#
# Authors: Ms. Prajwalita Jayadev Chavan <prajwalita.chavan@gmail.com>
#
# Copyright (c) 2024 Prajwalita Jayadev Chavan, GISE Hub, IIT Bombay
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# =================================================================



import logging

from pygeoapi.process.base import BaseProcessor, ProcessorExecuteError

LOGGER = logging.getLogger(__name__)
# =================================================================

#: Process metadata and description
PROCESS_METADATA = {
    'version': '0.1.0',
    'id': 'GDAL_LC',
    'title': {
        'en': 'GDAL Land Cover Change Analysis Processor'
    },
    'description': {
        'en': 'An OGC API: processes that takes Land Cover(LC) of separate timeframe and find Land Cover Change Analysis using GDAL'
              'the GDAL_LC raster change analysis result'
    },
    'jobControlOptions': ['sync-execute', 'async-execute'],
    'keywords': ['GDAL_LC_ChangeAnalysis'],
    'links': [{
        'type': 'text/html',
        'rel': 'about',
        'title': 'information',
        'href': 'https://example.org/process',
        'hreflang': 'en-US'
    }],
    'inputs': {
        # provide ratser files path
    },
    'outputs': {
        'GDAL_LC': {
            'title': 'GDAL_LC',
            'description': 'An example process that change analysis GDAL_LC '
                           'GDAL_LC Change Analysis result',
            'schema': {
                'type': 'object',
                'contentMediaType': 'application/geo+json'
            }
        }
    },
    'example': {
        'inputs': {
            # provide ratser files path
            
        }
    }
}
# =================================================================




class GDAL_LC_ChangeAnalysisProcessor(BaseProcessor):
    """GDAL_LC_ChangeAnalysis Processor example"""

    def __init__(self, processor_def):
        """
        Initialize object

        :param processor_def: provider definition

        :returns: pygeoapi.process.GDAL.GDAL_LC_ChangeAnalysis
        """

        super().__init__(processor_def, PROCESS_METADATA)

    def execute(self, data):

        value = None
        mimetype = 'application/geo+json'

        from osgeo import ogr, gdal, osr
        import numpy as np
        import os
        import matplotlib.pyplot as plt

        #Input Raster and Vector Paths
        #Image-2019
        path_B5_2019="/pygeoapi/mydata/GDAL/Input/Image20190203clip/LC08_L1TP_029047_20190203_20190206_01_T1_B5_clip.TIF"
        path_B4_2019="/pygeoapi/mydata/GDAL/Input/Image20190203clip/LC08_L1TP_029047_20190203_20190206_01_T1_B4_clip.TIF"
        #Image-2014
        path_B5_2014="/pygeoapi/mydata/GDAL/Input/Image20140205clip/LC08_L1TP_029047_20140205_20170307_01_T1_B5_clip.TIF"
        path_B4_2014="/pygeoapi/mydata/GDAL/Input/Image20140205clip/LC08_L1TP_029047_20140205_20170307_01_T1_B4_clip.TIF"

        #Output Files
        #Output NDVI Rasters 
        path_NDVI_2019 = '/pygeoapi/mydata/GDAL/Output/NDVI2019.tif'
        path_NDVI_2014 = '/pygeoapi/mydata/GDAL/Output/NDVI2014.tif'
        path_NDVIChange_19_14 = '/pygeoapi/mydata/GDAL/Output/NDVIChange_19_14.tif'
        #NDVI Contours
        contours_NDVIChange_19_14 = '/pygeoapi/mydata/GDAL/Output/NDVIChange_19_14.shp'

        #Open raster bands
        B5_2019 = gdal.Open(path_B5_2019)
        B4_2019 = gdal.Open(path_B4_2019)
        B5_2014 = gdal.Open(path_B5_2014)
        B4_2014 = gdal.Open(path_B4_2014)

        #Read bands as matrix arrays
        B52019_Data = B5_2019.GetRasterBand(1).ReadAsArray().astype(np.float32)
        B42019_Data = B4_2019.GetRasterBand(1).ReadAsArray().astype(np.float32)
        B52014_Data = B5_2014.GetRasterBand(1).ReadAsArray().astype(np.float32)
        B42014_Data = B4_2014.GetRasterBand(1).ReadAsArray().astype(np.float32)

        print(B5_2014.GetProjection()[:80])
        print(B5_2019.GetProjection()[:80])
        if B5_2014.GetProjection()[:80]==B5_2019.GetProjection()[:80]: print('SRC OK')

        print(B52014_Data.shape)
        print(B52019_Data.shape)
        if B52014_Data.shape==B52019_Data.shape: print('Array Size OK')

        print(B5_2014.GetGeoTransform())
        print(B5_2019.GetGeoTransform())
        if B5_2014.GetGeoTransform()==B5_2019.GetGeoTransform(): print('Geotransformation OK')

        geotransform = B5_2014.GetGeoTransform()

        originX,pixelWidth,empty,finalY,empty2,pixelHeight=geotransform
        cols =  B5_2014.RasterXSize
        rows =  B5_2014.RasterYSize

        projection = B5_2014.GetProjection()

        finalX = originX + pixelWidth * cols
        originY = finalY + pixelHeight * rows

        ndvi2014 = np.divide(B52014_Data - B42014_Data, B52014_Data+ B42014_Data,where=(B52014_Data - B42014_Data)!=0)
        ndvi2014[ndvi2014 == 0] = -999

        ndvi2019 = np.divide(B52019_Data - B42019_Data, B52019_Data+ B42019_Data,where=(B52019_Data - B42019_Data)!=0)
        ndvi2019[ndvi2019 == 0] = -999

        def saveRaster(dataset,datasetPath,cols,rows,projection):
            rasterSet = gdal.GetDriverByName('GTiff').Create(datasetPath, cols, rows,1,gdal.GDT_Float32)
            rasterSet.SetProjection(projection)
            rasterSet.SetGeoTransform(geotransform)
            rasterSet.GetRasterBand(1).WriteArray(dataset)
            rasterSet.GetRasterBand(1).SetNoDataValue(-999)
            rasterSet = None

        saveRaster(ndvi2014,path_NDVI_2014,cols,rows,projection)

        saveRaster(ndvi2019,path_NDVI_2019,cols,rows,projection)

        extentArray = [originX,finalX,originY,finalY]
        def plotNDVI(ndviImage,extentArray,vmin,cmap):
            ndvi = gdal.Open(ndviImage)
            ds2019 = ndvi.ReadAsArray()
            plt.figure(figsize=(20,15))
            im = plt.imshow(ds2019, vmin=vmin, cmap=cmap, extent=extentArray)#
            plt.colorbar(im, fraction=0.015)
            plt.xlabel('Este')
            plt.ylabel('Norte')
            plt.show()

        plotNDVI(path_NDVI_2014,extentArray,0,'YlGn')
        plotNDVI(path_NDVI_2019,extentArray,0,'YlGn')   
        # =================================================================  
                
        ndviChange = ndvi2019-ndvi2014
        ndviChange = np.where((ndvi2014>-999) & (ndvi2019>-999),ndviChange,-999)            
        saveRaster(ndviChange,path_NDVIChange_19_14,cols,rows,projection)
        plotNDVI(path_NDVIChange_19_14,extentArray,-0.5,'Spectral')
        # ================================================================= 

        Dataset_ndvi = gdal.Open(path_NDVIChange_19_14)#path_NDVI_2014
        ndvi_raster = Dataset_ndvi.GetRasterBand(1)

        ogr_ds = ogr.GetDriverByName("ESRI Shapefile").CreateDataSource(contours_NDVIChange_19_14)

        prj=Dataset_ndvi.GetProjectionRef()#GetProjection()

        srs = osr.SpatialReference(wkt=prj)#
        #srs.ImportFromProj4(prj)

        contour_shp = ogr_ds.CreateLayer('contour', srs)
        field_defn = ogr.FieldDefn("ID", ogr.OFTInteger)
        contour_shp.CreateField(field_defn)
        field_defn = ogr.FieldDefn("ndviChange", ogr.OFTReal)
        contour_shp.CreateField(field_defn)
        #Generate Contourlines
        gdal.ContourGenerate(ndvi_raster, 0.1, 0, [], 1, -999, contour_shp, 0, 1)
        ogr_ds = None        
        # ================================================================= 

       
        outputs = {
            'id': 'GDAL_LC_ChangeAnalysis',         
                }
        # =================================================================      
        
             
       
        #Final output
        return mimetype, outputs

    def __repr__(self):
        return f'<GDAL_LC_ChangeAnalysis> {self.name}'




