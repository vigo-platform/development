# development

## Kibana dashboard

Copy `.env.example` to `.env`, fill in the required values, then run:

```sh
docker compose up -d
```

The `kibana-setup` service waits up to 10 minutes for Kibana, then imports
`dashboards/kibana/export.ndjson`, including its data view and visualizations.
It exits with code 0 after a successful import. Keep the entire `dashboards/kibana`
directory with the Compose file when copying or checking out this project on another machine.

Open [VIGO | Log Monitoring & Investigation](http://localhost:5601/app/dashboards#/view/92140dea-64ef-42ad-81da-9e7649d63bb9).
Panels populate when logs matching `app-logs*` arrive in Elasticsearch.

Each `docker compose up` reruns the completed setup service. Matching saved objects
are overwritten from the export without creating duplicates; export any UI changes
back to this file if you want to keep them on subsequent startups.

Check the import result or manually rerun it:

```sh
docker compose logs kibana-setup
docker compose run --rm kibana-setup
```

To run the importer directly on your machine while Kibana is running:

```sh
python3 dashboards/kibana/import_dashboard.py
```

Direct execution connects to `http://localhost:5601`; Compose sets `KIBANA_URL`
to `http://kibana:5601`. Set `KIBANA_URL` explicitly to target a different server.
While waiting, the script prints the connection error or Kibana status every 5 seconds.

Import uses Kibana's [saved objects import API](https://www.elastic.co/docs/api/doc/kibana/v8/operation/operation-importsavedobjectsdefault).
