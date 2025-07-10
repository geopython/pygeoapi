-- A test database for the mysql provider; a simple geospatial app 

-- Create the database
DROP DATABASE IF EXISTS test_geo_app;
CREATE DATABASE test_geo_app;
USE test_geo_app;

-- Create the location table
CREATE TABLE location (
    locationID INT AUTO_INCREMENT PRIMARY KEY,
    locationName VARCHAR(100) NOT NULL,
    description TEXT,
    locationCoordinates POINT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    SPATIAL INDEX(locationCoordinates)
);

-- Insert sample geospatial data
INSERT INTO location (locationName, description, locationCoordinates) VALUES
('Central Park', 'A large public park in NYC', ST_GeomFromText('POINT(-73.9654 40.7829)')),
('Golden Gate Bridge', 'Iconic suspension bridge in SF', ST_GeomFromText('POINT(-122.4783 37.8199)')),
('Eiffel Tower', 'Famous Paris landmark', ST_GeomFromText('POINT(2.2945 48.8584)')),
('Sydney Opera House', 'Multi-venue performing arts centre in Australia', ST_GeomFromText('POINT(151.2153 -33.8568)')),
('Christ the Redeemer', 'Art Deco statue of Jesus Christ in Rio', ST_GeomFromText('POINT(-43.2105 -22.9519)'));
