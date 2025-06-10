# maybe incorprate some multiprocessing; it takes awhile with bigger DEMs

from osgeo import gdal, osr, ogr
from scipy.ndimage import binary_erosion, binary_dilation
import simplekml
import numpy as np
from shapely.geometry import Polygon

# function for loading dem and getting elevation data while ignoring -9999.0 values
def load_dem(file):
    ds = gdal.OpenEx(file)
    band = ds.GetRasterBand(1)
    arr = band.ReadAsArray()
    nodata = band.GetNoDataValue()
    return ds, arr, nodata

# function for finding pixel edge and generating mask
def extract_edge_mask(arr, nodata, dialations=2):
    valid_mask = (arr != nodata).astype(np.uint8)
    edge_mask = valid_mask - binary_erosion(valid_mask).astype(np.uint8)

    # increase edge width for easier visualization
    if dialations > 0:
        edge_mask = binary_dilation(edge_mask, iterations=dialations).astype(np.uint8)
    return edge_mask

# function to create temporary raster dataset entirely stored in RAM
def mask_to_memory_raster(edge_mask, ds):
    # tell GDAL to use MEM driver 
    driver = gdal.GetDriverByName("MEM")

    # actually create the raster
    mask_ds = driver.Create("", ds.RasterXSize, ds.RasterYSize, 1, gdal.GDT_Byte)

    # line temporary mask up with original DSM
    mask_ds.SetGeoTransform(ds.GetGeoTransform())

    # tell temporary mask to use the same CRS as the original DSM
    mask_ds.SetProjection(ds.GetProjection())

    # put binary edge data into raster
    mask_ds.GetRasterBand(1).WriteArray(edge_mask)

    return mask_ds

# function to trace a vector shape around the binary edge stored in RAM
def polygonize_mask(mask_ds):
    # tell OGR to use a memory based vector (RAM)
    shape_driver = ogr.GetDriverByName("Memory")

    # actually create the data source
    shape_ds = shape_driver.CreateDataSource("out")

    # create a vector layer in the data source; srs can be None for now since we transform it later
    layer = shape_ds.CreateLayer("poly", srs=None)

    # create field definition used to store polygon IDs
    fd = ogr.FieldDefn("id", ogr.OFTInteger)

    # add "id" field to the vector layer
    layer.CreateField(fd)

    # trace boundaries of raster into vector polygons
    gdal.Polygonize(mask_ds.GetRasterBand(1), None, layer, 0, [], callback=None)

    return shape_ds, layer

# function to transform CRS
def transform_crs(ds):
    # store the CRS of the input file; should be EPSG: 32627 if using Solo
    source_srs = osr.SpatialReference()
    source_srs.ImportFromWkt(ds.GetProjection())

    # KML must be represented in EPSG: 4326 or it'll do some funky stuff
    target_srs = osr.SpatialReference()
    target_srs.ImportFromEPSG(4326)

    # transform source CRS to traget CRS
    transform = osr.CoordinateTransformation(source_srs, target_srs)

    return transform

# find largest polygon by area to avoid having outline AND weird rectangle thing
def find_largest_polygon(layer, transform):
    max_geom = None
    max_area = 0

    # transform each polygon in layer to EPSG: 4326
    for feature in layer:
        geom = feature.GetGeometryRef().Clone()  
        geom.Transform(transform)

        # store largest polygon
        area = geom.GetArea()
        if area > max_area:
            max_geom = geom
            max_area = area
    return max_geom

def create_kml_outline(file, save=False):

    # idk what this does
    gdal.DontUseExceptions()

    # get GDAL dataset (ds), raster data array (arr), and NoData value (nodata)
    ds, arr, nodata = load_dem(file)

    # create binary mask (0: nodata, 1: valid data)
    edge_mask = extract_edge_mask(arr, nodata, dialations=2)

    # convert binary mask back into GDAL raster
    mask_ds = mask_to_memory_raster(edge_mask, ds)

    # polygonize the binary mask; have to return shape_ds or else layer gets mad
    shape_ds, layer = polygonize_mask(mask_ds)

    # convert original CRS to EPSG: 4326 so KML can interpret it
    transform = transform_crs(ds)

    # iterate over all polygons in layer; return the biggest polygon in layer
    max_geom = find_largest_polygon(layer, transform)

    # create kml 
    kml = simplekml.Kml()

    # only write the largest polygon to KML
    if max_geom is not None:

        # extract only the outer ring from max_geom polygon
        ring = max_geom.GetGeometryRef(0)

        # loop through each point in outer ring and get longitude and latitude for each point
        # additionally, KML expects (latitude, longitude) (Y, X) instead of standard (longitude, latitude) so they get flipped
        coords = [(ring.GetY(i), ring.GetX(i)) for i in range(ring.GetPointCount())]

        # create polygon in KML using coordinates from outer ring
        pol = kml.newpolygon(name="DSM Outline", outerboundaryis=coords)
        
        # set fill color for polygon
        pol.style.polystyle.color = simplekml.Color.changealphaint(100, simplekml.Color.red) 
        
        # set outline color
        pol.style.linestyle.color = simplekml.Color.red
        
        # set line width
        pol.style.linestyle.width = 1

    # save to file if specified
    if save:
        kml_file = file.split('.')[0] + '.kml'
        kml.save(kml_file)
        print(f"KML saved as: {kml_file}")
    else:
        return kml

# function to generate a Shapely polygon function form a DEM
def create_shapely_geometry(file):

    # idk what this does
    gdal.DontUseExceptions()

    # get GDAL dataset (ds), raster data array (arr), and NoData value (nodata)
    ds, arr, nodata = load_dem(file)

    # create binary mask (0: nodata, 1: valid data)
    edge_mask = extract_edge_mask(arr, nodata, dialations=2)

    # convert binary mask back into GDAL raster
    mask_ds = mask_to_memory_raster(edge_mask, ds)

    # polygonize the binary mask; have to return shape_ds or else layer gets mad
    shape_ds, layer = polygonize_mask(mask_ds)

    # convert original CRS to EPSG: 4326 so KML can interpret it
    transform = transform_crs(ds)

    # iterate over all polygons in layer; return the biggest polygon in layer
    max_geom = find_largest_polygon(layer, transform)

    if max_geom is not None:

        # extract only the outer ring from max_geom polygon
        ring = max_geom.GetGeometryRef(0)

        # loop through each point in outer ring and get longitude and latitude for each point
        coords = [(ring.GetX(i), ring.GetY(i)) for i in range(ring.GetPointCount())]

        # flip coordinates
        coords = [(x, y) for y, x in coords] 

        # return Shapely polygon
        return Polygon(coords)
    else:
        print("max_geom is None")
        return None
