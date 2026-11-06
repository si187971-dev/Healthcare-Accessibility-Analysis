# Urban Healthcare Accessibility Analysis

**Network-based walking accessibility to outpatient clinics in Saint Petersburg, Russia**

This project demonstrates a GIS and Data Science workflow:

**Geospatial data collection → Network analysis → Spatial accessibility metrics → Interactive visualization → Urban planning insights**

---

## Overview

This project evaluates pedestrian accessibility to outpatient healthcare facilities using OpenStreetMap data and Python-based geospatial analysis.

The study covers three districts of Saint Petersburg:

- Frunzensky District
- Moskovsky District
- Nevsky District

The main objective is to identify residential buildings and areas with limited access to outpatient healthcare facilities within a **10-minute walking threshold**.

## Research Questions

1. What proportion of residential buildings is within a 10-minute walk of an identified outpatient clinic?
2. What proportion of residential land-use area is covered by 10-minute walking isochrones?
3. Where are residential areas with limited pedestrian accessibility to healthcare facilities?
4. How does healthcare accessibility vary between districts?

## Data Sources

**OpenStreetMap (OSM)** provides:

- Pedestrian street and path networks
- Healthcare facilities and their attributes
- Residential building footprints
- Residential land-use polygons
- Administrative district boundaries

Data is retrieved using OSMnx and processed with GeoPandas.

## Methodology

The analysis consists of six main stages:

1. **Data collection:** Downloading pedestrian networks, healthcare facilities, residential buildings and land-use polygons from OpenStreetMap.
2. **Healthcare facility identification:** Filtering OSM healthcare objects using tags and facility names.
3. **Network preparation:** Assigning walking times to pedestrian network edges based on their lengths.
4. **Isochrone analysis:** Constructing network-based 10-minute accessibility zones around healthcare facilities.
5. **Building-level accessibility:** Connecting residential building centroids to their nearest pedestrian network nodes and calculating shortest travel times using the multi-source Dijkstra algorithm.
6. **Visualization:** Creating interactive maps with accessibility categories, healthcare locations and residential areas outside the 10-minute coverage zones.

### Model Assumptions

| Parameter | Value |
|---|---|
| Walking speed | 4.5 km/h |
| Primary accessibility threshold | 10 minutes |
| Travel mode | Walking |
| Routing algorithm | Multi-source Dijkstra |
| Network data | OpenStreetMap |

Travel times are calculated from pedestrian network edge lengths and a constant walking speed.

## Results

### Frunzensky District

| Indicator | Result |
|---|---:|
| Residential buildings analyzed | 1,107 |
| Buildings within 10 minutes | 673 |
| Building accessibility rate | 60.8% |
| Residential land-use area covered | 62.7% |

### Moskovsky District

| Indicator | Result |
|---|---:|
| Residential buildings analyzed | 1,394 |
| Buildings within 10 minutes | 680 |
| Building accessibility rate | 48.8% |
| Buildings requiring more than 20 minutes | 223 |
| Median walking time | 10.3 minutes |

### Nevsky District

Results to be added after analysis.

**Important:** Building accessibility and residential land-use coverage are different metrics. Building accessibility measures the share of analyzed buildings within the travel-time threshold, while land-use coverage measures the share of residential land area covered by the calculated isochrones.

## Interactive Map

![Healthcare accessibility map](https://si187971-dev.github.io/accessibility/outputs/maps/accessibility_overview.png)

[Open interactive accessibility map](https://si187971-dev.github.io/accessibility/outputs/accessibility_map.html)

The Folium map includes switchable layers showing healthcare facilities, walking accessibility zones, residential buildings classified by travel time and residential areas outside the coverage zones.

## Tech Stack

| Library | Purpose |
|---|---|
| Python | Data processing and analysis |
| OSMnx | OpenStreetMap data extraction and pedestrian network construction |
| NetworkX | Shortest-path and multi-source Dijkstra calculations |
| GeoPandas | Geospatial data processing |
| Shapely | Geometry operations and spatial analysis |
| Folium | Interactive web maps |
| Pandas / NumPy | Tabular and numerical analysis |
| Matplotlib | Statistical visualization |

## Installation

Clone the repository:

```bash
git clone https://github.com/si187971-dev/accessibility.git
cd accessibility
```

Install the required dependencies:

```bash
python -m pip install -r requirements.txt
```

The project also requires the local `network_isochrones.py` module.

## How to Run

Open the project in VS Code.

In `hospitals_availability.py`, select the district:

```python
PLACE = "Невский район, Санкт-Петербург"
```

Run the analysis:

```bash
python hospitals_availability.py
```

The script downloads the required OpenStreetMap data, builds the pedestrian network, calculates accessibility indicators and generates an interactive Folium map.

Downloaded data and pedestrian graphs are cached locally to reduce repeated requests.

**Note:** The initial download may take time depending on the selected district and Overpass API availability.

## Repository Structure

```text
accessibility/
├── README.md
├── hospitals_availability.py
├── network_isochrones.py
├── requirements.txt
└── data/
         ├── osmnx_cache/
         └── outputs/├── accessibility_map.html
                     └── maps/
                     └── accessibility_overview.png
    

```

The structure above is illustrative and should be adjusted to match the actual repository.

## Limitations

- OpenStreetMap data may be incomplete or contain classification errors.
- Healthcare facilities located outside the selected district are not included in the current facility selection.
- Building travel times are calculated from the nearest network node rather than the actual building entrance.
- The analysis assumes a constant walking speed and does not account for individual mobility limitations.
- Population distribution, facility capacity, service availability and appointment availability are not considered.
- Accessibility results are sensitive to the completeness of the healthcare facility dataset and pedestrian network.

## Future Improvements

- Include healthcare facilities in neighboring districts.
- Incorporate population distribution and residential density.
- Evaluate alternative walking-time thresholds.
- Investigate buildings with unusually long calculated routes.
- Develop a comparative accessibility dashboard for multiple districts.
- Explore potential locations for additional healthcare services based on accessibility and population demand.

## Urban Planning Relevance

The analysis provides a preliminary spatial assessment of healthcare accessibility.

Areas with long walking times can be prioritized for further investigation. However, recommendations for new healthcare facilities require additional evidence, including population demand, existing facility capacity, available sites and applicable planning requirements.