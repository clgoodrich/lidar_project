# Lidar catalogue

Metadata only. No point cloud is stored here.

- `lidar_win_*_us.csv` are current (2026-11-04). Built by `notebooks/wellsight_v2/s1_build/_list_lidar_windows_inventory_us.py` from the USGS 2026 well file. Queries are paged and logged (`lidar_win_query_log_us.csv`). Cover is area-based from tile bounding boxes (an upper bound).
- `lidar_projects_by_county_us.csv`, `lidar_pilot_windows_us.csv`, `lidar_pilot_windows_summary_us.csv`, `lidar_download_list_pilot_5km_us.csv` are SUPERSEDED. They came from the 2022 file and scripts that did not page, hid failures and used tile-count ratios. Kept for the record.
- The API gives no flight date and no point density. Publication date is not flight date.
