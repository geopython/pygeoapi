#! /bin/bash

# Source:
# https://github.com/glowabio/hydrographr/blob/main/inst/sh/snap_to_network.sh

##  file (e.g. txt or csv) that has been generated at the beginning
##  of the R function, based on the data.frame table the user provided
export DATA=$1

## name of the unique id column
export ID=$2

## names of the lon and lat columns
export LON=$3
export LAT=$4

## stream raster file (e.g. .tif file)
export STR=$5

## accumulation raster files
export ACC=$6

## What to calculate
export METHOD=$7

## radius distance
export rdist=$8

## accumulation threshold
export acct=$9

## Full path to output snap_points.txt file
export SNAP=${10}

## Temporary folder
export DIR=${11}



## Set random string
export RAND_STRING=$(xxd -l 8 -c 32 -p < /dev/random)

## save name of file without extension
#b=$(echo $DAT | awk -F"." '{print $1}')

# Note: Tmp output from R is already a .csv
# if the file is not csv, add the comma and make it .csv
#if [ "${DAT: -4}" != ".csv" ]
#then
#    cat  $DAT | tr -s '[:blank:]' ',' > ${b}.csv
#    export DATC=$(echo ${b}.csv)
#fi

##  make the file a gpkg -- works only if EPSG is 4326 (WGS 84)
# ogr2ogr -f "GPKG" -overwrite -nln ref_points -nlt POINT -a_srs EPSG:4326 \
#     $DIR/ref_points_${RAND_STRING}.gpkg $DATA -oo X_POSSIBLE_NAMES=$LON \
#     -oo Y_POSSIBLE_NAMES=$LAT -oo AUTODETECT_TYPE=YES

# how many points originally (save as reference)
# export op=$(ogrinfo -so -al $DIR/ref_points_${RAND_STRING}.gpkg \
#     | awk '/Feature/ {print $3}')

# how many points originally (save as reference)
export op=$(tail -n +2 $DATA | wc -l)

##  do the snapping in GRASS
grass -f --gtext --tmp-location $STR  <<'EOF'

# read stream raster file
r.in.gdal input=$STR output=stream

# read reference points
# v.in.ogr --o input=$DIR/ref_points_${RAND_STRING}.gpkg layer=ref_points output=ref_points \
#     type=point key=$ID

v.in.ascii -z in=$DATA out=ref_points separator=comma \
  cat=1 x=2 y=3 z=3 skip=1

# if not then identify id of those left out

if [ "$METHOD" = "distance" ]
then

    r.stream.snap --o input=ref_points output=snap_points stream_rast=stream \
        radius=$rdist

    # are all the original points in there?
    np=$(v.info snap_points | awk '/points:/{print $5}')

    # if not, then identify the ids of the points left out (out of extention of
    # stream raster file)
    if [[ $op != $np  ]]
    then
        lo=($(comm -3 \
            <(v.report -c map=ref_points option=coor | awk -F"|" '{print $1}') \
            <(v.report -c map=snap_points option=coor | awk -F"|" '{print $1}')))

        for i in ${lo[@]}
        do
            echo "$i,out-bbox,out-bbox,,NA" > $DIR/stream_ID_${RAND_STRING}_d_tmp.txt
        done
    fi

    r.what --o -v map=stream points=snap_points separator=comma \
        null_value=NA >> $DIR/stream_ID_${RAND_STRING}_d_tmp.txt

    echo "lon_snap_dist lat_snap_dist occu_id" > $DIR/snap_coords_${RAND_STRING}_d.txt

    if [[ "${#lo[@]}" -gt 0  ]]
    then
        for i in ${lo[@]}
        do
            echo "out-bbox out-bbox $i" >> $DIR/snap_coords_${RAND_STRING}_d.txt
        done
    fi

    v.out.ascii -c input=snap_points separator=space | awk 'NR > 1' \
        >> $DIR/snap_coords_${RAND_STRING}_d.txt

    cat  $DATA | tr -s ',' ' ' > $DIR/coords_${RAND_STRING}.txt

    paste -d" " \
        <(sort -gk1n $DIR/coords_${RAND_STRING}.txt) \
        <(sort -gk3n $DIR/snap_coords_${RAND_STRING}_d.txt) \
        <(printf "%s\n" subc_id_snap_dist $(awk -F, '{print $1, $5}' $DIR/stream_ID_${RAND_STRING}_d_tmp.txt | sort -gk1n | awk '{print $2}'))  \
        >  $DIR/final_tmp_${RAND_STRING}.txt

    awk '{print $1, $2, $3, $4, $5, $7}' \
        $DIR/final_tmp_${RAND_STRING}.txt \
        > $SNAP

    rm $DIR/snap_coords_${RAND_STRING}_d.txt $DIR/stream_ID_${RAND_STRING}_d_tmp.txt \
       $DIR/final_tmp_${RAND_STRING}.txt
