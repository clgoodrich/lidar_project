This repository contains the following: 

- `training` folder: Datasets used to train well pad and storage tank models. Note that `annotations_image` for each example are with respect to a image downloaded from the Google Earth satellite basemap at zoom level 1600 and EPSG:3857, with sizes 640x640px and 512x512px for well pads and storage tanks respectively (see also the `image_extent` column). `annotations_latlon` also provides the annotations in coordinate space. We also note that we are unable to redistribute the satellite imagery used to train the models in this study due to data licensing. Samples of satellite images may be made available upon request to the corresponding author.

- `deployment` folder: Deployment detections for well pads and storage tanks across the entire Permian and Denver basins. Datasets contain confidence scores (`bbox_score`) and coordinate locations (`geometry`) for each detection, as well as a well pad identifier (`wp_id`) that indicates which well pad a storage tank belongs to.


