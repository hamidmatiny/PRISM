{% macro silver_relation(dataset) %}
  {#- DuckDB: read Spark-written parquet. Databricks: Unity Catalog silver table. -#}
  {% if target.type == "duckdb" %}
    read_parquet(
      '{{ var("lakehouse_root") }}/silver/{{ dataset }}/**/*.parquet',
      hive_partitioning=true,
      union_by_name=true
    )
  {% else %}
    {{ source("lakehouse_silver", dataset) }}
  {% endif %}
{% endmacro %}
