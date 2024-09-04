

import inspect


def get_set_url_parameters(self: "SpeckleProvider"):
    """Parse and save URL parameters."""

    from pygeoapi.provider.speckle_utils.crs_utils import create_crs_from_authid
    
    crsauthid = False
    
    if (isinstance(self.data, str)):
        
        for item in self.data.lower().split("&"):
            # if CRS authid is found, rest will be ignored
            if "speckleurl=" in item:
                try:
                    speckle_url = item.split("speckleurl=")[1]
                    if "/projects/" not in speckle_url or "/models/" not in speckle_url:
                        raise ValueError(f"Provide valid Speckle Model URL: {item}")

                    if speckle_url[-1] == "/":
                        speckle_url = speckle_url[:-1]
                    self.speckle_project_url = speckle_url.split("/models")[0]
                except:
                    raise ValueError(f"Provide valid Speckle Model URL: {item}")

            elif "datatype=" in item:
                try:
                    requested_data_type = item.split("datatype=")[1]
                    if requested_data_type in ["points", "lines", "polygons", "projectcomments"]:
                        self.requested_data_type = requested_data_type
                except:
                    raise ValueError(f"Provide valid dataType parameter (points/lines/polygons/projectcomments): {item}")     
            
            elif "preserveattributes=" in item:
                try:
                    preserve_attributes = item.split("preserveattributes=")[1]
                    if preserve_attributes in ["true", "false"]:
                        self.preserve_attributes = preserve_attributes
                except:
                    ValueError(f"Provide valid preserverAttributes parameter (true/false): {item}")

            elif "crsauthid=" in item:
                crs_authid = item.split("crsauthid=")[1]
                if isinstance(crs_authid, str) and len(crs_authid)>3:
                    crsauthid = True
                    self.crs_authid = crs_authid

            elif "lat=" in item:
                try:
                    lat = float(item.split("lat=")[1])
                    self.lat = lat
                except:
                    raise ValueError(f"Invalid Lat input, must be numeric: {item}")
            elif "lon=" in item:
                try:
                    lon = float(item.split("lon=")[1])
                    self.lon = lon
                except:
                    raise ValueError(f"Invalid Lon input, must be numeric: {item}")
            elif "northdegrees=" in item:
                try:
                    north_degrees = float(item.split("northdegrees=")[1])
                    self.north_degrees = north_degrees
                except:
                    raise ValueError(f"Invalid northDegrees input, must be numeric: {item}")    
            elif "limit=" in item:
                try:
                    limit = int(item.split("limit=")[1])
                    if limit>0: 
                        self.limit = limit
                except:
                    ValueError(f"Invalid limit input, must be a positive integer: {item}")
                

        if self.speckle_url == "-":
            self.missing_url = "true"

        # if CRS authid is found, rest will be ignored
        if crsauthid:
            self.lat = str(self.lat) + " (not applied)"
            self.lon = str(self.lon) + " (not applied)"
            self.north_degrees = str(self.north_degrees) + " (not applied)"

        # if CRS parameter present, create and assign CRS:
        if len(self.crs_authid)>3:
            create_crs_from_authid(self)
