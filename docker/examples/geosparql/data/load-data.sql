ld_dir('.', '*.ttl', 'http://www.example.org/POI#');
rdf_loader_run();
checkpoint;

# Log table:
select * from DB.DBA.load_list;

