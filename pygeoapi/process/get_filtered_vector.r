
# /usr/bin/Rscript --vanilla /home/mbuurman/work/instance_pygeoapi/pygeoapi/pygeoapi/pygeoapi/process/get_filtered_vector.r 481051 basin 


# Get command line arguments, passed by python
args <- commandArgs(trailingOnly = TRUE)
print(paste0('Command line args: ', args))

# Imports
library(sf) # for write_sf
library(hydrographr) # for read_geopackage
library(stringr) # for str_remove

# Convert to number:
basin_id = as.numeric(args[1]) # e.g. 481051
print(paste0('Basin id: ', basin_id))

### TODO: How to get several?
var1_gpkg = args[2]
vars_gpkg = c(var1_gpkg)
print(paste0('Variables: ', vars_gpkg))

### And the variables? They were filtered during download! But we don't want to download!
### Check down below!
#vars_gpkg <- c("basin", "order_vect_segment")
#download_tiles(variable = vars_gpkg, tile_id = tile_id, file_format = "gpkg", download_dir =   paste0(wdir, "/data"))

# Define paths
wdir = "/home/mbuurman/work/hydro_casestudy_saofra"
saofra_dir <-  paste0(wdir, "/data/basin_", basin_id)
print(paste0('Will store to: ', saofra_dir))
print(paste0('Will find inputs here: ', wdir))

# Get the full paths of the basin GeoPackage tiles
# These are the ones we will use as inputs:
basin_dir <- list.files(wdir, pattern = "basin_h[v0-8]+.gpkg$", full.names = TRUE, recursive = TRUE)
print(paste0("Input files: ", basin_dir))

# Filter basin ID from the GeoPackages of the basin tiles
# Save the filtered tiles
for(itile in basin_dir) {
  #filtered_tile <- read_geopackage(itile, import_as = "sf", subc_id = basin_id, name = "ID")   
  filtered_tile <- read_geopackage(itile, import_as = "sf", subc_id = basin_id, name = "ID", layer_name=vars_gpkg)   
  # here must make sure it is not empty!
  write_sf(filtered_tile, paste(saofra_dir, paste0(str_remove(basename(itile), ".gpkg"), "_tmp.gpkg"), sep="/"))
}

# Merge filtered GeoPackage tiles
#merge_tiles(tile_dir = saofra_dir, tile_names = list.files(saofra_dir, full.names = FALSE, pattern = "basin_.+_tmp.gpkg$"), out_dir = saofra_dir, file_name = "basin_481051.gpkg", name = "ID", read = FALSE)
output_filename = paste0("basin_",basin_id,".gpkg")
print(paste0('Output file: ', output_filename))
merge_tiles(tile_dir = saofra_dir, tile_names = list.files(saofra_dir, full.names = FALSE, pattern = "basin_.+_tmp.gpkg$"), out_dir = saofra_dir, file_name = output_filename, name = "ID", read = FALSE)

print(paste0('RETURNNNN', paste(saofra_dir, output_filename, sep='/')))
