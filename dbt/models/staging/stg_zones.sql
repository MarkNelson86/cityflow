select
    LocationID as zone_id,
    Borough as borough,
    Zone as zone_name,
    service_zone,
    source_sha256
from {{ source('cityflow_raw', 'zones') }}
