# KLMS Dashboard

KLMS Dashboard provides a quick overview to the user about key information related to the datasets, workflows and tasks managed by the KLMS based on the various metadata maintained for these entities. This dashboard comprises a series of charts (like histograms, pie charts, timelines, maps, wordclouds, etc.) that visually present aggregate statistics. 

For creating and presenting dashboards we use [Apache Superset](https://superset.apache.org/), an open-source platform for data visualization and exploration. Superset can connect to the PostgreSQL database where all metadata managed by the KLMS are being stored. Superset provides a graphical interface for creating charts and dashboards, as well as an SQL editor for writing SQL queries that retrieve the data to populate each chart. 


# List of visualizations

KLMS Dashboard currently offers the following visualizations: 

* V1 -- _Datasets over time_

    Number of new datasets published in the Data Catalog over time. [Timeline chart](visualizations/v1)

* V2 -- _Datasets geographic distribution_

    Heatmap constructed based on the spatial coverage (i.e., minimum bounding box) of the datasets published in the Data Catalog. [Map](visualizations/v2)

* V3 -- _Tag frequency_

    Number of datasets in the Data Catalog that are associated with each tag or with tags of each vocabulary. [Wordcloud](visualizations/v3)

* V4 -- _Files per format_

    Number of files in the Data Catalog per different file format (e.g., CSV, JSON, RDF). [Histogram](visualizations/v4)

* V5 -- _Files per size_

    Distribution of the size (in mbytes) of the files in the Data Catalog. [Histogram](visualizations/v5)

* V6 -- _Workflows per state_

    Number of workflows that have succeeded, failed or are currently running. [Pie chart](visualizations/v6)

* V7 -- _Workflows per schedule_

    Number of workflows scheduled to run hourly, daily, weekly, etc. [Pie chart](visualizations/v7)

* V8 -- _Workflows execution time distribution_

    Distribution of the execution time of workflows. [Histogram](visualizations/v8)

* V9 -- _Tasks execution time distribution_

    Distribution of the execution time of tasks. [Histogram](visualizations/v9)

* V10 -- _Metrics frequency_ 

    Number of tasks that each performance metric applies to. [Wordcloud](visualizations/v10)


# Import to Superset

In order to import any of the aforementioned visualizations in Superset, you must download its directory, e.g., `visualizations/v2`. This directory contains YAML specifications for connection to the database, extraction of the dataset, and definition of the chart. 

First, you need to specify credentials to the PostgreSQL database that holds all metadata. For each visualization (e.g., V2), open file `v2/databases/PostgreSQL-CKAN-DB.yaml` and edit your credentials for connecting to the PostgreSQL database:

```sh
sqlalchemy_uri: postgresql+psycopg2://USERNAME:PASSWORD@host.docker.internal:PORT/DATABASE
```

Then, compress the entire directory in a zip file, e.g., `v2.zip`. You must repeat this step for each one of the visualizations you wish to import to your Superset installation. 

Finally, in the Superset GUI, navigate under the tab *Charts*, click on button *Import Charts*, and specify the `.zip` file with all YAML specifications for this chart (database connection, dataset specification, chart definition). The chart will appear under the list of charts in the Superset GUI. If a chart with the same name exists, Superset may ask for confirmation to overwrite it.

