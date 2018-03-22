
outDic={'name_alt': None, 'scalerank': 0, 'featureclass': 'Lake', 'OGC_FID': 25, 'admin': 'admin-0', 'name': 'Lake\rMichigan', 'AsGeoJSON(geometry)': '{"type":"Polygon","coordinates":[[[-85.53999284538474,46.03000722918407],[-84.75355506055086,45.92448395444408],[-84.93000423861146,45.78999603940448],[-85.06999569369014,45.40999339454619],[-85.29044735384727,45.30824249936348],[-85.46710323763704,44.81457754167922],[-85.55999162468168,45.15000926368577],[-85.95983801954005,44.91059235287752],[-86.20935767286137,44.57479889584493],[-86.47027197950303,44.08423452409817],[-86.52001054558397,43.65999685319803],[-86.18842871778315,43.04140412044817],[-86.21604977084317,42.38170278581012],[-86.62191647006355,41.8944198675139],[-86.8244364082154,41.75618541113313],[-87.09444576694042,41.64616628678373],[-87.4342183092595,41.64071442317694],[-87.52617652052288,41.70851390234388],[-87.79569495314115,42.23411489518453],[-87.80344641798492,42.49399567318035],[-87.77672970249003,42.74085399023863],[-87.9021484036624,43.23051402442028],[-87.71221167677363,43.79650014909702],[-87.48635982944199,44.49335683855294],[-86.9674767727993,45.26287059181122],[-87.11806189649782,45.25933075619923],[-87.85282324903983,44.6150548366003],[-87.98831885450911,44.73331635190025],[-87.59643063022369,45.09370779070377],[-87.00000708692704,45.73999909116209],[-86.31999691439827,45.82999359799839],[-85.53999284538474,46.03000722918407]]]}'}

from marshmallow import Schema,fields


property_fields = {
    'name_alt': fields.String(),
    'scalerank': fields.Int(),
    'featureclass': fields.String(),
    'admin': fields.String(),
    'admin-0': fields.String(), 
    'name': fields.String() 
}

#class GeometrySchema(Schema):
#   type = fields.String()
#   coordinates = fields.List(fields.List(fields.Float())) 


class PropertiesSchema(Schema):
    title = fields.String(default='Untitled')

    def __init__(self, property_fields=None, **kwargs):
        super().__init__(**kwargs)
        self.declared_fields.update(property_fields)    
 
#"geometry": {
#               "type": "LineString",
#               "coordinates": [
#                   [102.0, 0.0], [103.0, 1.0], [104.0, 0.0], [105.0, 1.0]
#               ]
#           },


class GeometrySchema(Schema):
    type = fields.String()

class FeatureSchema(Schema):
   type = "Feature"
   id = fields.Int(load_from="OGC_FID")
   #geometry = fields.List(load_from="AsGeoJSON(geometry)")
   properties = fields.Nested(PropertiesSchema)



class PropertiesSchema(Schema):
    title = fields.String(default='Untitled')

    def __init__(self, property_fields=None, **kwargs):
        super().__init__(**kwargs)
        self.declared_fields.update(property_fields)	


class FeatureCollectionSchema(Schema):
    #type = fields.String(default='FeatureCollection')
    type = "FeatureCollection"
    features = fields.Nested(FeatureSchema,many=True)


#feature=FeatureSchema().load(outDic) 
#print(feature)
#print(outDic['AsGeoJSON(geometry)'])
print(GeometrySchema().load(outDic['AsGeoJSON(geometry)']))
#properties = GeoJSONProperties(property_fields=property_fields)

#print(properties.dump(outDic).data)  # {'foo': 123}
#GeometrySchema
