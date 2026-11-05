"""Build the lidar download list from the window inventory (the downloader is _fetch_lidar_windows_us.py). Downloads nothing.
Inputs  data/_source/reference/lidar_catalogue/lidar_win_{projects,tile_window,tiles_unique}_us.csv
Outputs data/_source/reference/lidar_catalogue/lidar_win_download_list_us.csv   (window, project, tile, gb, url, dest)
        data/_source/reference/lidar_catalogue/lidar_win_download_urls_us.txt  (window|project|url, Pennsylvania first)
Run     python notebooks/wellsight_v2/s1_build/_make_lidar_download_bat_us.py
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
CAT = ROOT / "data/_source/reference/lidar_catalogue"
DEST = r"F:\lidar_project_data\lidar_us_windows"

P = pd.read_csv(CAT / "lidar_win_projects_us.csv").fillna("")
P = P[P.recommended != ""][["window", "project", "recommended", "cover"]]
M = pd.read_csv(CAT / "lidar_win_tile_window_us.csv")
T = pd.read_csv(CAT / "lidar_win_tiles_unique_us.csv")[["url", "tile", "mb"]]
D = M.merge(P, on=["window", "project"]).merge(T, on="url")
D["pa"] = ~D.window.str.startswith("Pennsylvania")
D = D.sort_values(["pa", "window", "tile"]).drop_duplicates("url")
D["dest"] = DEST + "\\" + D.project + "\\" + D.url.str.rsplit("/", n=1).str[-1]
D["gb"] = (D.mb / 1000).round(3)
D[["window", "project", "recommended", "cover", "tile", "gb", "url", "dest"]].to_csv(CAT / "lidar_win_download_list_us.csv", index=False)
(CAT / "lidar_win_download_urls_us.txt").write_text("\n".join(D.window + "|" + D.project + "|" + D.url) + "\n", encoding="ascii")
g = D.groupby("window").agg(project=("project", "first"), rec=("recommended", "first"), cover=("cover", "first"), tiles=("url", "size"), gb=("gb", "sum")).reset_index()
g["pa"] = ~g.window.str.startswith("Pennsylvania")
g = g.sort_values(["pa", "gb"], ascending=[True, False]).drop(columns="pa")
g.gb = g.gb.round(2)
g.to_csv(CAT / "lidar_win_download_summary_us.csv", index=False)
print(len(D), "tiles", round(D.gb.sum(), 1), "GB", len(g), "windows")
print(g.to_string(index=False))