fi
#
#
if [ "$METHOD" = "accumulation" ]
then
    r.in.gdal input=$ACC output=accum
    r.stream.snap --o input=ref_points output=snap_points stream_rast=stream \
        radius=$rdist accumulation=accum threshold=$acct

    # are all the original points in there?
    np=$(v.info snap_points | awk '/points:/{print $5}')

    # if not, then identify the ids of the points left out (out of extention of
    # stream raster file)
    if [[ $op != $np  ]]
    then
        lo=($(comm -3 \
            <(v.report -c map=ref_points option=coor | awk -F"|" '{print $1}') \
            <(v.report -c map=snap_points option=coor | awk -F"|" '{print $1}')))

        for i in ${lo[@]}
        do
            echo "$i,out-bbox,out-bbox,,NA" > $DIR/stream_ID_${RAND_STRING}_a_tmp.txt
        done
    fi

    r.what --o -v map=stream points=snap_points separator=comma \
        null_value=NA >> $DIR/stream_ID_${RAND_STRING}_a_tmp.txt

    echo "lon_snap_accu lat_snap_accu occu_id" > $DIR/snap_coords_${RAND_STRING}_a.txt

    if [[ "${#lo[@]}" -gt 0  ]]
    then
        for i in ${lo[@]}
        do
            echo "out-bbox out-bbox $i" >> $DIR/snap_coords_${RAND_STRING}_a.txt
        done
    fi

    v.out.ascii -c input=snap_points separator=space | awk 'NR > 1' \
        >> $DIR/snap_coords_${RAND_STRING}_a.txt

    cat  $DATA | tr -s ',' ' ' > $DIR/coords_${RAND_STRING}.txt

    paste -d" " \
        <(sort -gk1n $DIR/coords_${RAND_STRING}.txt) \
        <(sort -gk3n $DIR/snap_coords_${RAND_STRING}_a.txt) \
        <(printf "%s\n" subc_id_snap_accu $(awk -F, '{print $1, $5}' $DIR/stream_ID_${RAND_STRING}_a_tmp.txt | sort -gk1n | awk '{print $2}'))  \
        >  $DIR/final_tmp_${RAND_STRING}.txt

    awk '{print $1, $2, $3, $4, $5, $7}' \
        $DIR/final_tmp_${RAND_STRING}.txt \
        > $SNAP

    rm $DIR/snap_coords_${RAND_STRING}_*.txt $DIR/stream_ID_${RAND_STRING}_*.txt \
        $DIR/final_tmp_${RAND_STRING}.txt
fi


if [ "$METHOD" = "both" ]
then
    r.stream.snap --o input=ref_points output=snap_points_d stream_rast=stream \
        radius=$rdist

    # are all the original points in there?
    np=$(v.info snap_points_d | awk '/points:/{print $5}')

    # if not, then identify the ids of the points left out (out of extention of
    # stream raster file)
    if [[ $op != $np  ]]
    then
        lo=($(comm -3 \
            <(v.report -c map=ref_points option=coor | awk -F"|" '{print $1}') \
            <(v.report -c map=snap_points_d option=coor | awk -F"|" '{print $1}')))

        for i in ${lo[@]}
        do
            echo "$i,out-bbox,out-bbox,,NA" > $DIR/stream_ID_${RAND_STRING}_d_tmp.txt
            echo "$i,out-bbox,out-bbox,,NA" > $DIR/stream_ID_${RAND_STRING}_a_tmp.txt
        done
    fi

    r.what --o -v map=stream points=snap_points_d separator=comma \
        null_value=NA >> $DIR/stream_ID_${RAND_STRING}_d_tmp.txt


    r.in.gdal input=$ACC output=accum
    r.stream.snap --o input=ref_points output=snap_points_a stream_rast=stream \
        radius=$rdist accumulation=accum threshold=$acct

    r.what --o -v map=stream points=snap_points_a separator=comma \
        null_value=NA >> $DIR/stream_ID_${RAND_STRING}_a_tmp.txt


    echo "lon_snap_dist lat_snap_dist occu_id" > $DIR/snap_coords_${RAND_STRING}_d.txt
    echo "lon_snap_accu lat_snap_accu occu_id" > $DIR/snap_coords_${RAND_STRING}_a.txt

    if [[ "${#lo[@]}" -gt 0  ]]
    then
        for i in ${lo[@]}
        do
            echo "out-bbox out-bbox $i" >> $DIR/snap_coords_${RAND_STRING}_d.txt
            echo "out-bbox out-bbox $i" >> $DIR/snap_coords_${RAND_STRING}_a.txt
        done
    fi


    v.out.ascii -c input=snap_points_d separator=space | awk 'NR > 1'  \
        >> $DIR/snap_coords_${RAND_STRING}_d.txt


    v.out.ascii -c input=snap_points_a separator=space | awk 'NR > 1' \
        >> $DIR/snap_coords_${RAND_STRING}_a.txt


    cat  $DATA | tr -s ',' ' ' > $DIR/coords_${RAND_STRING}.txt

    paste -d" " \
        <(sort -gk1n $DIR/coords_${RAND_STRING}.txt) \
        <(sort -gk3n $DIR/snap_coords_${RAND_STRING}_d.txt) \
        <(printf "%s\n" subc_id_snap_dist $(awk -F, '{print $1, $5}' $DIR/stream_ID_${RAND_STRING}_d_tmp.txt | sort -gk1n | awk '{print $2}'))  \
        <(sort -gk3n $DIR/snap_coords_${RAND_STRING}_a.txt) \
        <(printf "%s\n" subc_id_snap_accu $(awk -F, '{print $1, $5}' $DIR/stream_ID_${RAND_STRING}_a_tmp.txt | sort -gk1n | awk '{print $2}'))  \
        >  $DIR/final_tmp_${RAND_STRING}.txt  #$SNAP

    awk '{print $1, $2, $3, $4, $5, $7, $8, $9, $11}' \
        $DIR/final_tmp_${RAND_STRING}.txt \
        > $SNAP


    rm $DIR/snap_coords_${RAND_STRING}_*.txt $DIR/stream_ID_${RAND_STRING}_*.txt \
        $DIR/final_tmp_${RAND_STRING}.txt
fi


EOF

# rm $DIR/ref_points_${RAND_STRING}.gpkg
