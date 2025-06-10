from dem_outline import create_shapely_geometry, create_kml_outline
from shapely.geometry import Polygon, MultiPolygon
import simplekml

# function to get overlap for at least two DEMs
def get_overlap_kml(*dems, save=False):
    if len(dems) < 2:
        raise ValueError("At least two DEM files are required.")

    # generate first DEMs polygon shape which is saved into cumulative shape (overlap) that will be updated iteratively
    overlap = create_shapely_geometry(dems[0])
    if overlap is None:
        raise ValueError(f"{dems[0]} did not produce a usable shape.")

    # compare remaining shapes with previously established overlap shape
    for dem in dems[1:]:
        shape = create_shapely_geometry(dem)
        if shape is None:
            raise ValueError(f"{dem} did not produce a usable shape.")

        # update overlap shape 
        overlap = overlap.intersection(shape)

        if overlap.is_empty:
            print("No overlapping area found.")
            return None

    # create kml
    kml = simplekml.Kml()

    # logic for if shape is a polygon
    if overlap.geom_type == "Polygon":

        # loop through each point in outer ring and get longitude and latitude for each point
        coords = [(lon, lat) for lon, lat in overlap.exterior.coords]

        # create polygon in KML using coordinates from outer ring
        pol = kml.newpolygon(name="Overlap", outerboundaryis=coords)

        # set fill color for polygon
        pol.style.polystyle.color = simplekml.Color.changealphaint(120, simplekml.Color.red)

        # set outline color
        pol.style.linestyle.color = simplekml.Color.red

        # set line width
        pol.style.linestyle.width = 1

    # logic for if shape is a multipolygon; basically the same as polygon, just looping through all of the polygons in the shape
    elif overlap.geom_type == "MultiPolygon":

        # loop through each polygon in the shape
        for i, geom in enumerate(overlap.geoms):

            # loop through each point in outer ring and get longitude and latitude for each point
            coords = [(lon, lat) for lon, lat in geom.exterior.coords]

            # create polygon in KML using coordinates from outer ring
            pol = kml.newpolygon(name=f"Overlap {i+1}", outerboundaryis=coords)

            # set fill color for polygon
            pol.style.polystyle.color = simplekml.Color.changealphaint(120, simplekml.Color.red)

            # set outline color
            pol.style.linestyle.color = simplekml.Color.red

            # set line width
            pol.style.linestyle.width = 1

    # save to file if specified
    if save:
        kml.save('overlap.kml')
        print("KML saved as: overlap.kml")
    else:
        return kml

# create overlap kml and outline kmls; save needs to be True or else it won't save output
get_overlap_kml('Solo-2017-dsm.tif', 'Solo-2023-dsm.tif', 'Solo-2024-dsm.tif', save=True)
create_kml_outline('Solo-2017-dsm.tif', save=True)
create_kml_outline('Solo-2023-dsm.tif', save=True)
create_kml_outline('Solo-2024-dsm.tif', save=True)
